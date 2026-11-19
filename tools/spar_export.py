"""
Downloads products (name, price, category, photo) from SPAR Albania's online shop
into a folder you can zip and send back.

Run:   pip install requests pillow
       python spar_export.py
Result: spar_export.zip  (products.json + img/*.jpg)
"""
import io, json, os, re, shutil, time
import requests
from PIL import Image

BASE = "https://shop.spar.al/wp-json/wc/store/v1/products"
OUT = "spar_export"
MAX_PRODUCTS = 400          # enough to fill the store; raise if you want more
HEAD = {"User-Agent": "Mozilla/5.0 (personal prototype export)"}

os.makedirs(f"{OUT}/img", exist_ok=True)
products, page = [], 1

while len(products) < MAX_PRODUCTS:
    r = requests.get(BASE, params={"per_page": 100, "page": page}, headers=HEAD, timeout=30)
    if r.status_code != 200:
        print("Stopped at page", page, "status", r.status_code)
        break
    batch = r.json()
    if not batch:
        break
    for p in batch:
        if not p.get("images") or not p.get("is_in_stock", True):
            continue
        pr = p.get("prices", {})
        minor = int(pr.get("currency_minor_unit", 0) or 0)
        try:
            price = int(pr.get("price", "0")) / (10 ** minor)
        except ValueError:
            continue
        if price <= 0:
            continue
        cats = [c.get("name", "") for c in p.get("categories", [])]
        slugs = [c.get("slug", "") for c in p.get("categories", [])]
        products.append({
            "id": p["id"],
            "name": re.sub(r"<[^>]+>", "", p.get("name", "")).replace("&amp;", "&").strip(),
            "price": round(price),
            "categories": cats,
            "slugs": slugs,
            "url": p.get("permalink", ""),
            "img_src": p["images"][0]["src"],
        })
    print(f"page {page}: {len(products)} products so far")
    page += 1
    time.sleep(0.5)

products = products[:MAX_PRODUCTS]
kept = []
for i, p in enumerate(products, 1):
    try:
        r = requests.get(p["img_src"], headers=HEAD, timeout=30)
        im = Image.open(io.BytesIO(r.content)).convert("RGB")
        im.thumbnail((256, 256))
        canvas = Image.new("RGB", (256, 256), "white")
        canvas.paste(im, ((256 - im.width) // 2, (256 - im.height) // 2))
        fn = f"img/{p['id']}.jpg"
        canvas.save(f"{OUT}/{fn}", "JPEG", quality=80)
        p["img"] = fn
        del p["img_src"]
        kept.append(p)
    except Exception as e:
        print("skip image", p["name"], e)
    if i % 25 == 0:
        print(f"images {i}/{len(products)}")
    time.sleep(0.2)

with open(f"{OUT}/products.json", "w", encoding="utf-8") as f:
    json.dump(kept, f, ensure_ascii=False, indent=1)

shutil.make_archive("spar_export", "zip", OUT)
print(f"Done: {len(kept)} products -> spar_export.zip")
