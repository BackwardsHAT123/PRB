# Georeferenced reference figures

`warp.py` places a rendered figure on the map: it fits an affine transform (pixels -> local equirectangular metres) to hand-picked control points and resamples the figure into a Web-Mercator-aligned WebP that Leaflet can show as an image overlay.

    python3 tools/georef/warp.py SRC.png tools/georef/bht_cps.json x0,y0,x1,y1 data/ref/prb_bht.webp 3000

- `SRC.png`: the PDF rendered with `sips -s format png --resampleWidth 6400 file.pdf`.
- `bht_cps.json`: `[px, py, lon, lat]` for nine towns on the Powder River Basin bottom-hole-temperature figure (Sheridan, Buffalo, Kaycee, Moorcroft, Gillette, Douglas, Lusk, Casper, Evansville). RMS residual 1.1 mi.
- The frame rectangle (`151,351,4718,4766` for that render) clips everything outside the map frame.
- The printed bounds go into `LY.refbht.bounds` in `index.html`.

The USGS I-1159 plate is not georeferenced yet (four figure frames, no usable control points beyond the state-line tripoints).
