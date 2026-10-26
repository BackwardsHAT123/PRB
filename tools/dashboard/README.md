# Operator performance dashboard

`dashboard.html` (repo root) is the public page, served by GitHub Pages at https://backwardshat123.github.io/PRB/dashboard.html. It loads four tables from `dashboard/data/` (`wells`, `bench`, `curves`, `drivers`) and covers every operator on the map that has wells with reported production.

To rebuild the tables:

1. Copy `index.html` and `data/production.json` into one folder with `build_all.py`.
2. Run `python3 build_all.py` (needs `numpy`).
3. Copy `wells.json`, `bench.json`, `curves.json` and `drivers.json` into `dashboard/data/`.

The comparison basis ("vs basin") is the median well in the same formation across all operators on the map. Everything else (operator picker, formation filter, rankings, verdicts) is computed in the page from `wells.json`.
Well links on the dashboard use `https://backwardshat123.github.io/PRB/#<API number>`; the map opens that well.
