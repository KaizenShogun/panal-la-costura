#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LA COSTURA — arte generativo. V203, ventana de anchura. Sin medir nada.

No dibujo hexágonos. Dibujo CENTROS y dejo que el Voronoi decida la forma.
Dos cuadrillas de abejas empiezan el panal por sitios distintos, con paso
distinto (obrera ~5,2 mm, zángano ~6,4 mm) y orientación distinta, y avanzan a
oscuras hasta encontrarse. Donde se encuentran, nadie puede poner un hexágono:
salen pentágonos y heptágonos, casi siempre por parejas. Eso no lo programo yo;
emerge del teselado. Yo sólo lo pinto para que se vea.

Hecho con la librería estándar. Salida: SVG.
"""
import math, random, os

W, H = 1680, 1180           # lienzo (los últimos 90 px son la cartela)
ALTO_PANEL = 1030           # hasta dónde llega el panal
MARGEN = 200                # los sitios se generan más allá del marco
PASO_A = 52.0               # paso de la cuadrilla de abajo (celda de obrera)
RATIO = 6.4 / 5.2           # obrera → zángano, el ratio real
PASO_B = PASO_A * RATIO     # paso de la cuadrilla de arriba
ROT_A = math.radians(1.5)
ROT_B = math.radians(19.0)  # desajuste de orientación: el otro eje del conflicto
SEMILLA = 7

# la costura no es recta: ondula, como en el panal de verdad
def y_costura(x):
    return ALTO_PANEL * 0.44 + 58 * math.sin(x / 240.0) + 22 * math.sin(x / 83.0 + 1.3)

# ── paleta: cera, miel, propóleo ──────────────────────────────────────────────
FONDO      = "#F2E8D5"
PARED      = "#2B2117"
CELDA      = "#FAF3E2"
PENTAGONO  = "#E39B22"   # miel
HEPTAGONO  = "#7A3D11"   # propóleo
RARO       = "#A32C22"   # 4, 8, 9 lados: existen, y son pocos


def cera(t):
    """Tono de cera: entre la recién estirada y la ya curada. Ninguna celda igual."""
    a = (0xFC, 0xF6, 0xE8)
    b = (0xEE, 0xDF, 0xC0)
    return "#%02X%02X%02X" % tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def lattice(paso, rot, dentro, margen_extra=0.0):
    """Retículo triangular rotado; su Voronoi es el panal hexagonal."""
    pts = []
    dy = paso * math.sqrt(3) / 2
    n_i = int((W + 2 * MARGEN) / paso) + 4
    n_j = int((ALTO_PANEL + 2 * MARGEN) / dy) + 4
    cx, cy = W / 2, ALTO_PANEL / 2
    c, s = math.cos(rot), math.sin(rot)
    for j in range(-n_j, n_j):
        for i in range(-n_i, n_i):
            x = i * paso + (j % 2) * paso / 2
            y = j * dy
            xr = cx + x * c - y * s
            yr = cy + x * s + y * c
            if -MARGEN <= xr <= W + MARGEN and -MARGEN <= yr <= ALTO_PANEL + MARGEN:
                if dentro(xr, yr, margen_extra):
                    pts.append([xr, yr])
    return pts


def recortar(poly, p, q):
    """Sutherland-Hodgman contra el semiplano de los más cercanos a p que a q."""
    nx, ny = q[0] - p[0], q[1] - p[1]
    mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
    c = nx * mx + ny * my
    out = []
    n = len(poly)
    for k in range(n):
        a = poly[k]
        b = poly[(k + 1) % n]
        da = nx * a[0] + ny * a[1] - c
        db = nx * b[0] + ny * b[1] - c
        if da <= 0:
            out.append(a)
        if (da < 0 < db) or (db < 0 < da):
            t = da / (da - db)
            out.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
    return out


def limpiar(poly, eps=0.9):
    """Sin esto un hexágono exacto sale de 12 lados por astillas de coma flotante."""
    if len(poly) < 3:
        return poly
    p = []
    for v in poly:
        if not p or math.dist(v, p[-1]) > eps:
            p.append(v)
    if len(p) > 1 and math.dist(p[0], p[-1]) <= eps:
        p.pop()
    # colineales fuera: un vértice que no dobla no es un vértice
    q = []
    n = len(p)
    for k in range(n):
        a, b, c_ = p[k - 1], p[k], p[(k + 1) % n]
        v1 = (b[0] - a[0], b[1] - a[1])
        v2 = (c_[0] - b[0], c_[1] - b[1])
        cross = v1[0] * v2[1] - v1[1] * v2[0]
        l1 = math.hypot(*v1) or 1e-9
        l2 = math.hypot(*v2) or 1e-9
        if abs(cross) / (l1 * l2) > 0.02:
            q.append(b)
    return q if len(q) >= 3 else p


def voronoi(sitios, k=26):
    """O(n·k) recortando sólo contra los k vecinos más cercanos. Basta en retículo."""
    caja = [(-MARGEN, -MARGEN), (W + MARGEN, -MARGEN),
            (W + MARGEN, ALTO_PANEL + MARGEN), (-MARGEN, ALTO_PANEL + MARGEN)]
    celdas = []
    for i, p in enumerate(sitios):
        d = sorted(((math.dist(p, q), j) for j, q in enumerate(sitios) if j != i))[:k]
        poly = caja
        for _, j in d:
            poly = recortar(poly, p, sitios[j])
            if len(poly) < 3:
                break
        celdas.append(limpiar(poly))
    return celdas


def relajar(sitios, celdas, sigma):
    """Lloyd LOCAL: sólo la cera cercana a la costura fluye. Lejos, el retículo manda.
    Es la parte que las abejas hacen de verdad: ajustan varias celdas ANTES de llegar."""
    nuevos = []
    for p, poly in zip(sitios, celdas):
        if len(poly) < 3:
            nuevos.append(p); continue
        a2 = 0.0; cx = 0.0; cy = 0.0
        n = len(poly)
        for k in range(n):
            x0, y0 = poly[k]; x1, y1 = poly[(k + 1) % n]
            cr = x0 * y1 - x1 * y0
            a2 += cr; cx += (x0 + x1) * cr; cy += (y0 + y1) * cr
        if abs(a2) < 1e-9:
            nuevos.append(p); continue
        cx /= (3 * a2); cy /= (3 * a2)
        d = abs(p[1] - y_costura(p[0]))
        w = math.exp(-(d * d) / (2 * sigma * sigma))
        nuevos.append([p[0] + w * (cx - p[0]), p[1] + w * (cy - p[1])])
    return nuevos


def main():
    random.seed(SEMILLA)
    abajo = lattice(PASO_A, ROT_A, lambda x, y, m: y > y_costura(x) + m)
    arriba = lattice(PASO_B, ROT_B, lambda x, y, m: y < y_costura(x) - m)

    # Ninguna cuadrilla puede poner un centro encima del de la otra: el que llega
    # tarde cede. Ese descarte es todo el "conflicto"; lo demás lo hace la geometría.
    sitios = list(abajo)
    umbral = 0.62 * PASO_A
    for p in arriba:
        if all(math.dist(p, q) > umbral for q in sitios
               if abs(q[1] - p[1]) < PASO_B and abs(q[0] - p[0]) < PASO_B):
            sitios.append(p)

    celdas = voronoi(sitios)
    for _ in range(2):                      # la cera tibia se asienta, dos veces
        sitios = relajar(sitios, celdas, sigma=1.9 * PASO_A)
        celdas = voronoi(sitios)

    # ── dibujo ────────────────────────────────────────────────────────────────
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
           f'viewBox="0 0 {W} {H}">',
           f'<rect width="{W}" height="{H}" fill="{FONDO}"/>',
           '<g stroke-linejoin="round" stroke-linecap="round">']
    cuenta = {}
    raros = []
    rnd = random.Random(SEMILLA + 1)
    for p, poly in zip(sitios, celdas):
        n = len(poly)
        if n < 3:
            continue
        if not (-30 <= p[0] <= W + 30 and -30 <= p[1] <= ALTO_PANEL + 30):
            continue
        cuenta[n] = cuenta.get(n, 0) + 1
        # la cera no es plana: cada celda se seca con su propio tono
        t = rnd.random()
        if n == 6:
            fill = cera(t); sw = 1.6 + 0.9 * rnd.random()
        elif n == 5:
            fill, sw = PENTAGONO, 2.3; raros.append((p, n))
        elif n == 7:
            fill, sw = HEPTAGONO, 2.3; raros.append((p, n))
        else:
            fill, sw = RARO, 2.6; raros.append((p, n))
        d = " ".join(f"{x:.1f},{y:.1f}" for x, y in poly)
        out.append(f'<polygon points="{d}" fill="{fill}" '
                   f'stroke="{PARED}" stroke-width="{sw:.2f}"/>')
    out.append('</g>')

    # las parejas: una línea finísima une cada 5 con el 7 más cercano si se tocan
    pent = [p for p, n in raros if n == 5]
    hept = [p for p, n in raros if n == 7]
    out.append(f'<g stroke="{PARED}" stroke-opacity="0.55" stroke-width="1.1" '
               f'stroke-dasharray="3 4" fill="none">')
    for p in pent:
        if not hept:
            break
        q = min(hept, key=lambda h: math.dist(p, h))
        if math.dist(p, q) < 2.4 * PASO_A:
            out.append(f'<line x1="{p[0]:.1f}" y1="{p[1]:.1f}" '
                       f'x2="{q[0]:.1f}" y2="{q[1]:.1f}"/>')
    out.append('</g>')

    # cartela: banda limpia debajo del panal, para que el texto se lea
    out.append(f'<rect x="0" y="{ALTO_PANEL}" width="{W}" height="{H-ALTO_PANEL}" '
               f'fill="{FONDO}"/>')
    out.append(f'<line x1="0" y1="{ALTO_PANEL}" x2="{W}" y2="{ALTO_PANEL}" '
               f'stroke="{PARED}" stroke-width="2.5"/>')
    out.append(f'<text x="46" y="{ALTO_PANEL+52}" font-family="Georgia,serif" '
               f'font-size="34" letter-spacing="6" fill="{PARED}">LA COSTURA</text>')
    out.append(f'<text x="46" y="{ALTO_PANEL+82}" font-family="Georgia,serif" '
               f'font-size="17" fill="{PARED}" fill-opacity="0.72">'
               f'dos cuadrillas empiezan el panal por su lado, con paso y ángulo distintos, '
               f'y se encuentran a oscuras</text>')
    # leyenda a la derecha
    lx = W - 470
    for i, (col, txt) in enumerate(((PENTAGONO, "cinco lados"), (HEPTAGONO, "siete lados"))):
        y0 = ALTO_PANEL + 34 + i * 34
        out.append(f'<rect x="{lx}" y="{y0}" width="20" height="20" fill="{col}" '
                   f'stroke="{PARED}" stroke-width="1.6"/>')
        out.append(f'<text x="{lx+32}" y="{y0+16}" font-family="Georgia,serif" '
                   f'font-size="17" fill="{PARED}" fill-opacity="0.82">{txt}</text>')
    out.append(f'<text x="{lx+150}" y="{ALTO_PANEL+50}" font-family="Georgia,serif" '
               f'font-size="15" fill="{PARED}" fill-opacity="0.6">'
               f'no los dibujé: los dibuja el encuentro</text>')
    out.append(f'<text x="{lx+150}" y="{ALTO_PANEL+72}" font-family="Georgia,serif" '
               f'font-size="15" fill="{PARED}" fill-opacity="0.6">'
               f'{len([1 for _,n in raros if n==5])} y {len([1 for _,n in raros if n==7])} '
               f'entre {sum(cuenta.values())} celdas</text>')
    out.append('</svg>')

    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "panal_costura.svg")
    with open(ruta, "w") as f:
        f.write("\n".join(out))
    print("escrito:", ruta)
    print("celdas por número de lados:", dict(sorted(cuenta.items())))
    print("sitios:", len(sitios))


if __name__ == "__main__":
    main()
