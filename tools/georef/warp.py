"""Warp a rendered map image into a Web-Mercator-aligned WebP overlay.
usage: python3 warp.py SRC.png CPS.json FRAME(x0,y0,x1,y1) OUT.webp [maxwidth]
CPS = [[px,py,lon,lat],...]; order-1 (affine) fit in a local equirectangular projection."""
import sys, json, numpy as np
from PIL import Image
from scipy.ndimage import map_coordinates
Image.MAX_IMAGE_PIXELS = None
R = 6371008.8; LAT0, LON0 = 44.0, -105.5
def proj(lon, lat): return R*np.radians(np.asarray(lon)-LON0)*np.cos(np.radians(LAT0)), R*np.radians(np.asarray(lat)-LAT0)
def unproj(X, Y): return LON0+np.degrees(np.asarray(X)/(R*np.cos(np.radians(LAT0)))), LAT0+np.degrees(np.asarray(Y)/R)
def merc(lon, lat): return np.radians(lon)*6378137.0, np.log(np.tan(np.pi/4+np.radians(lat)/2))*6378137.0
def unmerc(x, y): return np.degrees(x/6378137.0), np.degrees(2*np.arctan(np.exp(y/6378137.0))-np.pi/2)
def affine(src, dst):
    A = np.c_[np.ones(len(src)), src]; return np.linalg.lstsq(A, dst, rcond=None)[0]   # 3x2
def apply(M, p): return np.c_[np.ones(len(p)), p] @ M
def main():
    src, cps, frame, out = sys.argv[1], json.load(open(sys.argv[2])), [int(v) for v in sys.argv[3].split(',')], sys.argv[4]
    mw = int(sys.argv[5]) if len(sys.argv) > 5 else 3000
    c = np.array(cps, float); XY = np.c_[proj(c[:, 2], c[:, 3])]
    fwd = affine(c[:, :2], XY); inv = affine(XY, c[:, :2])
    res = np.hypot(*(apply(fwd, c[:, :2]) - XY).T)/1609.34; print('residual mi', np.round(res, 2), 'rms', round(float(np.sqrt((res**2).mean())), 2))
    x0, y0, x1, y1 = frame
    corners = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], float)
    lonlat = np.c_[unproj(*apply(fwd, corners).T)]
    mx, my = merc(lonlat[:, 0], lonlat[:, 1]); mnx, mxx, mny, mxy = mx.min(), mx.max(), my.min(), my.max()
    W = mw; H = int(round(W*(mxy-mny)/(mxx-mnx)))
    u, v = np.meshgrid(np.arange(W)+.5, np.arange(H)+.5)
    X_m = mnx+(mxx-mnx)*u/W; Y_m = mxy-(mxy-mny)*v/H
    lon, lat = unmerc(X_m, Y_m); X, Y = proj(lon, lat)
    P = apply(inv, np.c_[X.ravel(), Y.ravel()]); sx, sy = P[:, 0].reshape(H, W), P[:, 1].reshape(H, W)
    img = np.array(Image.open(src).convert('RGBA'))
    chans = [map_coordinates(img[..., k].astype(float), [sy, sx], order=1, cval=0) for k in range(4)]
    inside = (sx >= x0) & (sx <= x1) & (sy >= y0) & (sy <= y1)
    chans[3] = np.where(inside, chans[3], 0)
    o = np.stack(chans, -1).clip(0, 255).astype(np.uint8)
    Image.fromarray(o, 'RGBA').save(out, 'WEBP', quality=82, method=6)
    s, w_, n, e = *unmerc(mnx, mny), *unmerc(mxx, mxy)
    print(json.dumps({'south': s[()] if hasattr(s,'shape') else s, 'west': w_, 'north': n, 'east': e, 'size': [W, H]}) if False else json.dumps({'bounds': [[float(unmerc(mnx,mny)[1]), float(unmerc(mnx,mny)[0])], [float(unmerc(mxx,mxy)[1]), float(unmerc(mxx,mxy)[0])]], 'size': [W, H]}))
main()
