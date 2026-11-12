// node tools/test_gridcore.js  -- sanity tests for the gridding core in gridmap.js
const C = require('../gridmap.js');
const assert = require('assert');
let fails = 0; const ok = (c, m) => { if (!c) { fails++; console.log('FAIL', m); } else console.log('ok  ', m); };

// CSV
const d = C.parseCSV('API,Lat,Lon,"Name, x",T\n1,43.5,-105.5,"A ""q""",200\n2,43.6,-105.4,B,\n');
ok(d.rows.length === 2 && d.rows[0]['Name, x'] === 'A "q"', 'csv quotes');
const dc = C.detectColumns(d.headers); ok(dc.lat === 'Lat' && dc.lon === 'Lon' && dc.label === 'API', 'column detect');

// planar surface z = 0.01*x + 0.02*y (m), random points
const proj = C.makeProj(-105.5, 43.7); let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
const pts = []; for (let i = 0; i < 200; i++) { const x = (rnd() - .5) * 40000, y = (rnd() - .5) * 40000; pts.push({ x, y, z: 100 + 0.01 * x + 0.02 * y }); }
const ext = (() => { const a = proj.inv(-15000, -15000), b = proj.inv(15000, 15000); return { w: a[0], s: a[1], e: b[0], n: b[1] }; })();
let g = C.makeGrid(ext, 0.5 * C.MI, proj);
ok(Math.abs(g.dx - 804.672) < 1e-6 && g.nx >= 37 && g.nx <= 39, 'cell is 0.5 mile, nx=' + g.nx);
C.gridPoints(g, pts, { method: 'spline', maxDist: 5 * C.MI });
let err = 0, n = 0; for (let j = 0; j < g.ny; j++) for (let i = 0; i < g.nx; i++) { const z = g.z[j * g.nx + i]; if (isNaN(z)) continue; err = Math.max(err, Math.abs(z - (100 + 0.01 * C.cx(g, i) + 0.02 * C.cy(g, j)))); n++; }
ok(n > 1000 && err < 0.5, 'spline reproduces a plane (max err ' + err.toFixed(4) + ', ' + n + ' cells)');
g = C.makeGrid(ext, 0.5 * C.MI, proj); C.gridPoints(g, pts, { method: 'idw', power: 2, maxDist: 5 * C.MI });
err = 0; for (let j = 0; j < g.ny; j++) for (let i = 0; i < g.nx; i++) { const z = g.z[j * g.nx + i]; if (!isNaN(z)) err = Math.max(err, Math.abs(z - (100 + 0.01 * C.cx(g, i) + 0.02 * C.cy(g, j)))); }
ok(err < 80, 'idw roughly follows plane (max err ' + err.toFixed(1) + ' on range 1000)');

// mask: far points blank
const far = C.makeGrid({ w: -105.5, s: 43.7, e: -105.0, n: 43.75 }, C.MI, proj);
C.gridPoints(far, [{ x: -1000, y: 0, z: 5 }, { x: 0, y: 1000, z: 6 }], { method: 'idw', maxDist: 3 * C.MI });
const st = C.gridStats(far); ok(st.n > 0 && st.n < far.z.length, 'mask blanks distant cells (' + st.n + '/' + far.z.length + ')');

// contours of the plane at z=100 pass through origin: every segment endpoint satisfies the level
g = C.makeGrid(ext, 0.5 * C.MI, proj); C.gridPoints(g, pts, { method: 'spline', maxDist: 5 * C.MI });
const cs = C.contours(g, [100]); let cerr = 0; cs[0].segs.forEach(s => { cerr = Math.max(cerr, Math.abs(100 + 0.01 * s[0] + 0.02 * s[1] - 100), Math.abs(0.01 * s[2] + 0.02 * s[3])); });
ok(cs.length === 1 && cs[0].segs.length > 20 && cerr < 1, 'contour segments lie on level (' + cs[0].segs.length + ' segs, err ' + cerr.toFixed(3) + ')');

// sample
const zs = C.sampleGrid(g, 0, 0); ok(Math.abs(zs - 100) < 0.5, 'sampleGrid at origin = ' + zs.toFixed(3));
ok(isNaN(C.sampleGrid(g, 1e6, 0)), 'sample outside is NaN');

// levels / palettes
ok(C.niceStep(190, 10) === 20 && C.niceStep(0.9, 10) === 0.1, 'niceStep');
ok(C.contourLevels(103, 131, 10).join() === '110,120,130', 'contourLevels');
const cm = C.colormap('viridis', false, 0), r = C.colormap('viridis', true, 0);
ok(cm(0).join() === '68,1,84' && r(1).join() === '68,1,84', 'viridis ends / reverse');
const q = C.colormap('viridis', false, 4); ok(q(0.30).join() === q(0.40).join() && q(0.30).join() !== q(0.60).join(), 'discrete steps');

// big-grid guard
let threw = false; try { C.makeGrid({ w: -108, s: 41, e: -104, n: 45 }, 0.01 * C.MI, proj); } catch (e) { threw = true; } ok(threw, 'huge grid refused');
console.log(fails ? fails + ' FAILED' : 'all passed'); process.exit(fails ? 1 : 0);
