"""
Builds the full SPAR Albania catalogue for the Live Supermarket.

Crawls https://shop.spar.al/shop/page/N/, collects every product (name, price,
categories, photo), cuts each photo out of its white background and packs the
photos into 2048x2048 WebP sheets of 8x8 tiles (256 px each).

Output (in catalog/):
  catalog.json      sections, categories and products
  sheet_000.webp …  photo sheets (tile t of sheet s = product photo)

Run:  pip install requests beautifulsoup4 pillow numpy scipy
      python tools/build_catalog.py
"""
import io, json, os, re, sys, time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import requests
from bs4 import BeautifulSoup
from PIL import Image
from scipy import ndimage

BASE = "https://shop.spar.al"
OUT = "catalog"
TILE, GRID = 256, 8
PER_SHEET = GRID * GRID
HEAD = {"User-Agent": "Mozilla/5.0 (LiveSupermarket catalogue builder; github.com/hklejda/market)"}
CROSS_LISTS = {"produkte-spar", "produkte-italiane", "oferta", "te-pakategorizuara"}

S = requests.Session()
S.headers.update(HEAD)


def get(url, tries=4):
    for i in range(tries):
        try:
            r = S.get(url, timeout=40)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r
        except Exception as e:
            if i == tries - 1:
                print("  failed", url, e)
                return None
            time.sleep(2 + 3 * i)


# ---------- categories from the shop menu ----------
def load_categories():
    r = get(BASE + "/")
    soup = BeautifulSoup(r.text, "html.parser")
    paths = {}
    for a in soup.select('a[href*="/product-category/"]'):
        p = a["href"].split("?")[0].split("/product-category/")[1].strip("/")
        name = a.get_text(" ", strip=True)
        if p and name and p not in paths:
            paths[p] = name
    by_slug = {}
    for p, name in paths.items():
        slug = p.split("/")[-1]
        # keep the deepest path for a slug
        if slug not in by_slug or len(p) > len(by_slug[slug][0]):
            by_slug[slug] = (p, name)
    return paths, by_slug


def section_for(path, paths):
    parts = path.split("/")
    if parts[0] == "ushqimore" and len(parts) > 1:
        key = "/".join(parts[:2])
    else:
        key = parts[0]
    return key, paths.get(key, key.replace("-", " ").title())


# ---------- products ----------
def parse_price(el):
    if not el:
        return 0
    t = re.sub(r"[^\d.,]", "", el.get_text())
    t = re.sub(r"[.,](?=\d{3}(\D|$))", "", t).replace(",", ".")
    try:
        return round(float(t))
    except ValueError:
        return 0


def crawl_products():
    first = get(BASE + "/shop/")
    soup = BeautifulSoup(first.text, "html.parser")
    nums = [int(x.get_text()) for x in soup.select(".page-numbers") if x.get_text().strip().isdigit()]
    last = max(nums) if nums else 1
    print("pages:", last)

    def page(n):
        r = first if n == 1 else get(f"{BASE}/shop/page/{n}/")
        if not r:
            return []
        s = BeautifulSoup(r.text, "html.parser")
        out = []
        for li in s.select("ul.products li.product"):
            t = li.select_one(".cmsmasters_product_title")
            a = li.select_one("a[href*='/product/']")
            img = li.select_one("img")
            pr = li.select_one(".price ins .amount") or (li.select(".price .amount") or [None])[-1]
            if not (t and a and img):
                continue
            price = parse_price(pr)
            src = img.get("data-src") or img.get("src") or ""
            if price <= 0 or not src or src.startswith("data:"):
                continue
            cats = [c[len("product_cat-"):] for c in li.get("class", []) if c.startswith("product_cat-")]
            out.append({
                "name": re.sub(r"\s+", " ", t.get_text()).strip(),
                "price": price,
                "slug": a["href"].split("/product/")[1].strip("/"),
                "cats": cats,
                "src": src,
            })
        return out

    products = {}
    with ThreadPoolExecutor(4) as ex:
        for n, items in enumerate(ex.map(page, range(1, last + 1)), 1):
            for p in items:
                products.setdefault(p["slug"], p)
            if n % 20 == 0:
                print(f"  page {n}/{last}: {len(products)} products")
    return list(products.values())


