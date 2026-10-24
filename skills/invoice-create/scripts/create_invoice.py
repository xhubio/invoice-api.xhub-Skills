#!/usr/bin/env python3
"""Create an e-invoice with invoice-api.xhub.io and check the result.

Usage:
  python3 create_invoice.py INVOICE.json [--country de] [--format zugferd]
                            [--out DIR] [--template-id UUID] [--no-compute]

Steps:
  1. Compute line amounts, tax summary and totals from quantity, unitPrice and
     taxRate (the API never calculates amounts). Skip with --no-compute.
  2. Run local checks for known pitfalls (dates, negative prices, BT-10/BT-13).
  3. POST /api/v1/invoice/{country}/{format}/generate with validate=true.
  4. Save the document; for zugferd/xrechnung read it back with /parse and
     compare number and totals.
  5. Write <number>.report.json next to the document.
Exit code 0 = document created and all checks passed.
"""
import argparse
import base64
import json
import os
import re
import sys
from decimal import ROUND_HALF_UP, Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from invoice_api import load_config, post, strip_binary  # noqa: E402

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CENT = Decimal("0.01")


def money(x):
    return Decimal(str(x)).quantize(CENT, rounding=ROUND_HALF_UP)


def compute(inv):
    """Fill netAmount/taxAmount/grossAmount per line, taxSummary, subtotal, total."""
    groups = {}
    for i, it in enumerate(inv["items"], 1):
        it.setdefault("position", i)
        rate = Decimal(str(it.get("taxRate", 0)))
        cat = it.get("taxCategoryCode") or ("S" if rate > 0 else "E")
        it["taxCategoryCode"] = cat
        net = money(Decimal(str(it["quantity"])) * Decimal(str(it["unitPrice"])))
        tax = money(net * rate / 100)
        it["netAmount"], it["taxAmount"], it["grossAmount"] = float(net), float(tax), float(net + tax)
        g = groups.setdefault((cat, rate), {"net": Decimal(0), "reason": it.get("taxExemptionReason")})
        g["net"] += net
    summary, subtotal, taxsum = [], Decimal(0), Decimal(0)
    for (cat, rate), g in groups.items():
        tax = money(g["net"] * rate / 100)  # tax per rate on the summed net (EN 16931)
        row = {"taxRate": float(rate), "taxCategoryCode": cat, "netAmount": float(g["net"]), "taxAmount": float(tax)}
        if g["reason"]:
            row["exemptionReason"] = g["reason"]
        summary.append(row)
        subtotal += g["net"]
        taxsum += tax
    inv["taxSummary"], inv["subtotal"], inv["total"] = summary, float(subtotal), float(subtotal + taxsum)
    return inv


def precheck(inv):
    problems = []
    for f in ("issueDate", "dueDate", "deliveryDate"):
        if inv.get(f) and not DATE.match(str(inv[f])):
            problems.append(f"{f} must be YYYY-MM-DD, got {inv[f]!r}")
    sp = inv.get("servicePeriod") or {}
    for f in ("start", "end"):
        if sp.get(f) and not DATE.match(str(sp[f])):
            problems.append(f"servicePeriod.{f} must be YYYY-MM-DD")
    for it in inv.get("items", []):
        if Decimal(str(it.get("unitPrice", 0))) < 0:
            problems.append(
                f"item {it.get('position')}: negative unitPrice is not allowed (BR-27). "
                "Use a negative quantity or an allowance instead."
            )
    buyer_name = (inv.get("buyer") or {}).get("name", "").strip().lower()
    ref = ((inv.get("countrySpecific") or {}).get("buyerReference") or "").strip().lower()
    if ref and ref == buyer_name:
        problems.append("countrySpecific.buyerReference (BT-10) equals the buyer name - use a reference the buyer gave you, or leave it out")
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("invoice")
    ap.add_argument("--country", default="de")
    ap.add_argument("--format", default="zugferd")
    ap.add_argument("--out", default=".")
    ap.add_argument("--template-id")
    ap.add_argument("--no-compute", action="store_true")
    a = ap.parse_args()

    cfg = load_config()
    inv = json.load(open(a.invoice, encoding="utf-8"))
    inv = inv.get("invoice", inv)
    if not a.no_compute:
        compute(inv)
    problems = precheck(inv)
    if problems:
        print("Fix before generating:\n- " + "\n- ".join(problems))
        sys.exit(2)

    body = {"invoice": inv, "validate": True}
    tpl = a.template_id or cfg.get("INVOICE_XHUB_TEMPLATE_ID")
    if tpl and a.format in ("pdf", "zugferd", "facturx"):
        body["templateId"] = tpl
    status, resp = post(cfg, f"/api/v1/invoice/{a.country}/{a.format}/generate", body)
    report = {"request": {"country": a.country, "format": a.format, "templateId": bool(tpl)},
              "invoice": inv, "generate": {"http": status, **strip_binary(resp)}}
    os.makedirs(a.out, exist_ok=True)
    nr = re.sub(r"[^A-Za-z0-9._-]", "_", inv["invoiceNumber"])
    ok = status == 200 and resp.get("success")
    if ok:
        ext = ".pdf" if "pdf" in (resp.get("mimeType") or "") else ".xml"
        doc = os.path.join(a.out, nr + ext)
        open(doc, "wb").write(base64.b64decode(resp["data"]))
        json.dump(inv, open(os.path.join(a.out, nr + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        report["document"] = doc
        if a.country == "de" and a.format in ("zugferd", "xrechnung"):
            ps, pr = post(cfg, f"/api/v1/invoice/de/{a.format}/parse",
                          {"data": base64.b64encode(open(doc, "rb").read()).decode(), "filename": os.path.basename(doc)})
            back = (pr or {}).get("invoice") or {}
            same = (back.get("invoiceNumber") == inv["invoiceNumber"]
                    and money(back.get("total", 0)) == money(inv["total"])
                    and money(back.get("subtotal", 0)) == money(inv["subtotal"]))
            report["readBack"] = {"http": ps, "format": pr.get("format"), "errors": pr.get("errors"),
                                  "warnings": pr.get("warnings"), "matches": same}
            ok = ok and ps == 200 and not pr.get("errors") and same
    json.dump(report, open(os.path.join(a.out, nr + ".report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    val = (resp.get("validation") or {}) if isinstance(resp, dict) else {}
    print(json.dumps({
        "ok": bool(ok), "http": status, "document": report.get("document"),
        "subtotal": inv["subtotal"], "total": inv["total"],
        "validation": val.get("status"),
        "errors": resp.get("complianceErrors") or val.get("errors") or resp.get("errors"),
        "warnings": resp.get("warnings"),
        "readBack": report.get("readBack"),
        "report": os.path.join(a.out, nr + ".report.json"),
    }, ensure_ascii=False, indent=1))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
