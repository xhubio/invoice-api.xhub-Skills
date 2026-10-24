#!/usr/bin/env python3
"""Read and check an e-invoice (ZUGFeRD/Factur-X PDF or XRechnung/CII XML).

Usage:
  python3 read_invoice.py FILE [--format zugferd|xrechnung] [--validate] [--json OUT.json]

- Sends the file to POST /api/v1/invoice/de/{format}/parse. A PDF is read as
  zugferd; an XML is tried as xrechnung first, then as zugferd.
- Prints a short summary (number, dates, parties, totals, lines) plus the
  errors and warnings the service reports for the document.
- --validate additionally checks the extracted data against the format rules
  (POST /api/v1/invoice/de/{format}/validate). This costs one extra call.
- --json writes the extracted invoice data to a file.
Exit code 0 = readable and no errors.
"""
import argparse
import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from invoice_api import load_config, post  # noqa: E402


def parse(cfg, path, fmt):
    body = {"data": base64.b64encode(open(path, "rb").read()).decode(), "filename": os.path.basename(path)}
    return post(cfg, f"/api/v1/invoice/de/{fmt}/parse", body)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--format", choices=["zugferd", "xrechnung"])
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    cfg = load_config()

    if a.format:
        tries = [a.format]
    elif a.file.lower().endswith(".pdf"):
        tries = ["zugferd"]
    else:
        tries = ["xrechnung", "zugferd"]
    status, resp, used = None, {}, None
    for fmt in tries:
        status, resp = parse(cfg, a.file, fmt)
        used = fmt
        if status == 200 and resp.get("success"):
            break

    inv = resp.get("invoice") or {}
    out = {
        "ok": status == 200 and bool(resp.get("success")) and not resp.get("errors"),
        "http": status, "parsedAs": used, "detectedFormat": resp.get("format"),
        "invoiceNumber": inv.get("invoiceNumber"), "type": inv.get("type"),
        "issueDate": inv.get("issueDate"), "dueDate": inv.get("dueDate"),
        "seller": (inv.get("seller") or {}).get("name"), "buyer": (inv.get("buyer") or {}).get("name"),
        "currency": inv.get("currency"), "subtotal": inv.get("subtotal"), "total": inv.get("total"),
        "taxSummary": inv.get("taxSummary"),
        "lines": [{"pos": i.get("position"), "description": i.get("description"), "quantity": i.get("quantity"),
                   "unitPrice": i.get("unitPrice"), "netAmount": i.get("netAmount"), "taxRate": i.get("taxRate")}
                  for i in inv.get("items") or []],
        "errors": resp.get("errors"), "warnings": resp.get("warnings"), "infos": resp.get("infos"),
    }
    if not inv and status != 200:
        out["response"] = resp
    if a.validate and inv:
        vs, vr = post(cfg, f"/api/v1/invoice/de/{used}/validate", {"invoice": inv})
        out["validate"] = {"http": vs, "status": vr.get("status"), "valid": vr.get("valid"),
                           "failed": [r for r in vr.get("results", []) if r.get("valid") is False]}
        out["ok"] = out["ok"] and vs == 200 and vr.get("valid") is not False
    if a.json and inv:
        json.dump(inv, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    sys.exit(0 if out["ok"] else 1)


if __name__ == "__main__":
    main()
