#!/usr/bin/env python3
"""Measure an existing invoice PDF so a template can be rebuilt from facts, not guesses.

Usage:
  python3 analyze_pdf.py ORIGINAL.pdf --out analysis/ [--page 1] [--dpi 110]

Writes:
  analysis/analysis.json   page size, content box, text lines (x, y, size, font,
                           bold, colour), filled areas and rules (colour, box),
                           images, colour palette, font-size histogram
  analysis/page-N.png      the page as image, to look at
  analysis/assets/*.png    every embedded image (logo etc.) cut out at 300 dpi
Units are PDF points (1 pt = 1/72 inch), origin top-left, like the template.
Requires: pip install pdfplumber pillow
"""
import argparse
import collections
import json
import os
import sys

try:
    import pdfplumber
except ImportError:
    sys.exit("Missing dependency: pip install pdfplumber pillow")


def hexcolor(c):
    if c is None:
        return None
    if isinstance(c, (int, float)):
        c = (c,)
    c = [float(x) for x in c if isinstance(x, (int, float))]
    if len(c) == 1:
        r = g = b = c[0]
    elif len(c) == 3:
        r, g, b = c
    elif len(c) == 4:  # CMYK
        k = c[3]
        r, g, b = [(1 - x) * (1 - k) for x in c[:3]]
    else:
        return None
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(v * 255))) for v in (r, g, b))


def lines_from_words(words):
    """Group words that share baseline, font and size into text lines."""
    words = sorted(words, key=lambda w: (round(w["top"], 0), w["x0"]))
    out = []
    for w in words:
        key = (w.get("fontname"), round(w.get("size", 0), 1), hexcolor(w.get("non_stroking_color")))
        last = out[-1] if out else None
        if (last and abs(last["top"] - w["top"]) < 1.5 and last["_key"] == key
                and w["x0"] - last["x1"] < max(3.5, w["size"] * 0.6)):
            gap = " " if w["x0"] - last["x1"] > w["size"] * 0.15 else ""
            last["text"] += gap + w["text"]
            last["x1"] = w["x1"]
            last["bottom"] = max(last["bottom"], w["bottom"])
        else:
            out.append({"_key": key, "text": w["text"], "x0": w["x0"], "x1": w["x1"], "top": w["top"],
                        "bottom": w["bottom"], "size": round(w.get("size", 0), 2), "font": w.get("fontname"),
                        "color": key[2]})
    for l in out:
        font = (l["font"] or "").lower()
        l["bold"] = any(s in font for s in ("bold", "black", "heavy", "semibold", "demi"))
        l["font"] = (l["font"] or "").split("+")[-1]
        for k in ("x0", "x1", "top", "bottom"):
            l[k] = round(l[k], 1)
        del l["_key"]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("--out", default="analysis")
    ap.add_argument("--page", type=int, default=1)
    ap.add_argument("--dpi", type=int, default=110)
    a = ap.parse_args()
    os.makedirs(os.path.join(a.out, "assets"), exist_ok=True)

    with pdfplumber.open(a.pdf) as pdf:
        res = {"file": os.path.basename(a.pdf), "pages": len(pdf.pages), "analysedPage": a.page}
        p = pdf.pages[a.page - 1]
        res["pageSize"] = {"width": round(p.width, 2), "height": round(p.height, 2),
                           "format": "A4" if abs(p.width - 595.3) < 2 and abs(p.height - 841.9) < 2 else "custom"}
        words = p.extract_words(extra_attrs=["fontname", "size", "non_stroking_color"], keep_blank_chars=False,
                                use_text_flow=False)
        lines = lines_from_words(words)
        res["textLines"] = lines

        areas, rules = [], []
        for r in p.rects:
            w, h = r["x1"] - r["x0"], r["bottom"] - r["top"]
            fill = hexcolor(r.get("non_stroking_color")) if r.get("fill") else None
            stroke = hexcolor(r.get("stroking_color")) if r.get("stroke") else None
            item = {"x0": round(r["x0"], 1), "top": round(r["top"], 1), "width": round(w, 1), "height": round(h, 1),
                    "fill": fill, "stroke": stroke}
            (rules if min(w, h) <= 2.5 else areas).append(item)
        for l in p.lines:
            rules.append({"x0": round(l["x0"], 1), "top": round(l["top"], 1), "width": round(l["x1"] - l["x0"], 1),
                          "height": round(l["bottom"] - l["top"], 1), "stroke": hexcolor(l.get("stroking_color")),
                          "lineWidth": l.get("linewidth")})
        res["filledAreas"] = [x for x in areas if x["fill"] and x["fill"] != "#FFFFFF"]
        res["rules"] = rules

        page_img = p.to_image(resolution=a.dpi)
        page_img.save(os.path.join(a.out, f"page-{a.page}.png"))
        hi = p.to_image(resolution=300)
        imgs = []
        for i, im in enumerate(p.images, 1):
            box = (max(0, im["x0"]), max(0, im["top"]), min(p.width, im["x1"]), min(p.height, im["bottom"]))
            if box[2] - box[0] < 2 or box[3] - box[1] < 2:
                continue
            f = os.path.join(a.out, "assets", f"image-{i}.png")
            p.crop(box).to_image(resolution=300).save(f)
            imgs.append({"file": f, "x0": round(box[0], 1), "top": round(box[1], 1),
                         "width": round(box[2] - box[0], 1), "height": round(box[3] - box[1], 1)})
        res["images"] = imgs

        xs = [l["x0"] for l in lines] + [i["x0"] for i in imgs]
        x1s = [l["x1"] for l in lines] + [i["x0"] + i["width"] for i in imgs]
        ts = [l["top"] for l in lines] + [i["top"] for i in imgs]
        bs = [l["bottom"] for l in lines] + [i["top"] + i["height"] for i in imgs]
        if xs:
            res["contentBox"] = {"left": round(min(xs), 1), "right": round(p.width - max(x1s), 1),
                                 "top": round(min(ts), 1), "bottom": round(p.height - max(bs), 1),
                                 "note": "distance of outermost content to the page edge; header/footer included"}
        res["palette"] = collections.Counter([l["color"] for l in lines] + [x["fill"] for x in areas if x["fill"]]
                                             + [x["stroke"] for x in rules if x.get("stroke")]).most_common(12)
        res["fontSizes"] = collections.Counter(round(l["size"], 1) for l in lines).most_common()
        res["fonts"] = collections.Counter(l["font"] for l in lines).most_common()

    json.dump(res, open(os.path.join(a.out, "analysis.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"analysis": os.path.join(a.out, "analysis.json"), "pageImage": os.path.join(a.out, f"page-{a.page}.png"),
                      "pageSize": res["pageSize"], "contentBox": res.get("contentBox"), "textLines": len(lines),
                      "images": [i["file"] for i in imgs], "fonts": res["fonts"], "fontSizes": res["fontSizes"][:10],
                      "palette": res["palette"]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
