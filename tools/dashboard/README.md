# Operator performance dashboard

`dashboard.html` (repo root) is the public page, served by GitHub Pages at https://backwardshat123.github.io/PRB/dashboard.html. It loads six tables from `dashboard/data/`.

To rebuild the tables for Ballard Petroleum and Sage Butte:

1. Copy `index.html` and `data/production.json` into one folder with these three scripts.
2. Run `python3 build_data.py`, then `python3 build2.py`, then `python3 build3.py`. Needs `numpy`.
3. Copy `wells.json`, `groups.json`, `curves.json`, `drivers.json`, `vintage.json` and `area.json` into `dashboard/data/`.

The basin comparison uses every other operator's wells on the map. Operators are chosen by the `FOCUS` tuple at the top of `build_data.py`.
Well links on the dashboard use `https://backwardshat123.github.io/PRB/#<API number>`; the map opens that well.
