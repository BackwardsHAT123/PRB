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

// contour chaining + label spots
const chains = C.chainSegments(cs[0].segs); const nseg = chains.reduce((t, c) => t + c.length - 1, 0);
ok(nseg === cs[0].segs.length && chains.length <= 3, 'chainSegments keeps every segment (' + chains.length + ' chain(s), ' + nseg + ' segs)');
const spots = C.labelSpots(chains, 14 * g.dx, 4 * g.dx);
ok(spots.length >= 1 && spots.every(p => Math.abs(p.angle) <= Math.PI / 2 + 1e-9 && isFinite(p.x) && isFinite(p.y)), 'labelSpots upright angles (' + spots.length + ' spots)');
const sp = spots[0]; ok(Math.abs(100 + 0.01 * sp.x + 0.02 * sp.y - 100) < 1, 'label sits on the contour');
ok(C.labelSpots([[[0, 0], [10, 0]]], 1000, 100).length === 0, 'short lines get no label');

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

// decluster: points in the same cell are averaged; IDW still blanks cells beyond the mask; nearest-N caps the neighbours
{
  const pr = C.makeProj(-105.5, 43.7), cell = 304.8;                 // 1000 ft
  const dp = [{ x: 10, y: 10, z: 100 }, { x: 60, y: 90, z: 200 }, { x: 120, y: 40, z: 300 }, { x: 5000, y: 5000, z: 50 }];
  const e2 = (() => { const a = pr.inv(-2000, -2000), b = pr.inv(7000, 7000); return { w: a[0], s: a[1], e: b[0], n: b[1] }; })();
  let g2 = C.makeGrid(e2, cell, pr); let info = C.gridPoints(g2, dp.map(p => ({ ...p })), { method: 'idw', power: 2, maxDist: 2 * C.MI, decluster: true, cellM: cell });
  ok(info.nraw === 4 && info.npts === 2, 'decluster averages the 3 points in one cell (raw ' + info.nraw + ' -> ' + info.npts + ')');
  g2 = C.makeGrid(e2, cell, pr); info = C.gridPoints(g2, dp.map(p => ({ ...p })), { method: 'idw', power: 2, maxDist: 2 * C.MI });
  ok(info.npts === 4, 'no decluster keeps all 4 points');
  const dc2 = C.declust(dp.map(p => ({ ...p })), cell).sort((a, b) => a.z - b.z); ok(Math.abs(dc2[1].z - 200) < 1e-9, 'cell mean is 200');
  const far = C.makeGrid({ w: -105.9, s: 43.3, e: -105.8, n: 43.4 }, cell, pr); C.gridPoints(far, [{ x: 0, y: 0, z: 1 }], { method: 'idw', power: 2, maxDist: 2 * C.MI });
  ok(C.gridStats(far).n === 0, 'IDW leaves cells beyond the mask blank');
  const cl = [{ x: 0, y: 0, z: 100 }, { x: 10, y: 0, z: 100 }, { x: 20, y: 0, z: 100 }, { x: 30, y: 0, z: 100 }, { x: 3000, y: 0, z: 200 }];
  const gn = (nn) => { const gg = C.makeGrid(e2, cell, pr); C.gridPoints(gg, cl.map(p => ({ ...p })), { method: 'idw', power: 2, maxDist: 3 * C.MI, neighbors: nn, clamp: false }); return C.sampleGrid(gg, 1500, 0); };
  ok(Math.abs(gn(0) - gn(2)) > 1, 'nearest-N changes the cluster-weighted result (' + gn(0).toFixed(1) + ' vs ' + gn(2).toFixed(1) + ')');
}

// well comparison helpers
ok(C.cmpMode({oc:'A',r:'Turner'},{oc:'A',r:'Parkman'}) === 'well', 'compare: same operator -> by well');
ok(C.cmpMode({oc:'A',r:'Turner'},{oc:'B',r:'Turner'}) === 'well', 'compare: same formation -> by well');
ok(C.cmpMode({oc:'A',r:'Turner'},{oc:'B',r:'Parkman'}) === 'formation', 'compare: different operator and formation -> by formation');
ok(C.cmpWhy({oc:'A',r:'Turner'},{oc:'B',r:'Turner'}) === 'same formation' && C.cmpWhy({oc:'A',r:'T'},{oc:'A',r:'P'}) === 'same operator' && C.cmpWhy({oc:'A',r:'T'},{oc:'B',r:'P'}) === 'different formations', 'compare: reason text');
ok(JSON.stringify(C.cumSeries([1,2,0,'3',null])) === '[1,3,3,6,6]', 'compare: cumulative series');
ok(JSON.stringify(C.cmpOffsets('2019-11','2020-02','age')) === '[0,0]' && JSON.stringify(C.cmpOffsets('2019-11','2020-02','date')) === '[0,3]' && JSON.stringify(C.cmpOffsets('2020-02','2019-11','date')) === '[3,0]', 'compare: x offsets');
ok(JSON.stringify(C.cmpOffsetsN(['2020-03','2020-01','2021-01'],'date')) === '[2,0,12]' && JSON.stringify(C.cmpOffsetsN(['2020-03','2020-01'],'age')) === '[0,0]', 'compare: N-well offsets');
ok(Math.abs(C.milesBetween(-105.5, 43.5, -105.5, 44.5) - 69.1) < 0.3 && C.milesBetween(-105.5, 43.5, -105.5, 43.5) === 0, 'miles between points (1 deg lat = 69.1 mi)');
ok(C.cmpExtent([20,48,30],'age',36) === 36 && C.cmpExtent([20,30],'age',36) === 30 && C.cmpExtent([20,48],'date',36) === 48, 'compare: axis capped at 36 months, else oldest extent');
{ // Harrison BHT correction: 9000 ft = 2743.2 m -> +15.96 C = +28.7 F
  const c = C.harrisonBHT(178, 9000); ok(Math.abs(c - 178 - 28.72) < 0.05, 'harrison BHT 9000 ft (' + (c - 178).toFixed(2) + ' F added)');
  ok(isNaN(C.harrisonBHT(178, 0)) && isNaN(C.harrisonBHT(NaN, 9000)), 'harrison BHT needs depth and temperature');
}
ok(C.percentile([1,2,3,4,5],0.5) === 3 && C.percentile([0,10],0.1) === 1 && C.percentile([7],0.9) === 7 && isNaN(C.percentile([],0.5)), 'percentile');
console.log(fails ? fails + ' FAILED' : 'all passed'); process.exit(fails ? 1 : 0);
