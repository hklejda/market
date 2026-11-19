# Live Supermarket

A walkable 3D supermarket in the browser, built with Three.js. You walk the aisles, browse real products, and add them to a cart.

## Features
- 6 sections (Fruta & Perime, Bulmet, Ushqime, Pije, Ëmbëlsira, Shtëpia) with 120 real products
- Real product photos, names and prices in Lek from SPAR Albania's online shop (shop.spar.al), collected on 19 Nov 2026
- Click a product to see its photo and price, add it to the cart, or open its page on shop.spar.al
- Cart with checkout, a minimap you can click to walk, and section shortcuts
- Desktop (drag + W A S D) and mobile (joystick + drag) controls

## Run locally
The page loads its photo files, so serve the folder rather than opening the file directly:

```bash
python -m http.server 8000
# open http://localhost:8000
```

## Files
- `index.html`: the whole app (HTML, CSS and JavaScript; Three.js r128 from cdnjs)
- `atlas0.jpg` to `atlas11.jpg`: product photo sheets, 10 products per sheet in a 5×2 grid of 256px tiles. Sheet `n` holds products 1–10 of section `n`, and sheet `n+6` holds products 11–20.
- `tools/spar_export.py`: optional script to download more products from shop.spar.al

## Note
The product photos come from SPAR Albania's shop and the brands. Get permission before using them publicly or commercially.
