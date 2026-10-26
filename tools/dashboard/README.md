# Operator performance dashboard

`dashboard.html` (repo root) is the public page, served by GitHub Pages at https://backwardshat123.github.io/PRB/dashboard.html. It loads five tables from `dashboard/data/` (`wells`, `bench`, `curves`, plus `grid` and `sections` for the map's township and section lines) and covers every operator on the map that has wells with reported production.

To rebuild the tables:

1. Copy `index.html` and `data/production.json` into one folder with `build_all.py`.
2. Run `python3 build_all.py` (needs `numpy`).
3. Copy `wells.json`, `bench.json`, `curves.json`, `grid.json` and `sections.json` into `dashboard/data/`. (`grid.json` and `sections.json` rarely change.) The map's street background comes from OpenStreetMap tiles at view time.

The comparison basis ("vs basin") is the median well in the same formation across all operators on the map. Everything else (operator picker, formation filter, rankings, verdicts and the "what explains" regressions) is computed in the page from `wells.json`, so it follows the filters.
Well links on the dashboard use `https://backwardshat123.github.io/PRB/#<API number>`; the map opens that well.
