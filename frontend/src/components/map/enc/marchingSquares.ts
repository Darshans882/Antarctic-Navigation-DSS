/**
 * Marching squares over the bathymetry grid, used to draw smooth vector
 * coastlines and iso-depth contours on the ENC chart.
 *
 * The grid is 0.1 degrees, so raw cell edges would render as a visible
 * staircase.  Marching squares interpolates the crossing point along each cell
 * edge, which turns the 0.1 degree mask into coastline that reads like a
 * printed chart.
 *
 * Emitted segments are chained into polylines by matching quantised endpoints,
 * so a contour draws as one continuous stroke rather than hundreds of dashes.
 */

type Pt = { x: number; y: number };

const KEY_SCALE = 1e4;

function keyOf(p: Pt): number {
  return Math.round(p.x * KEY_SCALE) * 1e7 + Math.round(p.y * KEY_SCALE);
}

/**
 * Extract iso-lines of `field` at `level` over the inclusive index window
 * [i0..i1] x [j0..j1].  `rowStride` and `index(i, j)` locate cells in `field`.
 * `toPoint(i, j, t)` maps a fractional grid coordinate to output space.
 *
 * `iStep` / `jStep` sample every n-th cell.  The bathymetry grid is 0.1 degrees,
 * which is far finer than the screen when zoomed out, so stepping keeps the
 * contour pass proportional to the number of visible pixels rather than to the
 * number of grid cells.
 */
export function marchingSquares(
  field: ArrayLike<number>,
  i0: number,
  i1: number,
  j0: number,
  j1: number,
  level: number,
  index: (i: number, j: number) => number,
  toPoint: (i: number, j: number, t: number) => Pt,
  iStep = 1,
  jStep = 1,
): Pt[][] {
  if (i1 <= i0 || j1 <= j0) return [];

  const di = Math.max(1, Math.round(iStep));
  const dj = Math.max(1, Math.round(jStep));

  const segs: [Pt, Pt][] = [];

  // Corner values and the four edge crossing helpers for one cell.
  const va = new Float64Array(4);
  const vb = new Float64Array(4);

  const lerpT = (p: number, q: number): number => {
    const d = q - p;
    if (d === 0) return 0.5;
    const t = (level - p) / d;
    return t < 0 ? 0 : t > 1 ? 1 : t;
  };

  for (let i = i0; i < i1; i += di) {
    for (let j = j0; j < j1; j += dj) {
      // a = (i,   j)   b = (i,   j+1)
      // d = (i+1, j)   c = (i+1, j+1)
      va[0] = field[index(i, j)];
      va[1] = field[index(i, j + 1)];
      vb[0] = field[index(i + 1, j)];
      vb[1] = field[index(i + 1, j + 1)];

      let code = 0;
      if (va[0] > level) code |= 1;
      if (va[1] > level) code |= 2;
      if (vb[1] > level) code |= 4;
      if (vb[0] > level) code |= 8;
      if (code === 0 || code === 15) continue;

      // Edge crossing points.  `top` runs along i at constant j, `right` along
      // j at constant i+1, `bottom` along i at constant j+1, `left` along j at
      // constant i.
      const top = () => toPoint(i, j, lerpT(va[0], va[1]));
      const right = () => toPoint(i + 1, j, lerpT(va[1], vb[1]));
      const bottom = () => toPoint(i + 1, j + 1, lerpT(vb[0], vb[1]));
      const left = () => toPoint(i, j + 1, lerpT(va[0], vb[0]));

      let p: Pt;
      let q: Pt;
      switch (code) {
        case 1:
        case 14:
          p = left(); q = top(); segs.push([p, q]); break;
        case 2:
        case 13:
          p = top(); q = right(); segs.push([p, q]); break;
        case 3:
        case 12:
          p = left(); q = right(); segs.push([p, q]); break;
        case 4:
        case 11:
          p = right(); q = bottom(); segs.push([p, q]); break;
        case 6:
        case 9:
          p = top(); q = bottom(); segs.push([p, q]); break;
        case 7:
        case 8:
          p = left(); q = bottom(); segs.push([p, q]); break;
        case 5:
          // Saddle: resolve with the cell-centre average so the two arcs join
          // consistently instead of producing a bow-tie.
          p = left(); q = top();
          if ((va[0] + va[1] + vb[0] + vb[1]) / 4 > level) {
            segs.push([p, q]);
            p = right(); q = bottom();
            segs.push([p, q]);
          } else {
            p = top(); q = right();
            segs.push([p, q]);
            p = left(); q = bottom();
            segs.push([p, q]);
          }
          break;
        case 10:
          p = left(); q = top();
          if ((va[0] + va[1] + vb[0] + vb[1]) / 4 > level) {
            p = right(); q = bottom();
            segs.push([p, q]);
            p = left(); q = top();
            segs.push([p, q]);
          } else {
            p = left(); q = bottom();
            segs.push([p, q]);
            p = top(); q = right();
            segs.push([p, q]);
          }
          break;
        default:
          break;
      }
    }
  }

  return chainSegments(segs);
}

/** Join loose segments into continuous polylines by endpoint matching. */
function chainSegments(segs: [Pt, Pt][]): Pt[][] {
  if (segs.length === 0) return [];

  const byStart = new Map<number, number[]>();
  const used = new Uint8Array(segs.length);

  for (let s = 0; s < segs.length; s++) {
    const k = keyOf(segs[s][0]);
    const list = byStart.get(k);
    if (list) list.push(s);
    else byStart.set(k, [s]);
  }

  const takeFrom = (from: Pt): number | null => {
    const list = byStart.get(keyOf(from));
    if (!list) return null;
    for (const s of list) {
      if (!used[s]) return s;
    }
    return null;
  };

  const lines: Pt[][] = [];
  for (let s = 0; s < segs.length; s++) {
    if (used[s]) continue;
    used[s] = 1;
    const line: Pt[] = [segs[s][0], segs[s][1]];

    // Extend forward, then backward, as long as a free segment continues.
    for (let dir = 0; dir < 2; dir++) {
      for (;;) {
        const end = dir === 0 ? line[line.length - 1] : line[0];
        const nxt = takeFrom(end);
        if (nxt === null) break;
        used[nxt] = 1;
        const [a, b] = segs[nxt];
        const far = keyOf(a) === keyOf(end) ? b : a;
        if (dir === 0) line.push(far);
        else line.unshift(far);
        if (line.length > 20000) break;
      }
    }
    lines.push(line);
  }

  return lines;
}
