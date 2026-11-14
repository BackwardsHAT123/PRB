/* gridmap.js - import points (e.g. vertical wells with a datapoint), grid them, optionally contour them,
   and show the result as a layer on the PRB map.  Core maths (GridCore) has no browser dependencies and is
   unit-tested under node (tools/test_gridcore.js).  The UI at the bottom only runs where Leaflet + `map` exist. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.GridCore = factory();
})(this, function () {
  'use strict';
  const MI = 1609.344;

  /* ---------- CSV ---------- */
  function parseCSV(text) {
    text = text.replace(/^﻿/, '');
    const rows = []; let row = [], f = '', q = false;
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (q) {
        if (c === '"') { if (text[i + 1] === '"') { f += '"'; i++; } else q = false; } else f += c;
      } else if (c === '"') q = true;
      else if (c === ',') { row.push(f); f = ''; }
      else if (c === '\n' || c === '\r') {
        if (c === '\r' && text[i + 1] === '\n') i++;
        row.push(f); f = ''; if (row.length > 1 || row[0] !== '') rows.push(row); row = [];
      } else f += c;
    }
    if (f !== '' || row.length) { row.push(f); rows.push(row); }
    if (!rows.length) return { headers: [], rows: [] };
    const headers = rows[0].map(h => h.trim());
    return { headers, rows: rows.slice(1).map(r => { const o = {}; headers.forEach((h, i) => o[h] = (r[i] || '').trim()); return o; }) };
  }
  const num = v => { if (v === '' || v == null) return NaN; const n = Number(String(v).replace(/,/g, '')); return isFinite(n) ? n : NaN; };
  function pick(headers, res) { for (const re of res) { const h = headers.find(x => re.test(x)); if (h) return h; } return ''; }
  function detectColumns(headers) {
    return {
      lat: pick(headers, [/^lat(itude)?$/i, /^shl[_ ]?lat/i, /lat/i, /^y$/i]),
      lon: pick(headers, [/^lon(g|gitude)?$/i, /^shl[_ ]?lon/i, /lon/i, /^x$/i]),
      fm: pick(headers, [/^botform$/i, /^formation$/i, /^fm$/i, /form/i]),
      label: pick(headers, [/^api/i, /well/i, /^name$/i, /^id$/i])
    };
  }
  function numericColumns(rows, headers, skip) {
    return headers.filter(h => !skip.includes(h) && rows.length &&
      rows.filter(r => !isNaN(num(r[h]))).length >= Math.max(3, 0.2 * rows.length));
  }

  /* ---------- projection (local equirectangular, metres) ---------- */
  function makeProj(lon0, lat0) {
    const kx = 111320 * Math.cos(lat0 * Math.PI / 180), ky = 110950;
    return { kx, ky, fwd: (lon, lat) => [(lon - lon0) * kx, (lat - lat0) * ky], inv: (x, y) => [lon0 + x / kx, lat0 + y / ky] };
  }

  /* ---------- grid definition ---------- */
  /* ext = {w,s,e,n} in degrees.  Cells are aligned to multiples of the cell size from the projection origin. */
  function makeGrid(ext, cellM, proj, maxCells) {
    const a = proj.fwd(ext.w, ext.s), b = proj.fwd(ext.e, ext.n);
    const x0 = Math.floor(a[0] / cellM) * cellM, y0 = Math.floor(a[1] / cellM) * cellM;
    const nx = Math.max(1, Math.ceil((b[0] - x0) / cellM)), ny = Math.max(1, Math.ceil((b[1] - y0) / cellM));
    if (nx * ny > (maxCells || 1500000)) throw new Error('Grid would be ' + nx + ' x ' + ny + ' = ' + (nx * ny).toLocaleString() + ' cells; use a larger cell or smaller extent');
    return { x0, y0, dx: cellM, nx, ny, z: new Float64Array(nx * ny).fill(NaN) };
  }
  const cx = (g, i) => g.x0 + (i + 0.5) * g.dx, cy = (g, j) => g.y0 + (j + 0.5) * g.dx;

  /* ---------- interpolators.  pts = [{x,y,z}] ---------- */
  function dedupe(pts) {
    const m = new Map();
    pts.forEach(p => { const k = Math.round(p.x) + ',' + Math.round(p.y); const e = m.get(k); if (e) { e.s += p.z; e.n++; } else m.set(k, { x: p.x, y: p.y, s: p.z, n: 1 }); });
    return [...m.values()].map(e => ({ x: e.x, y: e.y, z: e.s / e.n }));
  }
  /* decluster: average the points that fall in the same grid cell (cells aligned to multiples of cellM from the projection origin, same as the grid) */
  function declust(pts, cellM) {
    const m = new Map();
    pts.forEach(p => { const k = Math.floor(p.x / cellM) + ',' + Math.floor(p.y / cellM); const e = m.get(k); if (e) { e.x += p.x; e.y += p.y; e.z += p.z; e.n++; } else m.set(k, { x: p.x, y: p.y, z: p.z, n: 1 }); });
    return [...m.values()].map(e => ({ x: e.x / e.n, y: e.y / e.n, z: e.z / e.n }));
  }
  function nearestDist(pts, x, y) { let d = Infinity; for (const p of pts) { const h = Math.hypot(p.x - x, p.y - y); if (h < d) d = h; } return d; }

  /* inverse distance weighting; points beyond `maxDist` of the node are ignored, nodes with none are blank */
  function idw(g, pts, o) {
    const pw = o.power || 2, R = o.maxDist || Infinity, R2 = R * R, k = o.neighbors || 0;
    const cell = isFinite(R) ? R : Math.max(g.nx, g.ny) * g.dx;
    const bk = new Map(), key = (i, j) => i + ',' + j;
    pts.forEach(p => { const kk = key(Math.floor(p.x / cell), Math.floor(p.y / cell)); (bk.get(kk) || bk.set(kk, []).get(kk)).push(p); });
    for (let j = 0; j < g.ny; j++) for (let i = 0; i < g.nx; i++) {
      const x = cx(g, i), y = cy(g, j), bi = Math.floor(x / cell), bj = Math.floor(y / cell);
      const cand = [];
      for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) {
        const l = bk.get(key(bi + a, bj + b)); if (!l) continue;
        for (const p of l) { const d2 = (p.x - x) ** 2 + (p.y - y) ** 2; if (d2 <= R2) cand.push([d2, p.z]); }
      }
      if (!cand.length) continue;
      if (k && cand.length > k) { cand.sort((u, v) => u[0] - v[0]); cand.length = k; }
      let sw = 0, sz = 0, hit = NaN;
      for (const [d2, z] of cand) { if (d2 < 1) { hit = z; break; } const w = 1 / Math.pow(d2, pw / 2); sw += w; sz += w * z; }
      g.z[j * g.nx + i] = isNaN(hit) ? sz / sw : hit;
    }
  }

  /* thin-plate spline (smooth minimum-curvature surface).  smooth>=0 relaxes the fit through the points.
     Works in km so the numbers stay well conditioned. */
  function tps(g, pts, o) {
    const n = pts.length; if (n < 3) throw new Error('Spline needs at least 3 points');
    if (n > 1200) throw new Error('Spline limited to 1200 points (have ' + n + '); use IDW or filter formations');
    const S = 1000, lam = (o.smooth || 0), m = n + 3, A = new Float64Array(m * m), b = new Float64Array(m);
    const ker = r2 => r2 > 0 ? 0.5 * r2 * Math.log(r2) : 0;
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) A[i * m + j] = ker(((pts[i].x - pts[j].x) / S) ** 2 + ((pts[i].y - pts[j].y) / S) ** 2);
      A[i * m + i] += lam; A[i * m + n] = A[n * m + i] = 1;
      A[i * m + n + 1] = A[(n + 1) * m + i] = pts[i].x / S; A[i * m + n + 2] = A[(n + 2) * m + i] = pts[i].y / S; b[i] = pts[i].z;
    }
    for (let c = 0; c < m; c++) { /* gaussian elimination, partial pivot */
      let p = c, best = Math.abs(A[c * m + c]);
      for (let r = c + 1; r < m; r++) { const v = Math.abs(A[r * m + c]); if (v > best) { best = v; p = r; } }
      if (best < 1e-12) throw new Error('Spline is singular (collinear or duplicate points)');
      if (p !== c) { for (let k = 0; k < m; k++) { const t = A[c * m + k]; A[c * m + k] = A[p * m + k]; A[p * m + k] = t; } const t = b[c]; b[c] = b[p]; b[p] = t; }
      for (let r = c + 1; r < m; r++) {
        const f = A[r * m + c] / A[c * m + c]; if (!f) continue;
        for (let k = c; k < m; k++) A[r * m + k] -= f * A[c * m + k]; b[r] -= f * b[c];
      }
    }
    const w = new Float64Array(m);
    for (let r = m - 1; r >= 0; r--) { let s = b[r]; for (let k = r + 1; k < m; k++) s -= A[r * m + k] * w[k]; w[r] = s / A[r * m + r]; }
    for (let j = 0; j < g.ny; j++) for (let i = 0; i < g.nx; i++) {
      const x = cx(g, i) / S, y = cy(g, j) / S; let z = w[n] + w[n + 1] * x + w[n + 2] * y;
      for (let k = 0; k < n; k++) z += w[k] * ker((x - pts[k].x / S) ** 2 + (y - pts[k].y / S) ** 2);
      g.z[j * g.nx + i] = z;
    }
  }

  /* full pipeline: interpolate, clamp, mask by distance to data */
  function gridPoints(g, pts, o) {
    const nraw = pts.length; pts = dedupe(pts); if (o.decluster && o.cellM > 0) pts = declust(pts, o.cellM); if (!pts.length) throw new Error('No points to grid');
    const zs = pts.map(p => p.z), zmin = Math.min(...zs), zmax = Math.max(...zs);
    if (o.method === 'spline' && g.nx * g.ny * pts.length > 6e8) throw new Error('Spline would take too long here (' + (g.nx * g.ny).toLocaleString() + ' cells x ' + pts.length + ' points); use IDW, a larger cell, or a smaller extent');
    if (o.method === 'spline') tps(g, pts, o); else idw(g, pts, { power: o.power, neighbors: o.neighbors, maxDist: o.maxDist });
    const R = o.maxDist || Infinity, pad = (zmax - zmin) * (o.clampPad == null ? 0.1 : o.clampPad);
    for (let j = 0; j < g.ny; j++) for (let i = 0; i < g.nx; i++) {
      const k = j * g.nx + i; if (isNaN(g.z[k])) continue;
      if (o.method === 'spline' && isFinite(R) && nearestDist(pts, cx(g, i), cy(g, j)) > R) { g.z[k] = NaN; continue; }   // IDW already leaves cells with no point within R blank
      if (o.clamp !== false) g.z[k] = Math.min(zmax + pad, Math.max(zmin - pad, g.z[k]));
    }
    return { npts: pts.length, nraw, zmin, zmax };
  }
  function gridStats(g) { let mn = Infinity, mx = -Infinity, n = 0; for (const v of g.z) if (!isNaN(v)) { n++; if (v < mn) mn = v; if (v > mx) mx = v; } return { min: mn, max: mx, n }; }
  function sampleGrid(g, x, y) { /* bilinear between cell centres; nearest cell at the edges; NaN outside */
    const fi = (x - g.x0) / g.dx - 0.5, fj = (y - g.y0) / g.dx - 0.5, i = Math.floor(fi), j = Math.floor(fj);
    if (i < 0 || j < 0 || i + 1 >= g.nx || j + 1 >= g.ny) {
      const ii = Math.round(fi), jj = Math.round(fj);
      return (ii >= 0 && jj >= 0 && ii < g.nx && jj < g.ny && Math.abs(fi - ii) <= 0.5 && Math.abs(fj - jj) <= 0.5) ? g.z[jj * g.nx + ii] : NaN;
    }
    const tx = fi - i, ty = fj - j, a = g.z[j * g.nx + i], b = g.z[j * g.nx + i + 1], c = g.z[(j + 1) * g.nx + i], d = g.z[(j + 1) * g.nx + i + 1];
    return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty;
  }

  /* ---------- contours (marching squares on cell centres, gaps skipped) ---------- */
  function niceStep(range, target) {
    const raw = range / (target || 10); if (!(raw > 0)) return 1;
    const p = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / p;
    return (f < 1.5 ? 1 : f < 3.5 ? 2 : f < 7.5 ? 5 : 10) * p;
  }
  function contourLevels(min, max, step) { const out = []; for (let v = Math.ceil(min / step) * step; v <= max + step * 1e-9; v += step) out.push(+v.toFixed(10)); return out; }
  function contours(g, levels) {
    const out = [];
    for (const L of levels) {
      const segs = [];
      for (let j = 0; j < g.ny - 1; j++) for (let i = 0; i < g.nx - 1; i++) {
        const a = g.z[j * g.nx + i], b = g.z[j * g.nx + i + 1], c = g.z[(j + 1) * g.nx + i + 1], d = g.z[(j + 1) * g.nx + i];
        if (isNaN(a + b + c + d)) continue;
        const code = (a >= L ? 1 : 0) | (b >= L ? 2 : 0) | (c >= L ? 4 : 0) | (d >= L ? 8 : 0);
        if (code === 0 || code === 15) continue;
        const x0 = cx(g, i), x1 = cx(g, i + 1), y0 = cy(g, j), y1 = cy(g, j + 1), t = (u, v) => (L - u) / (v - u);
        const e = { /* edge crossings: B bottom(a-b), R right(b-c), T top(d-c), Lf left(a-d) */
          B: () => [x0 + t(a, b) * g.dx, y0], R: () => [x1, y0 + t(b, c) * g.dx], T: () => [x0 + t(d, c) * g.dx, y1], Lf: () => [x0, y0 + t(a, d) * g.dx]
        };
        const avg = (a + b + c + d) / 4, S = (p, q) => segs.push([...e[p](), ...e[q]()]);
        switch (code) {
          case 1: case 14: S('Lf', 'B'); break; case 2: case 13: S('B', 'R'); break;
          case 3: case 12: S('Lf', 'R'); break; case 4: case 11: S('R', 'T'); break;
          case 6: case 9: S('B', 'T'); break; case 7: case 8: S('Lf', 'T'); break;
          case 5: if (avg >= L) { S('Lf', 'T'); S('B', 'R'); } else { S('Lf', 'B'); S('R', 'T'); } break;
          case 10: if (avg >= L) { S('Lf', 'B'); S('R', 'T'); } else { S('Lf', 'T'); S('B', 'R'); } break;
        }
      }
      if (segs.length) out.push({ level: L, segs });
    }
    return out;
  }

  /* join marching-squares segments into polylines (endpoints matched to the nearest metre) */
  function chainSegments(segs) {
    const key = (x, y) => Math.round(x) + ',' + Math.round(y), ends = new Map();
    segs.forEach((s, i) => { [key(s[0], s[1]), key(s[2], s[3])].forEach(k => { const l = ends.get(k); l ? l.push(i) : ends.set(k, [i]); }); });
    const used = new Uint8Array(segs.length), out = [];
    const nextFrom = (k) => { const l = ends.get(k); if (l) for (const i of l) if (!used[i]) return i; return -1; };
    for (let i = 0; i < segs.length; i++) {
      if (used[i]) continue; used[i] = 1;
      const chain = [[segs[i][0], segs[i][1]], [segs[i][2], segs[i][3]]];
      for (let dir = 0; dir < 2; dir++) {
        for (;;) {
          const end = dir ? chain[0] : chain[chain.length - 1], j = nextFrom(key(end[0], end[1]));
          if (j < 0) break; used[j] = 1; const s = segs[j];
          const far = key(s[0], s[1]) === key(end[0], end[1]) ? [s[2], s[3]] : [s[0], s[1]];
          dir ? chain.unshift(far) : chain.push(far);
        }
      }
      out.push(chain);
    }
    return out;
  }
  /* label positions along chains: {x,y,angle(rad, along the line, upright)}; one near the middle of short lines, more on long ones */
  function labelSpots(chains, spacing, minLen) {
    const spots = [];
    chains.forEach(ch => {
      const cum = [0]; for (let i = 1; i < ch.length; i++) cum.push(cum[i - 1] + Math.hypot(ch[i][0] - ch[i - 1][0], ch[i][1] - ch[i - 1][1]));
      const len = cum[cum.length - 1]; if (len < minLen) return;
      const n = Math.max(1, Math.floor(len / spacing));
      for (let k = 0; k < n; k++) {
        const at = (k + 0.5) * len / n; let i = 1; while (i < cum.length - 1 && cum[i] < at) i++;
        const a = ch[Math.max(0, i - 2)], b = ch[Math.min(ch.length - 1, i + 1)], f = (at - cum[i - 1]) / ((cum[i] - cum[i - 1]) || 1);
        let ang = Math.atan2(b[1] - a[1], b[0] - a[0]); if (ang > Math.PI / 2) ang -= Math.PI; if (ang < -Math.PI / 2) ang += Math.PI;
        spots.push({ x: ch[i - 1][0] + (ch[i][0] - ch[i - 1][0]) * f, y: ch[i - 1][1] + (ch[i][1] - ch[i - 1][1]) * f, angle: ang });
      }
    });
    return spots;
  }

  /* ---------- colour maps ---------- */
  const STOPS = {
    viridis: ['#440154', '#472d7b', '#3b528b', '#2c728e', '#21908d', '#27ad81', '#5cc863', '#aadc32', '#fde725'],
    plasma: ['#0d0887', '#5402a3', '#8b0aa5', '#b83289', '#db5c68', '#f48849', '#febd2a', '#f0f921'],
    inferno: ['#000004', '#2a0c4b', '#6a176e', '#a52c60', '#dd513a', '#f98e09', '#f3d746', '#fcffa4'],
    turbo: ['#30123b', '#4662d7', '#36aaf9', '#1ae4b6', '#72fe5e', '#c7ef34', '#faba39', '#f66b19', '#ca2a04', '#7a0403'],
    'blue-red': ['#2166ac', '#67a9cf', '#d1e5f0', '#f7f7f7', '#fddbc7', '#ef8a62', '#b2182b'],
    'red-yellow-blue': ['#a50026', '#f46d43', '#fee090', '#ffffbf', '#abd9e9', '#4575b4', '#313695'],
    'green-brown': ['#01665e', '#5ab4ac', '#c7eae5', '#f5f5f5', '#f6e8c3', '#d8b365', '#8c510a'],
    gray: ['#f5f5f5', '#bdbdbd', '#737373', '#252525']
  };
  const hex = h => [1, 3, 5].map(i => parseInt(h.substr(i, 2), 16));
  function colormap(name, reverse, steps) {
    const st = (STOPS[name] || STOPS.viridis).map(hex);
    return t => {
      if (reverse) t = 1 - t;
      if (steps > 1) t = Math.min(steps - 1, Math.floor(Math.min(0.999999, Math.max(0, t)) * steps)) / (steps - 1);
      t = Math.min(1, Math.max(0, t)); const p = t * (st.length - 1), i = Math.min(st.length - 2, Math.floor(p)), f = p - i;
      return st[i].map((v, k) => Math.round(v + (st[i + 1][k] - v) * f));
    };
  }

  /* ---- well comparison helpers (used by the compare-two-wells plot in index.html) ---- */
  /* Colour rule: same operator or same formation -> colour by well; otherwise colour by formation. */
  function cmpMode(a, b) { return (a.oc === b.oc || a.r === b.r) ? 'well' : 'formation'; }
  function cmpWhy(a, b) { return a.r === b.r ? 'same formation' : a.oc === b.oc ? 'same operator' : 'different formations'; }
  function cumSeries(arr) { let t = 0; return arr.map(v => (t += (+v || 0))); }
  /* month offset of each series on the x axis: 'age' = months since first production (both start at 0),
     'date' = calendar months (the later well starts at its real offset). s is 'YYYY-MM'. */
  function cmpOffsetsN(starts, xmode) {
    const mi = s => (+s.slice(0, 4)) * 12 + (+s.slice(5) - 1), m = starts.map(mi);
    if (xmode !== 'date') return m.map(() => 0);
    const lo = Math.min(...m); return m.map(v => v - lo);
  }
  function cmpOffsets(sa, sb, xmode) { return cmpOffsetsN([sa, sb], xmode); }
  /* x-axis length in months for the compare chart: the oldest producer's extent, capped (age axis only) */
  function cmpExtent(lens, xmode, cap) { const m = Math.max(...lens); return xmode === 'age' ? Math.min(cap, m) : m; }
  /* Bottom-hole temperature correction after Harrison et al. (1983, Oklahoma Geological Survey SP 83-1; AAPG-type correction):
     dT(degC) = -16.51213476 + 0.01826842109 Z - 2.344936959e-6 Z^2, Z = depth in metres, added to the measured BHT.
     Takes and returns degF, depth in feet. Depth-only (it does not use time since circulation); NaN without a usable depth. */
  function harrisonBHT(tF, depthFt) {
    if (!(depthFt > 0) || isNaN(tF)) return NaN;
    const z = depthFt * 0.3048; return tF + 1.8 * (-16.51213476 + 0.01826842109 * z - 2.344936959e-6 * z * z);
  }
  /* great-circle distance in statute miles between two lon/lat points */
  function milesBetween(lon1, lat1, lon2, lat2) {
    const r = Math.PI / 180, dLat = (lat2 - lat1) * r, dLon = (lon2 - lon1) * r;
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin(dLon / 2) ** 2;
    return 3958.8 * 2 * Math.asin(Math.min(1, Math.sqrt(h)));
  }
  return { cmpMode, cmpWhy, cumSeries, cmpOffsets, cmpOffsetsN, cmpExtent, harrisonBHT, milesBetween, MI, parseCSV, num, detectColumns, numericColumns, makeProj, makeGrid, cx, cy, dedupe, declust, idw, tps, gridPoints, gridStats, sampleGrid,
    niceStep, contourLevels, contours, chainSegments, labelSpots, colormap, PALETTES: Object.keys(STOPS) };
});

