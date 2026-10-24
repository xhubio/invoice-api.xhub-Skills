#!/usr/bin/env python3
"""Render a BlockTemplate through invoice-api.xhub.io and compare it with the original PDF.

Usage:
  python3 render_check.py TEMPLATE.json --invoice SAMPLE.json --out check/
         [--original ORIGINAL.pdf] [--variant full|minimal|long] [--format zugferd|pdf]

- Sends the template inline (formatOptions.template), so nothing has to be
  saved in the console first. One API call per run.
- --variant minimal removes optional fields (delivery date, order number,
  customer number, buyer VAT ID, contact, notes); long repeats lines to 30
  positions to test page breaks and repeated header/footer.
- With --original: writes side-by-side.png (original | render), overlay.png
  (original red, render blue; dark = identical) and a text comparison:
  every text line of the original is searched in the render and dx/dy/size
  differences are reported. Use a SAMPLE built from the original's data, so
  the texts are identical.
Requires: pip install pdfplumber pillow
"""
import argparse
import base64
import copy
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from invoice_api import load_config, post, strip_binary  # noqa: E402

try:
    import pdfplumber
    from PIL import Image, ImageChops, ImageOps
except ImportError:
    sys.exit("Missing dependency: pip install pdfplumber pillow")
from analyze_pdf import lines_from_words  # noqa: E402

OPTIONAL = ["deliveryDate", "orderNumber", "customerNumber", "notes", "servicePeriod", "contractNumber", "projectNumber"]


def variant(inv, name):
    inv = copy.deepcopy(inv)
    if name == "minimal":
        for k in OPTIONAL:
            inv.pop(k, None)
        for k in ("vatId", "contact", "additionalStreet", "email", "phone"):
            inv.get("buyer", {}).pop(k, None)
    elif name == "long":
        base = inv["items"]
        items = []
        for i in range(30):
            it = copy.deepcopy(base[i % len(base)])
            it["position"] = i + 1
            items.append(it)
        inv["items"] = items
        net = round(sum(i["netAmount"] for i in items), 2)
        groups = {}
        for i in items:
            groups.setdefault((i.get("taxCategoryCode", "S"), i.get("taxRate", 0)), 0)
            groups[(i.get("taxCategoryCode", "S"), i.get("taxRate", 0))] += i["netAmount"]
        inv["taxSummary"] = [{"taxCategoryCode": c, "taxRate": r, "netAmount": round(n, 2),
                              "taxAmount": round(round(n, 2) * r / 100 + 1e-9, 2)} for (c, r), n in groups.items()]
        inv["subtotal"] = net
        inv["total"] = round(net + sum(t["taxAmount"] for t in inv["taxSummary"]), 2)
    return inv


def text_lines(pdf_path, page_no):
    with pdfplumber.open(pdf_path) as pdf:
        p = pdf.pages[page_no - 1]
        return lines_from_words(p.extract_words(extra_attrs=["fontname", "size", "non_stroking_color"])), len(pdf.pages)


def raster(pdf_path, page_no, dpi):
    with pdfplumber.open(pdf_path) as pdf:
        return pdf.pages[page_no - 1].to_image(resolution=dpi).original.convert("RGB")


def norm(s):
    return " ".join(s.replace(" ", " ").split()).lower()


