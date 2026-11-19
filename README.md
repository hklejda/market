# Live Supermarket

A walkable 3D supermarket in the browser, built with Three.js, stocked with the **full SPAR Albania online catalogue**: about 3,000 real products with their photos, names and prices in Lek.

**Live:** https://hklejda.github.io/market/

## Features
- Every SPAR product that has a photo and a price, laid out automatically into aisles by category
- Search any product and jump straight to its shelf
- Click a product for its photo, price and a link to its page on shop.spar.al, then add it to the cart
- Category shortcuts, a clickable minimap and an aisle label that shows where you are
- Sharp photos load for the aisles near you and lighter ones for the rest, so it stays fast
- Desktop (drag + W A S D, Shift to run) and mobile (joystick + drag) controls

## How the catalogue is built
`tools/build_catalog.py` crawls shop.spar.al, cuts each product photo out of its white background and packs the photos into WebP sheets:

- `catalog/catalog.json`: sections, categories and products (`[name, price, slug, category, sheet, tile]`)
- `catalog/sheet_NNN.webp`: 2048×2048 sheets of 8×8 photos, 256 px each
- `catalog/sheet_NNN_s.webp`: the same sheets at 512×512, for distant shelves

The GitHub Action `.github/workflows/catalog.yml` runs the builder **every Monday** and commits the result, so prices and products stay current. You can also run it by hand from the Actions tab ("Build SPAR catalogue" → Run workflow).

## Run locally
```bash
python -m http.server 8000
# open http://localhost:8000
```

## Note
Product photos and names belong to SPAR Albania and the brands. This is a personal prototype. Get permission before using it commercially.