# ---------- photos ----------
def cutout(raw):
    im = Image.open(io.BytesIO(raw))
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(bg, im)
    im = im.convert("RGB")
    a = np.asarray(im)
    white = a.min(axis=2) > 236
    lab, _ = ndimage.label(white)
    border = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    border = border[border > 0]
    bgmask = np.isin(lab, border)
    fg = ~bgmask
    ys, xs = np.where(fg)
    if len(xs) == 0:
        return None
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    rgba = np.dstack([a, np.where(bgmask, 0, 255).astype(np.uint8)])[y0:y1, x0:x1]
    piece = Image.fromarray(rgba, "RGBA")
    m = TILE - 10
    k = min(m / piece.width, m / piece.height)
    piece = piece.resize((max(1, round(piece.width * k)), max(1, round(piece.height * k))), Image.LANCZOS)
    return piece


def fetch_photo(p):
    r = get(p["src"])
    if not r:
        big = re.sub(r"-\d+x\d+(\.\w+)$", r"\1", p["src"])
        r = get(big) if big != p["src"] else None
    if not r:
        return None
    try:
        return cutout(r.content)
    except Exception as e:
        print("  bad image", p["slug"], e)
        return None


def main():
    os.makedirs(OUT, exist_ok=True)
    paths, by_slug = load_categories()
    print("categories:", len(paths))
    products = crawl_products()
    print("products found:", len(products))

    # assign each product its most specific real category
    sec_order, sections, cat_index, categories = [], {}, {}, []
    menu_order = list(paths.keys())
    for p in products:
        best = None
        for c in p["cats"]:
            if c in by_slug:
                path, name = by_slug[c]
                score = (c not in CROSS_LISTS, path.count("/"))
                if best is None or score > best[0]:
                    best = (score, path, name)
        if best is None:
            best = ((False, 0), "te-tjera", "Të tjera")
        _, path, name = best
        skey, sname = section_for(path, paths)
        p["skey"], p["sname"], p["path"], p["cname"] = skey, sname, path, name

    def order_key(path):
        return menu_order.index(path) if path in menu_order else len(menu_order)

    products.sort(key=lambda p: (order_key(p["skey"]), order_key(p["path"]), p["name"].lower()))

    # photos (parallel), keep products that have one
    print("downloading photos…")
    with ThreadPoolExecutor(8) as ex:
        photos = list(ex.map(fetch_photo, products))
    kept = [(p, ph) for p, ph in zip(products, photos) if ph is not None]
    print("with photos:", len(kept))

    for f in os.listdir(OUT):
        if f.startswith("sheet_"):
            os.remove(os.path.join(OUT, f))

    out_products = []
    sheet = None
    for i, (p, ph) in enumerate(kept):
        s, t = divmod(i, PER_SHEET)
        if t == 0:
            if sheet is not None:
                sheet.save(f"{OUT}/sheet_{s - 1:03d}.webp", "WEBP", quality=82, method=6)
            sheet = Image.new("RGBA", (TILE * GRID, TILE * GRID), (255, 255, 255, 0))
        cx, cy = (t % GRID) * TILE, (t // GRID) * TILE
        sheet.paste(ph, (cx + (TILE - ph.width) // 2, cy + TILE - ph.height - 4), ph)

        if p["skey"] not in sections:
            sections[p["skey"]] = len(sec_order)
            sec_order.append({"key": p["skey"], "name": p["sname"]})
        if p["path"] not in cat_index:
            cat_index[p["path"]] = len(categories)
            categories.append({"path": p["path"], "name": p["cname"], "section": sections[p["skey"]]})
        out_products.append([p["name"], p["price"], p["slug"], cat_index[p["path"]], s, t])
    if sheet is not None:
        sheet.save(f"{OUT}/sheet_{(len(kept) - 1) // PER_SHEET:03d}.webp", "WEBP", quality=82, method=6)

    data = {
        "source": BASE,
        "updated": time.strftime("%Y-%m-%d"),
        "tile": TILE, "grid": GRID,
        "sheets": (len(kept) + PER_SHEET - 1) // PER_SHEET,
        "sections": sec_order,
        "categories": categories,
        "products": out_products,
    }
    with open(f"{OUT}/catalog.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"done: {len(out_products)} products, {data['sheets']} sheets, {len(sec_order)} sections")


if __name__ == "__main__":
    sys.exit(main())