/* ====================================================================== UI ====================================================================== */
(function () {
  if (typeof L === 'undefined' || typeof map === 'undefined' || typeof document === 'undefined') return;
  const C = window.GridCore, KEY = 'prb_gridmap_v1';
  const css = document.createElement('style');
  css.textContent = `
#gridbtn{position:absolute;z-index:1000;left:10px;top:256px;width:34px;height:34px;padding:0;border:1px solid var(--bstrong);border-radius:50%;background:var(--panel);color:var(--fg);font:inherit;font-size:10px;font-weight:700;line-height:1;cursor:pointer}
#gridbtn.on{background:var(--accent);color:#fff}
#gridpop{position:absolute;z-index:1000;left:52px;top:256px;width:268px;max-height:calc(100% - 276px);overflow:auto;padding:8px 10px;background:var(--panel);border:1px solid var(--line);border-radius:8px;box-shadow:0 2px 10px #0003;font-size:12px}
#gridpop[hidden]{display:none}
#gridpop h4{margin:8px 0 2px;font-size:12px;border-top:1px solid var(--line);padding-top:6px}#gridpop h4:first-child{border:0;margin-top:0;padding:0}
#gridpop label{display:block;margin:3px 0 0}#gridpop label.ck{display:flex;gap:5px;align-items:center}
#gridpop select,#gridpop input[type=text],#gridpop input[type=number]{width:100%;box-sizing:border-box;padding:3px;background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:4px;font:inherit}
#gridpop .row2{display:flex;gap:6px}#gridpop .row2 label{flex:1 1 0;min-width:0}
#gridpop .fmlist{max-height:92px;overflow:auto;border:1px solid var(--line);border-radius:4px;padding:2px 4px;background:var(--bg)}
#gridpop .fmlist label{margin:0}#gridpop .msg{margin:4px 0 0;opacity:.75}#gridpop .err{color:#c0392b;opacity:1}
.gridclab.b{font-weight:800;font-size:12px}.gridclab{background:none;border:0;font:600 11px/1 system-ui,sans-serif;color:var(--fg);white-space:nowrap;text-align:center;text-shadow:0 0 3px var(--panel),0 0 3px var(--panel),0 0 2px var(--panel);pointer-events:none}
#gridlegend{position:absolute;z-index:900;left:50%;transform:translateX(-50%);top:10px;padding:6px 8px;background:var(--panel);color:var(--fg);border:1px solid var(--line);border-radius:6px;font-size:11px;box-shadow:0 1px 6px #0003}
#gridlegend[hidden]{display:none}#gridlegend canvas{display:block;width:200px;height:12px}#gridlegend .tk{position:relative;height:14px;margin-top:2px}
#gridlegend .tk span{position:absolute;transform:translateX(-50%);white-space:nowrap}
@media (max-width:700px){#gridbtn{top:auto;bottom:244px}#gridpop{top:auto;bottom:244px;max-height:55%}#gridlegend{top:auto;bottom:130px;left:10px;transform:none}}`;
  document.head.appendChild(css);

  const host = map.getContainer().parentNode;
  const btn = document.createElement('button'); btn.id = 'gridbtn'; btn.type = 'button'; btn.textContent = 'GRID'; btn.title = btn.ariaLabel = 'Grid and contour imported points';
  const pop = document.createElement('div'); pop.id = 'gridpop'; pop.hidden = true;
  const leg = document.createElement('div'); leg.id = 'gridlegend'; leg.hidden = true;
  host.append(btn, pop, leg);
  pop.innerHTML = `
<label class="ck"><input type="checkbox" id="g_vert" checked> Vertical wells with logs <span id="g_vn"></span></label>
<h4>Data</h4>
<input type="file" id="g_file" accept=".csv,text/csv">
<details id="g_bh"><summary>Borehole temperatures (AASG/SMU, via NBMG)</summary>
<div class="row2"><label>Depth min (ft) <input type="number" id="bh_dmin" value="4000" min="0" step="500"></label><label>Depth max (ft) <input type="number" id="bh_dmax" placeholder="none" min="0" step="500"></label></div>
<div class="row2"><label>Surface temp (&deg;F) <input type="number" id="bh_ts" value="47" step="1"></label><label class="ck"><input type="checkbox" id="bh_qc" checked> Drop gradients outside 0.5-4</label></div>
<button type="button" class="pbtn" id="bh_load">Load and grid these points</button><div class="msg" id="bh_msg">Pulls the public state borehole-temperature points for the basin (reads the map service, nothing is stored on a server). Temp = max recorded if reported, else the measured value; Gradient_F_100ft = (Temp - surface) / depth x 100.</div></details>
<div class="msg" id="g_info">Import a CSV with latitude / longitude and one or more numeric columns.</div>
<label>Variable to grid <select id="g_var" class="calc"></select></label>
<details id="g_bhd"><summary>Bottom-hole temperature correction <span id="g_bhn"></span></summary>
<label class="ck"><input type="checkbox" id="g_bht" class="calc"> Correct the variable as a raw bottom-hole temperature (&deg;F)</label>
<div class="row2"><label>Depth col (ft) <select id="g_bhtd" class="calc"></select></label><label>If blank, use <select id="g_bhtd2" class="calc"></select></label></div>
<div class="msg">Harrison et al. (1983) depth correction (Oklahoma DST calibration), added to the measured temperature. It ignores time since circulation, so treat it as a first-order correction. Wells with no depth in either column are left out.</div>
</details>
<div class="row2"><label>Lat col <select id="g_lat" class="calc"></select></label><label>Lon col <select id="g_lon" class="calc"></select></label></div>
<details id="g_fmd"><summary>Filter by formation <span id="g_fmn"></span></summary>
<label>Formation column <select id="g_fmc" class="calc"></select></label>
<div class="fmlist" id="g_fms"></div>
<div class="row2"><button type="button" class="pbtn" id="g_all">All</button><button type="button" class="pbtn" id="g_none">None</button></div>
</details>
<h4>Grid</h4>
<label>Method <select id="g_meth" class="calc"><option value="idw">IDW (stays within data, masked)</option><option value="spline">Spline (smooth, min. curvature)</option></select></label>
<div class="row2"><label>Cell (ft) <input type="number" id="g_cell" class="calc" value="1000" min="100" step="100"></label>
<label>Mask beyond (mi) <input type="number" id="g_mask" class="calc" value="5" min="0" step="0.5"></label></div>
<label class="ck"><input type="checkbox" id="g_dec" class="calc" checked> Average points within each cell first (declusters pads and infill)</label>
<div class="row2"><label>IDW nearest N (0 = all) <input type="number" id="g_nn" class="calc" value="0" min="0" step="1"></label></div>
<div class="row2"><label>IDW power <input type="number" id="g_pow" class="calc" value="2" min="0.5" max="6" step="0.5"></label>
<label>Spline smooth <input type="number" id="g_smooth" class="calc" value="0" min="0" step="0.1"></label></div>
<label>Extent <select id="g_ext" class="calc"><option value="auto">Auto (data + 2 mi)</option><option value="view">Current map view</option><option value="custom">Custom</option></select></label>
<div class="row2"><label>West <input type="text" id="g_w" class="calc"></label><label>East <input type="text" id="g_e" class="calc"></label></div>
<div class="row2"><label>South <input type="text" id="g_s" class="calc"></label><label>North <input type="text" id="g_n" class="calc"></label></div>
<div class="row2"><button type="button" class="pbtn" id="g_setview">Copy view to custom</button></div>
<h4>Display</h4>
<div class="row2"><label>Colors <select id="g_cmap" class="disp"></select></label><label>Steps (0=smooth) <input type="number" id="g_steps" class="disp" value="0" min="0" max="20"></label></div>
<div class="row2"><label>Min <input type="text" id="g_min" class="disp" placeholder="auto"></label><label>Max <input type="text" id="g_max" class="disp" placeholder="auto"></label></div>
<label class="ck"><input type="checkbox" id="g_rev" class="disp"> Reverse colors</label>
<label>Opacity <input type="range" id="g_op" class="disp" min="0.1" max="1" step="0.05" value="0.7"></label>
<label class="ck"><input type="checkbox" id="g_fill" class="disp"> Show filled grid</label>
<label class="ck"><input type="checkbox" id="g_cont" class="disp"> Contours</label>
<label>Contour interval <input type="text" id="g_cint" class="disp" placeholder="auto"></label>
<label class="ck"><input type="checkbox" id="g_clab" class="disp" checked> Contour labels</label>
<label>Bold every Nth line (0 = off) <input type="number" id="g_cbold" class="disp" value="5" min="0" max="50" step="1"></label>
<label class="ck"><input type="checkbox" id="g_pts" class="disp"> Show points</label>
<label class="ck"><input type="checkbox" id="g_wlab" class="disp" checked> Show well values (when grid shown, zoom 10+)</label>
<label class="ck"><input type="checkbox" id="g_box" class="disp"> Show extent box</label>
<div class="msg" id="g_msg"></div>
<div class="row2"><button type="button" class="pbtn" id="g_go">Update</button><button type="button" class="pbtn" id="g_exp">Export grid CSV</button><button type="button" class="pbtn" id="g_clear">Clear</button></div>`;
  const $ = id => pop.querySelector('#' + id);
  C.PALETTES.forEach(p => $('g_cmap').add(new Option(p, p)));
  ['click', 'dblclick', 'mousedown', 'wheel', 'touchstart'].forEach(ev => { L.DomEvent.on(pop, ev, L.DomEvent.stopPropagation); L.DomEvent.on(btn, ev, L.DomEvent.stopPropagation); });
  btn.onclick = () => { pop.hidden = !pop.hidden; btn.classList.toggle('on', !pop.hidden); };

  const S = { data: null, grid: null, proj: null, fms: new Set(), range: null, pts: [] };
  map.createPane('gridpane').style.zIndex = 345;
  map.getPane('gridpane').style.pointerEvents = 'none';
  /* Everything interactive below is drawn in the map's own canvas renderer (overlay pane), so clicks on the horizontal wells still reach them */
  const cv = document.createElement('canvas'); cv.style.position = 'absolute'; cv.style.left = cv.style.top = '0'; map.getPane('gridpane').appendChild(cv);
  const contourGrp = L.layerGroup().addTo(map), ptGrp = L.layerGroup().addTo(map); let boxLayer = null;

  function msg(t, err) { const m = $('g_msg'); m.textContent = t || ''; m.className = 'msg' + (err ? ' err' : ''); }
  function fillSelect(sel, opts, val, blank) { sel.innerHTML = ''; if (blank) sel.add(new Option('(none)', '')); opts.forEach(o => sel.add(new Option(o, o))); if (val != null && [...sel.options].some(o => o.value === val)) sel.value = val; }

  /* well locations the map already knows, by API: the vertical-wells layer plus the horizontals in D */
  let locPromise = null;
  function wellLocations() {
    if (!locPromise) locPromise = fetch('data/vertical_wells.json').then(r => r.json()).catch(() => []).then(list => {
      const m = new Map();
      if (typeof D !== 'undefined') D.forEach(w => { if (w.a && w.shl) m.set(w.a, { lon: w.shl[0], lat: w.shl[1], f: w.r || '' }); });
      list.forEach(w => m.set(w.a, { lon: w.ll[0], lat: w.ll[1], f: w.f || '' }));
      return m;
    });
    return locPromise;
  }
  function loadText(text, name) {
    const d = C.parseCSV(text); if (!d.rows.length) { msg('No rows found in that file', true); return; }
    const dc = C.detectColumns(d.headers), apiCol = d.headers.find(h => /^api/i.test(h));
    const hasXY = dc.lat && dc.lon && d.rows.some(r => !isNaN(C.num(r[dc.lat])) && !isNaN(C.num(r[dc.lon])));
    if (hasXY || !apiCol) return finishLoad(d, dc, name, text, '');
    msg('No lat/lon columns: matching wells by ' + apiCol + ' to the wells on the map...');
    wellLocations().then(m => {
      let hit = 0; const addFm = !dc.fm;
      d.rows.forEach(r => { const w = m.get(r[apiCol]); r.Lat = w ? String(w.lat) : ''; r.Lon = w ? String(w.lon) : ''; if (addFm) r.Formation = w ? w.f : ''; if (w) hit++; });
      d.headers = d.headers.concat(['Lat', 'Lon']).concat(addFm ? ['Formation'] : []);
      dc.lat = 'Lat'; dc.lon = 'Lon'; if (addFm) dc.fm = 'Formation';
      finishLoad(d, dc, name, text, hit + ' of ' + d.rows.length + ' rows matched to a well on the map by API');
    });
  }
  function finishLoad(d, dc, name, text, note) {
    S.data = d; S.name = name;
    fillSelect($('g_lat'), d.headers, dc.lat); fillSelect($('g_lon'), d.headers, dc.lon); fillSelect($('g_fmc'), d.headers, dc.fm, true);
    S.label = dc.label; refreshVars(); refreshFms(true);
    $('g_info').textContent = name + ': ' + d.rows.length + ' rows' + (note ? ' (' + note + ')' : '');
    try { localStorage.setItem(KEY, JSON.stringify({ text, name })); } catch (e) { }
    rebuild();
  }
  function refreshVars() {
    const skip = [$('g_lat').value, $('g_lon').value, $('g_fmc').value], keep = $('g_var').value;
    const nc = C.numericColumns(S.data.rows, S.data.headers, skip.concat(S.data.headers.filter(h => /name|^api|^id$|log_?id/i.test(h))));
    const pref = nc.find(h => /temp/i.test(h)) || nc[0];
    fillSelect($('g_var'), nc, nc.includes(keep) ? keep : pref);
    const k1 = $('g_bhtd').value, k2 = $('g_bhtd2').value;
    fillSelect($('g_bhtd'), nc, nc.includes(k1) ? k1 : (nc.find(h => /bottom_?logged|bli/i.test(h)) || nc.find(h => /td/i.test(h)) || nc[0]));
    fillSelect($('g_bhtd2'), nc, nc.includes(k2) ? k2 : (nc.find(h => /state_?td|^td|depth/i.test(h)) || nc[0]));
  }
  function refreshFms(all) {
    const fc = $('g_fmc').value, box = $('g_fms'), counts = new Map();
    S.data.rows.forEach(r => { const f = fc ? (r[fc] || '(blank)') : ''; counts.set(f, (counts.get(f) || 0) + 1); });
    if (all) S.fms = new Set(counts.keys());
    box.innerHTML = ''; const badge = () => { $('g_fmn').textContent = fc && S.fms.size < counts.size ? '(' + S.fms.size + ' of ' + counts.size + ')' : ''; }; badge();
    if (!fc) { box.textContent = 'No formation column'; return; }
    [...counts.entries()].sort((a, b) => b[1] - a[1]).forEach(([f, n]) => {
      const l = document.createElement('label'); l.className = 'ck';
      const c = document.createElement('input'); c.type = 'checkbox'; c.checked = S.fms.has(f);
      c.onchange = () => { c.checked ? S.fms.add(f) : S.fms.delete(f); badge(); rebuild(); };
      l.append(c, document.createTextNode(f + ' (' + n + ')')); box.appendChild(l);
    });
  }
  function currentPoints() {
    const v = $('g_var').value, la = $('g_lat').value, lo = $('g_lon').value, fc = $('g_fmc').value, out = [], bht = $('g_bht').checked; let nodepth = 0;
    S.data.rows.forEach(r => {
      const lat = C.num(r[la]), lon = C.num(r[lo]); let z = C.num(r[v]);
      if (isNaN(lat) || isNaN(lon) || isNaN(z) || Math.abs(lat) > 90 || Math.abs(lon) > 180) return;
      const f = fc ? (r[fc] || '(blank)') : ''; if (fc && !S.fms.has(f)) return;
      const raw = z;
      if (bht) { let dp = C.num(r[$('g_bhtd').value]); if (!(dp > 0)) dp = C.num(r[$('g_bhtd2').value]); z = C.harrisonBHT(z, dp); if (isNaN(z)) { nodepth++; return; } }
      out.push({ lat, lon, z, raw, f, id: r[S.label] || '', row: r });
    });
    S.nodepth = nodepth; $('g_bhn').textContent = bht ? '(on' + (nodepth ? ', ' + nodepth + ' without depth' : '') + ')' : '';
    return out;
  }
  function extent(pts) {
    const m = $('g_ext').value;
    if (m === 'view') { const b = map.getBounds(); return { w: b.getWest(), s: b.getSouth(), e: b.getEast(), n: b.getNorth() }; }
    if (m === 'custom') {
      const e = { w: +$('g_w').value, e: +$('g_e').value, s: +$('g_s').value, n: +$('g_n').value };
      if ($('g_w').value === '' || ![e.w, e.e, e.s, e.n].every(isFinite) || e.w >= e.e || e.s >= e.n) throw new Error('Enter West < East and South < North (decimal degrees)');
      return e;
    }
    const lons = pts.map(p => p.lon), lats = pts.map(p => p.lat), pr = S.proj, padM = 2 * C.MI;
    return { w: Math.min(...lons) - padM / pr.kx, e: Math.max(...lons) + padM / pr.kx, s: Math.min(...lats) - padM / pr.ky, n: Math.max(...lats) + padM / pr.ky };
  }

  function rebuild() {
    if (!S.data) return;
    try {
      const pts = currentPoints(); S.pts = pts;
      if (!pts.length) { S.grid = null; msg('No usable points (check lat/lon/variable/formations)', true); redraw(); return; }
      const lat0 = pts.reduce((a, p) => a + p.lat, 0) / pts.length, lon0 = pts.reduce((a, p) => a + p.lon, 0) / pts.length;
      S.proj = C.makeProj(lon0, lat0);
      const ext = extent(pts), cell = Math.max(30, +$('g_cell').value || 1000) * 0.3048;
      const g = C.makeGrid(ext, cell, S.proj);
      const maskMi = +$('g_mask').value, o = { method: $('g_meth').value, power: +$('g_pow').value || 2, smooth: +$('g_smooth').value || 0, maxDist: maskMi > 0 ? maskMi * C.MI : Infinity, decluster: $('g_dec').checked, cellM: cell, neighbors: Math.max(0, Math.floor(+$('g_nn').value || 0)) };
      const t0 = performance.now(), info = C.gridPoints(g, pts.map(p => { const q = S.proj.fwd(p.lon, p.lat); return { x: q[0], y: q[1], z: p.z }; }), o);
      S.grid = g; S.ext = ext; S.stats = C.gridStats(g);
      msg((info.nraw !== info.npts ? info.nraw + ' points (' + info.npts + ' after averaging within cells), ' : info.npts + ' points, ') + g.nx + ' x ' + g.ny + ' cells (' + S.stats.n.toLocaleString() + ' filled), ' + Math.round(performance.now() - t0) + ' ms');
    } catch (e) { S.grid = null; msg(e.message, true); }
    redraw();
  }

  function range() {
    const mn = $('g_min').value.trim(), mx = $('g_max').value.trim();
    let lo = mn === '' ? NaN : +mn, hi = mx === '' ? NaN : +mx;
    const st = S.grid && S.stats.n ? S.stats : { min: Math.min(...S.pts.map(p => p.z)), max: Math.max(...S.pts.map(p => p.z)) };
    if (isNaN(lo)) lo = st.min; if (isNaN(hi)) hi = st.max; if (!(hi > lo)) hi = lo + 1; return [lo, hi];
  }
  function paint() {
    const sz = map.getSize(); cv.width = sz.x; cv.height = sz.y; L.DomUtil.setPosition(cv, map.containerPointToLayerPoint([0, 0]));
    const ctx = cv.getContext('2d'); ctx.clearRect(0, 0, sz.x, sz.y);
    if (!S.grid || !$('g_fill').checked) return;
    const g = S.grid, [lo, hi] = S.range, cm = C.colormap($('g_cmap').value, $('g_rev').checked, +$('g_steps').value);
    const xs = [], ys = [];
    for (let i = 0; i <= g.nx; i++) { const ll = S.proj.inv(g.x0 + i * g.dx, g.y0); xs.push(map.latLngToContainerPoint([ll[1], ll[0]]).x); }
    for (let j = 0; j <= g.ny; j++) { const ll = S.proj.inv(g.x0, g.y0 + j * g.dx); ys.push(map.latLngToContainerPoint([ll[1], ll[0]]).y); }
    for (let j = 0; j < g.ny; j++) {
      if (Math.max(ys[j], ys[j + 1]) < 0 || Math.min(ys[j], ys[j + 1]) > sz.y) continue;
      for (let i = 0; i < g.nx; i++) {
        const z = g.z[j * g.nx + i]; if (isNaN(z) || xs[i + 1] < 0 || xs[i] > sz.x) continue;
        const c = cm((z - lo) / (hi - lo)); ctx.fillStyle = 'rgb(' + c[0] + ',' + c[1] + ',' + c[2] + ')';
        ctx.fillRect(xs[i], ys[j + 1], xs[i + 1] - xs[i] + 0.6, ys[j] - ys[j + 1] + 0.6);
      }
    }
  }
  const LABZ = 10; let labShown = false;   // well value labels only from zoom 10 so thousands of points stay readable
  function redraw() {
    contourGrp.clearLayers(); ptGrp.clearLayers(); if (boxLayer) { map.removeLayer(boxLayer); boxLayer = null; }
    cv.style.opacity = +$('g_op').value;
    if (!S.pts.length) { leg.hidden = true; paint(); return; }
    S.range = range(); const [lo, hi] = S.range, cm = C.colormap($('g_cmap').value, $('g_rev').checked, +$('g_steps').value);
    paint();
    if (S.grid && $('g_cont').checked) {
      const st = +$('g_cint').value > 0 ? +$('g_cint').value : C.niceStep(hi - lo, 10), col = isDark() ? '#f2f2f2' : '#222';
      const nb = Math.max(0, Math.floor(+$('g_cbold').value || 0)), lab = $('g_clab').checked, fmtL = v => (+v.toPrecision(6)).toString();
      C.contours(S.grid, C.contourLevels(lo, hi, st)).forEach(c => {
        const segs = c.segs.map(s => { const a = S.proj.inv(s[0], s[1]), b = S.proj.inv(s[2], s[3]); return [[a[1], a[0]], [b[1], b[0]]]; });
        const bold = nb > 0 && Math.round(c.level / st) % nb === 0;
        L.polyline(segs, { color: col, weight: bold ? 2.8 : 1.2, opacity: bold ? 1 : 0.85, interactive: false }).addTo(contourGrp);
        if (lab) C.labelSpots(C.chainSegments(c.segs), 14 * S.grid.dx, 4 * S.grid.dx).forEach(sp => {
          const ll = S.proj.inv(sp.x, sp.y), deg = (-sp.angle * 180 / Math.PI).toFixed(1);
          L.marker([ll[1], ll[0]], { interactive: false, keyboard: false, icon: L.divIcon({ className: 'gridclab' + (bold ? ' b' : ''), iconSize: [0, 0], html: '<span style="display:inline-block;transform:translate(-50%,-50%) rotate(' + deg + 'deg)">' + fmtL(c.level) + '</span>' }) }).addTo(contourGrp);
        });
      });
    }
    if ($('g_pts').checked) S.pts.forEach(p => {
      const c = cm((p.z - lo) / (hi - lo));
      L.circleMarker([p.lat, p.lon], { radius: 4, weight: 1, color: isDark() ? '#fff' : '#000', fillColor: 'rgb(' + c.join(',') + ')', fillOpacity: 1 })
        .bindTooltip((p.id ? p.id + '<br>' : '') + (p.f ? p.f + '<br>' : '') + $('g_var').value + ': ' + (p.raw != null && p.raw !== p.z ? (+p.z.toFixed(1)) + ' (raw ' + p.raw + ')' : p.z)).addTo(ptGrp);
    });
    labShown = map.getZoom() >= LABZ;
    if ($('g_wlab').checked && $('g_fill').checked && S.grid && labShown) S.pts.forEach(p => {
      L.marker([p.lat, p.lon], { interactive: false, keyboard: false, icon: L.divIcon({ className: 'gridclab', iconSize: [0, 0],
        html: '<span style="display:inline-block;transform:translate(8px,-50%)">' + (+(+p.z).toPrecision(5)) + '</span>' }) }).addTo(ptGrp);
    });
    if ($('g_box').checked && S.ext) boxLayer = L.rectangle([[S.ext.s, S.ext.w], [S.ext.n, S.ext.e]], { color: '#e67e22', weight: 1.5, dashArray: '5 4', fill: false, interactive: false }).addTo(map);
    if ($('g_fill').checked && S.grid) legend(lo, hi, cm); else leg.hidden = true;
  }
  function legend(lo, hi, cm) {
    const steps = +$('g_steps').value; leg.hidden = false; leg.innerHTML = '<b>' + $('g_var').value + ($('g_bht').checked ? ' (BHT-corrected)' : '') + '</b><canvas width="200" height="12"></canvas><div class="tk"></div>';
    const c = leg.querySelector('canvas').getContext('2d');
    for (let x = 0; x < 200; x++) { const k = cm(x / 199); c.fillStyle = 'rgb(' + k.join(',') + ')'; c.fillRect(x, 0, 1, 12); }
    const tk = leg.querySelector('.tk'), st = C.niceStep(hi - lo, 4), fmt = v => (+v.toPrecision(4)).toString();
    C.contourLevels(lo, hi, st).forEach(v => { const s = document.createElement('span'); s.style.left = (200 * (v - lo) / (hi - lo)) + 'px'; s.textContent = fmt(v); tk.appendChild(s); });
    leg.title = (steps > 1 ? steps + ' color steps; ' : '') + 'range ' + fmt(lo) + ' to ' + fmt(hi);
  }

  /* wiring */
  let timer; const later = fn => { clearTimeout(timer); timer = setTimeout(fn, 250); };
  pop.querySelectorAll('.calc').forEach(el => el.addEventListener(el.tagName === 'INPUT' ? 'input' : 'change', () => {
    if (!S.data) return;
    if (el.id === 'g_lat' || el.id === 'g_lon') refreshVars();
    if (el.id === 'g_fmc') refreshFms(true);
    later(rebuild);
  }));
  pop.querySelectorAll('.disp').forEach(el => el.addEventListener('input', () => later(redraw)));

  /* Borehole temperatures (state well-log header values, AASG/SMU via NBMG ArcGIS service): fetch the basin's points, filter, compute a depth-normalised gradient, then hand a CSV to the normal loader. */
  const BH_URL = 'https://web2.nbmg.unr.edu/arcgis/rest/services/WY_Data/WYBoreholeTemperatures/MapServer/0/query';
  async function loadBoreholes() {
    const msgB = t => { $('bh_msg').textContent = t; }, btn = $('bh_load'); btn.disabled = true; msgB('Loading points...');
    try {
      const F = 'WellName,APINo,Operator,County,MeasuredTemperature,MaximumRecordedTemperature,DepthOfMeasurement,TimeSinceCirculation,MeasurementFormation,MeasurementDateTime';
      let feats = [], off = 0;
      for (;;) {
        const q = new URLSearchParams({ where: '1=1', geometry: '-107.6,42.0,-104.0,45.0', geometryType: 'esriGeometryEnvelope', inSR: '4326', outSR: '4326', outFields: F, returnGeometry: 'true', resultOffset: off, resultRecordCount: 1000, orderByFields: 'OBJECTID', f: 'json' });
        const d = await (await fetch(BH_URL + '?' + q)).json(); if (d.error) throw new Error(d.error.message || 'service error');
        feats = feats.concat(d.features || []); off += 1000; msgB('Loading points... ' + feats.length);
        if (!d.exceededTransferLimit || !(d.features || []).length) break;
      }
      const ok = v => v != null && v !== '' && v !== 'Null' && +v > -90000, dmin = +$('bh_dmin').value || 0, dmax = +$('bh_dmax').value || Infinity, ts = +$('bh_ts').value, qc = $('bh_qc').checked;
      const hdr = ['API', 'Well_Name', 'Operator', 'County', 'Lat', 'Lon', 'Depth_ft', 'Temp_F', 'Gradient_F_100ft', 'Measured_F', 'MaxRecorded_F', 'Time_Since_Circ_hrs', 'Formation', 'Date'];
      const cell = v => { v = v == null ? '' : String(v); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
      let nd = 0, nq = 0, nm = 0; const lines = [hdr.join(',')];
      feats.forEach(f => {
        const a = f.attributes, g = f.geometry; if (!g || !ok(a.DepthOfMeasurement) || +a.DepthOfMeasurement <= 0) { nm++; return; }
        const dep = +a.DepthOfMeasurement, T = ok(a.MaximumRecordedTemperature) && +a.MaximumRecordedTemperature > 0 ? +a.MaximumRecordedTemperature : (ok(a.MeasuredTemperature) ? +a.MeasuredTemperature : NaN);
        if (isNaN(T) || dep < dmin || dep > dmax) { nd++; return; }
        const gr = (T - ts) / dep * 100; if (qc && (gr < 0.5 || gr > 4)) { nq++; return; }
        const dt = a.MeasurementDateTime ? new Date(+a.MeasurementDateTime).toISOString().slice(0, 10) : '';
        lines.push([a.APINo, a.WellName, a.Operator, a.County, g.y.toFixed(5), g.x.toFixed(5), dep, T, gr.toFixed(3), ok(a.MeasuredTemperature) ? a.MeasuredTemperature : '', ok(a.MaximumRecordedTemperature) ? a.MaximumRecordedTemperature : '', ok(a.TimeSinceCirculation) ? a.TimeSinceCirculation : '', a.MeasurementFormation || '', dt].map(cell).join(','));
      });
      if (lines.length < 4) { msgB('Only ' + (lines.length - 1) + ' points pass the filters; widen the depth range.'); return; }
      loadText(lines.join('\n'), 'Borehole temperatures (AASG/SMU)');
      $('g_var').value = 'Gradient_F_100ft'; $('g_fill').checked = true; $('g_pts').checked = true; rebuild();
      msgB((lines.length - 1) + ' points loaded of ' + feats.length + ' in the service (' + nm + ' have no depth, ' + nd + ' outside the depth range or no temperature, ' + nq + ' dropped by gradient check). Variable set to Gradient_F_100ft; choose Temp_F to grid temperature itself (best with a narrow depth range).');
    } catch (e) { msgB('Could not load: ' + (e.message || e) + ' (the state service may be down; try again later).'); }
    finally { btn.disabled = false; }
  }
  $('bh_load').onclick = loadBoreholes;
  $('g_file').onchange = e => { const f = e.target.files[0]; if (f) f.text().then(t => { loadText(t, f.name); $('g_fill').checked = true; $('g_pts').checked = true; redraw(); }); };
  $('g_all').onclick = () => { if (S.data) { refreshFms(true); rebuild(); } };
  $('g_none').onclick = () => { if (S.data) { S.fms.clear(); refreshFms(false); rebuild(); } };
  $('g_go').onclick = rebuild;
  $('g_setview').onclick = () => { const b = map.getBounds(); $('g_w').value = b.getWest().toFixed(4); $('g_e').value = b.getEast().toFixed(4); $('g_s').value = b.getSouth().toFixed(4); $('g_n').value = b.getNorth().toFixed(4); $('g_ext').value = 'custom'; if (S.data) rebuild(); };
  $('g_clear').onclick = () => { S.data = null; S.grid = null; S.pts = []; $('g_info').textContent = 'Cleared'; msg(''); try { localStorage.removeItem(KEY); } catch (e) { } redraw(); };
  $('g_exp').onclick = () => {
    if (!S.grid) { msg('Nothing to export yet', true); return; }
    const g = S.grid, rows = ['i,j,lon,lat,' + $('g_var').value.replace(/[",]/g, '_')];
    for (let j = 0; j < g.ny; j++) for (let i = 0; i < g.nx; i++) { const z = g.z[j * g.nx + i]; if (isNaN(z)) continue; const ll = S.proj.inv(C.cx(g, i), C.cy(g, j)); rows.push([i, j, ll[0].toFixed(6), ll[1].toFixed(6), +z.toPrecision(6)].join(',')); }
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([rows.join('\n')], { type: 'text/csv' })); a.download = 'grid_' + $('g_var').value + '.csv'; a.click();
  };
  map.on('zoomstart', () => { cv.style.visibility = 'hidden'; });
  map.on('zoomend', () => { if ((map.getZoom() >= LABZ) !== labShown && S.pts.length) redraw(); });
  map.on('zoomend moveend resize', () => { cv.style.visibility = ''; if (S.pts.length) paint(); });
  try { const sv = JSON.parse(localStorage.getItem(KEY) || 'null'); if (sv && sv.text) loadText(sv.text, sv.name); } catch (e) { }

  /* permanent layer: vertical wells whose logs were read (public state data only: location, name, API, operator, spud year, TD, formation) */
  const vertGrp = L.layerGroup(); let vertLoaded = false;
  function vertToggle() {
    if ($('g_vert').checked) { vertGrp.addTo(map); if (!vertLoaded) vertLoad(); } else map.removeLayer(vertGrp);
  }
  function vertLoad() {
    vertLoaded = true;
    fetch('data/vertical_wells.json').then(r => r.json()).then(list => {
      const dk = isDark();
      list.forEach(w => L.circleMarker([w.ll[1], w.ll[0]], { radius: 2.8, weight: 1, color: dk ? '#fff' : '#fff', fillColor: dk ? '#c9c9c9' : '#3b3b3b', fillOpacity: 1 })
        .bindPopup('<b>' + (w.n || '') + '</b><br>API <a href="https://pipeline.wyo.gov/wellapi.cfm?nAPINO=' + (+w.a.split('-')[1]) + w.a.split('-')[2] + '" target="_blank" rel="noopener">' + w.a + '</a><br>' + (w.o || '') + '<br>' + [w.y ? 'spud ' + w.y : '', w.td ? 'TD ' + w.td.toLocaleString() + ' ft' : '', w.f || ''].filter(Boolean).join(' · ') + '<br><i>vertical well, induction log reviewed</i>').addTo(vertGrp));
      $('g_vn').textContent = '(' + list.length + ')';
    }).catch(() => { vertLoaded = false; $('g_vn').textContent = '(not available)'; });
  }
  $('g_vert').addEventListener('change', vertToggle); vertToggle();

  /* handle for later work (correlating the surface with horizontal wells, scripts, console) */
  window.GridMap = {
    state: S, core: C, loadText,
    sample(lon, lat) { return S.grid ? C.sampleGrid(S.grid, ...S.proj.fwd(lon, lat)) : NaN; }
  };
})();