def compare(orig, rend):
    """Match each original line to the nearest render line with the same text.
    Short texts (< 4 chars) only match within 40 pt; partial matches need >= 8 chars."""
    pool = list(rend)
    rows, missing = [], []

    def dist(o, r):
        return abs(r["x0"] - o["x0"]) + abs(r["top"] - o["top"])

    for o in sorted(orig, key=lambda l: -len(l["text"])):
        t = norm(o["text"])
        cands = [r for r in pool if norm(r["text"]) == t]
        if not cands and len(t) >= 8:
            cands = [r for r in pool if len(norm(r["text"])) >= 8 and (t in norm(r["text"]) or norm(r["text"]) in t)]
        if len(t) < 4:
            cands = [r for r in cands if dist(o, r) < 40]
        if not cands:
            missing.append({"text": o["text"], "x0": o["x0"], "top": o["top"], "size": o["size"]})
            continue
        hit = min(cands, key=lambda r: dist(o, r))
        pool.remove(hit)
        rows.append({"text": o["text"][:60], "x0": o["x0"], "top": o["top"], "dx": round(hit["x0"] - o["x0"], 1),
                     "dy": round(hit["top"] - o["top"], 1), "dSize": round(hit["size"] - o["size"], 2),
                     "boldMatches": hit["bold"] == o["bold"],
                     "color": [o["color"], hit["color"]] if o["color"] != hit["color"] else None})
    rows.sort(key=lambda r: (r["top"], r["x0"]))
    worst = sorted(rows, key=lambda r: -(abs(r["dx"]) + abs(r["dy"]) + 10 * abs(r["dSize"])))[:15]
    return {
        "matched": len(rows), "originalLines": len(orig),
        "medianAbsDx": round(statistics.median([abs(r["dx"]) for r in rows]), 1) if rows else None,
        "medianAbsDy": round(statistics.median([abs(r["dy"]) for r in rows]), 1) if rows else None,
        "sizeMismatches": sum(1 for r in rows if abs(r["dSize"]) > 0.3),
        "boldMismatches": sum(1 for r in rows if not r["boldMatches"]),
        "colorMismatches": sum(1 for r in rows if r["color"]),
        "byLine": rows, "worst": worst,
        "missingInRender": sorted(missing, key=lambda m: m["top"])[:40],
        "extraInRender": [{"text": r["text"], "x0": r["x0"], "top": r["top"]} for r in sorted(pool, key=lambda r: r["top"])][:40],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("template")
    ap.add_argument("--invoice", required=True)
    ap.add_argument("--out", default="check")
    ap.add_argument("--original")
    ap.add_argument("--variant", default="full", choices=["full", "minimal", "long"])
    ap.add_argument("--format", default="zugferd", choices=["zugferd", "facturx", "pdf"])
    ap.add_argument("--page", type=int, default=1)
    ap.add_argument("--dpi", type=int, default=100)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    cfg = load_config()
    tpl = json.load(open(a.template, encoding="utf-8"))
    tpl.pop("samplePayload", None)
    inv = json.load(open(a.invoice, encoding="utf-8"))
    inv = variant(inv.get("invoice", inv), a.variant)
    status, resp = post(cfg, f"/api/v1/invoice/de/{a.format}/generate",
                        {"invoice": inv, "validate": a.format != "pdf", "formatOptions": {"template": tpl}})
    report = {"variant": a.variant, "http": status, "response": strip_binary(resp)}
    if status != 200 or not resp.get("data"):
        json.dump(report, open(os.path.join(a.out, "report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(json.dumps({"ok": False, "http": status, "errors": resp.get("errors") or resp.get("complianceErrors") or resp},
                         ensure_ascii=False, indent=1)[:4000])
        sys.exit(1)
    rpdf = os.path.join(a.out, f"render-{a.variant}.pdf")
    open(rpdf, "wb").write(base64.b64decode(resp["data"]))
    rlines, rpages = text_lines(rpdf, a.page)
    report.update({"render": rpdf, "renderPages": rpages})
    for n in range(1, rpages + 1):
        raster(rpdf, n, a.dpi).save(os.path.join(a.out, f"render-{a.variant}-p{n}.png"))

    if a.original:
        o_img, r_img = raster(a.original, a.page, a.dpi), raster(rpdf, a.page, a.dpi)
        r_img = r_img.resize(o_img.size)
        side = Image.new("RGB", (o_img.width * 2 + 20, o_img.height), "white")
        side.paste(o_img, (0, 0)); side.paste(r_img, (o_img.width + 20, 0))
        side.save(os.path.join(a.out, "side-by-side.png"))
        og, rg = ImageOps.grayscale(o_img), ImageOps.grayscale(r_img)
        Image.merge("RGB", (rg, og, og)).save(os.path.join(a.out, "overlay.png"))
        diff = ImageChops.difference(og, rg).point(lambda v: 255 if v > 60 else 0)
        report["pixelDiffShare"] = round(sum(diff.histogram()[255:]) / (diff.width * diff.height), 4)
        olines, _ = text_lines(a.original, a.page)
        report["textComparison"] = compare(olines, rlines)

    json.dump(report, open(os.path.join(a.out, f"report-{a.variant}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    val = resp.get("validation") or {}
    summary = {"ok": True, "variant": a.variant, "render": rpdf, "pages": rpages, "validation": val.get("status"),
               "warnings": resp.get("warnings"), "report": os.path.join(a.out, f"report-{a.variant}.json")}
    if a.original:
        tc = report["textComparison"]
        summary.update({"sideBySide": os.path.join(a.out, "side-by-side.png"), "overlay": os.path.join(a.out, "overlay.png"),
                        "pixelDiffShare": report["pixelDiffShare"],
                        **{k: tc[k] for k in ("matched", "originalLines", "medianAbsDx", "medianAbsDy", "sizeMismatches",
                                              "boldMismatches", "colorMismatches")},
                        "worst": tc["worst"][:8], "missingInRender": tc["missingInRender"][:12],
                        "extraInRender": tc["extraInRender"][:12]})
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
