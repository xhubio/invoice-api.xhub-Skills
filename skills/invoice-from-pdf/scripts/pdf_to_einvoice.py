#!/usr/bin/env python3
"""Turn an existing PDF invoice (from Word, Excel, an ERP) into an e-invoice.

Claude reads the PDF text; this script makes that read auditable. Every value
Claude takes from the PDF must come with a verbatim quote, and the script checks
that the quote is in the PDF and says what the value says. Then it recomputes
the totals and compares them with the printed ones. Only then does it generate.

Usage:
  python3 pdf_to_einvoice.py extract INVOICE.pdf --out work/
  python3 pdf_to_einvoice.py check work/extracted.json --extract work/extract.json
                             [--format zugferd] [--seller invoice-seller.json]
                             [--customers invoice-customers.json] [--log e-invoices/log.jsonl]
                             [--out work/checked.json]
  python3 pdf_to_einvoice.py remember customer "Beispiel Kunde AG" --set email=ap@example.org
                             [--set leitwegId=none] [--file invoice-customers.json] [--replace]
  python3 pdf_to_einvoice.py remember seller --set bankAccount.iban=DE02... [--file invoice-seller.json]
  python3 pdf_to_einvoice.py generate work/checked.json [--out e-invoices]
                             [--log e-invoices/log.jsonl] [--template-id UUID]

extract   writes extract.json (sha256, text per page, scan detection) and text.txt.
          Exit 3 = no text layer (scan); this script does no OCR.
check     offline, no API call. Writes checked.json with the assembled invoice,
          checks[] (severity error|warning), ok, and ask[]: master data that is
          missing (seller profile, buyer e-mail, Leitweg-ID). Exit 0 = ok, 1 = errors.
remember  saves what the user answered to ask[], validated (e-mail, IBAN, BIC,
          VAT ID, Leitweg-ID check digits). Never overwrites without --replace.
generate  only from a checked.json with ok=true. One generate call with
          validate=true, read-back for zugferd/xrechnung, one log line.
          Exit 0 = created and read back.
Only `generate` needs INVOICE_XHUB_API_KEY.
"""
import argparse
import base64
import calendar
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CENT = Decimal("0.01")
TOLERANCE = Decimal("0.02")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SCAN_CHARS_PER_PAGE = 30
# EU AI Act Art. 50: the data was read by an AI; it stays a proposal until the user confirms
AI_NOTE = "read by AI (Claude) from the PDF text, every value quote-checked, totals recomputed; generated after user confirmation"
# Code fields: the PDF shows a word ("Stk", "Gutschrift", "€"), the invoice a code.
# The quote must exist; the mapping word -> code is the reader's job.
CODE_FIELDS = {"type", "unit", "currency", "countryCode", "taxCategoryCode"}
CREDIT_WORDS = ("gutschrift", "credit note", "rechnungskorrektur", "korrekturrechnung", "storno", "avoir", "creditnota")
MONTHS = {
    "januar": 1, "jänner": 1, "january": 1, "jan": 1, "februar": 2, "february": 2, "feb": 2,
    "märz": 3, "maerz": 3, "march": 3, "mar": 3, "mär": 3, "april": 4, "apr": 4, "mai": 5, "may": 5,
    "juni": 6, "june": 6, "jun": 6, "juli": 7, "july": 7, "jul": 7, "august": 8, "aug": 8,
    "september": 9, "sept": 9, "sep": 9, "oktober": 10, "october": 10, "okt": 10, "oct": 10,
    "november": 11, "nov": 11, "dezember": 12, "december": 12, "dez": 12, "dec": 12,
}


# ── helpers ────────────────────────────────────────────────────────────────

def money(x):
    return Decimal(str(x)).quantize(CENT, rounding=ROUND_HALF_UP)


def norm(s):
    """Text normalisation used on both sides of every quote comparison."""
    s = unicodedata.normalize("NFKC", str(s)).replace("­", "")
    for a, b in (("‐", "-"), ("‑", "-"), ("‒", "-"), ("–", "-"), ("—", "-"), ("−", "-"),
                 ("“", '"'), ("”", '"'), ("„", '"'), ("‘", "'"), ("’", "'"), ("‚", "'")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip().lower()


def canonical_json(obj):
    """JSON like the API's payloadHash: keys sorted recursively, JS number format."""
    def fix(o):
        if isinstance(o, dict):
            return {k: fix(v) for k, v in o.items() if v is not None}
        if isinstance(o, list):
            return [fix(v) for v in o]
        if isinstance(o, float) and o.is_integer():
            return int(o)
        return o
    return json.dumps(fix(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def payload_hash(inv):
    return hashlib.sha256(canonical_json(inv).encode("utf-8")).hexdigest()


def drop_none(o):
    if isinstance(o, dict):
        return {k: drop_none(v) for k, v in o.items() if v is not None}
    if isinstance(o, list):
        return [drop_none(v) for v in o]
    return o


def leaves(o, prefix=""):
    """Yield (path, value) for every scalar, paths like items[0].unitPrice."""
    if isinstance(o, dict):
        for k, v in o.items():
            yield from leaves(v, f"{prefix}.{k}" if prefix else k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from leaves(v, f"{prefix}[{i}]")
    else:
        yield prefix, o


def numbers_in(quote):
    """Every number a quote can mean, German and English notation."""
    out = set()
    for tok in re.findall(r"\d+(?:[.,'  ]\d+)*", quote):
        tok = tok.replace("'", "").replace(" ", "").replace(" ", "")
        cands = []
        if "." in tok and "," in tok:
            dec = "," if tok.rfind(",") > tok.rfind(".") else "."
            thou = "." if dec == "," else ","
            cands.append(tok.replace(thou, "").replace(dec, "."))
        elif "," in tok or "." in tok:
            sep = "," if "," in tok else "."
            parts = tok.split(sep)
            if len(parts) == 2:
                cands.append(tok.replace(sep, "."))
            if all(len(p) == 3 for p in parts[1:]):
                cands.append(tok.replace(sep, ""))
        else:
            cands.append(tok)
        for c in cands:
            try:
                out.add(Decimal(c))
            except InvalidOperation:
                pass
    return out


def dates_in(quote):
    """(set of exact ISO dates, set of (year, month) mentioned without a day)."""
    q = norm(quote)
    exact, months = set(), set()

    def add(y, m, d):
        y = int(y)
        y = y + 2000 if y < 100 else y
        try:
            exact.add(datetime.date(y, int(m), int(d)).isoformat())
        except ValueError:
            pass

    for y, m, d in re.findall(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", q):
        add(y, m, d)
    for d, m, y in re.findall(r"\b(\d{1,2})[./](\d{1,2})[./](\d{4}|\d{2})\b", q):
        add(y, m, d)
    years = re.findall(r"\b(20\d{2})\b", q)
    for d, m in re.findall(r"\b(\d{1,2})\.(\d{1,2})\.(?!\d)", q):  # 01.07.-31.07.2026
        for y in years:
            add(y, m, d)
    names = "|".join(sorted(MONTHS, key=len, reverse=True))
    for d, mn, y in re.findall(rf"\b(\d{{1,2}})\.?\s*({names})\.?\s+(\d{{4}})\b", q):
        add(y, MONTHS[mn], d)
    for mn, d, y in re.findall(rf"\b({names})\.?\s+(\d{{1,2}}),?\s+(\d{{4}})\b", q):
        add(y, MONTHS[mn], d)
    for mn, y in re.findall(rf"\b({names})\.?\s+(\d{{4}})\b", q):
        months.add((int(y), MONTHS[mn]))
    for m, y in re.findall(r"\b(\d{1,2})/(\d{4})\b", q):
        if 1 <= int(m) <= 12:
            months.add((int(y), int(m)))
    return exact, months


def value_matches_quote(path, value, quote):
    """None if the quote supports the value, else a reason."""
    field = path.rsplit(".", 1)[-1].split("[")[0]
    if field in CODE_FIELDS:
        if field == "type" and value in ("credit_note", "correction") and not any(w in norm(quote) for w in CREDIT_WORDS):
            return f"type {value!r} needs a quote that names the document a credit note/correction"
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if abs(Decimal(str(value))) in {abs(n) for n in numbers_in(quote)}:
            return None
        return f"{value} does not appear as a number in the quote"
    s = str(value)
    if ISO_DATE.match(s):
        exact, months = dates_in(quote)
        if s in exact:
            return None
        d = datetime.date.fromisoformat(s)
        last = calendar.monthrange(d.year, d.month)[1]
        if (d.year, d.month) in months and (d.day == 1 or d.day == last):
            return None
        return f"date {s} does not appear in the quote"
    if norm(s) in norm(quote) or norm(s).replace(" ", "") in norm(quote).replace(" ", ""):
        return None
    return f"{s!r} does not appear in the quote"


def compute(inv):
    """Line amounts, tax summary and totals - same rules as invoice-create."""
    groups = {}
    for i, it in enumerate(inv["items"], 1):
        it["position"] = i
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


def load_json(path, what):
    if not path or not os.path.exists(path):
        return None
    try:
        return json.load(open(path, encoding="utf-8"))
    except ValueError as e:
        raise SystemExit(f"{what} {path} is not valid JSON: {e}")


def read_log(path):
    rows = []
    if path and os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    pass
    return rows


def customer_key(name):
    return re.sub(r"\s+", " ", str(name or "")).strip().lower()


def get_path(obj, path):
    for part in path.split("."):
        if not isinstance(obj, dict) or obj.get(part) in (None, ""):
            return None
        obj = obj[part]
    return obj


def has_path(obj, path):
    *parents, last = path.split(".")
    for part in parents:
        if not isinstance(obj, dict) or not isinstance(obj.get(part), dict):
            return False
        obj = obj[part]
    return isinstance(obj, dict) and last in obj


# ── extract ────────────────────────────────────────────────────────────────

def extract_pages(pdf):
    try:
        import pdfplumber
        with pdfplumber.open(pdf) as doc:
            return "pdfplumber", [p.extract_text() or "" for p in doc.pages]
    except ImportError:
        pass
    if shutil.which("pdftotext"):
        out = subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", pdf, "-"], capture_output=True, check=True)
        pages = out.stdout.decode("utf-8", "replace").split("\f")
        if pages and not pages[-1].strip():
            pages = pages[:-1]
        return "pdftotext", pages
    raise SystemExit("No PDF text extractor found: pip install pdfplumber (or install poppler for pdftotext).")


def cmd_extract(a):
    raw = open(a.pdf, "rb").read()
    if not raw.startswith(b"%PDF"):
        raise SystemExit(f"{a.pdf} is not a PDF file.")
    engine, pages = extract_pages(a.pdf)
    chars = [len(re.sub(r"\s", "", p)) for p in pages]
    scanned = not pages or all(c < SCAN_CHARS_PER_PAGE for c in chars)
    os.makedirs(a.out, exist_ok=True)
    res = {
        "file": os.path.basename(a.pdf),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "engine": engine,
        "pageCount": len(pages),
        "charsPerPage": chars,
        "isLikelyScanned": scanned,
        "pages": pages,
    }
    json.dump(res, open(os.path.join(a.out, "extract.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(os.path.join(a.out, "text.txt"), "w", encoding="utf-8") as f:
        for i, p in enumerate(pages, 1):
            f.write(f"===== page {i} =====\n{p}\n")
    print(json.dumps({**{k: v for k, v in res.items() if k != "pages"},
        "text": os.path.join(a.out, "text.txt"),
        "hint": "scanned PDF without text layer - rejected, no OCR" if scanned else "read text.txt and write extracted.json"},
        ensure_ascii=False, indent=1))
    sys.exit(3 if scanned else 0)


# ── check ──────────────────────────────────────────────────────────────────

class Checks:
    def __init__(self):
        self.items = []

    def error(self, code, msg, field=None):
        self.items.append({"severity": "error", "code": code, "message": msg, **({"field": field} if field else {})})

    def warn(self, code, msg, field=None):
        self.items.append({"severity": "warning", "code": code, "message": msg, **({"field": field} if field else {})})

    @property
    def ok(self):
        return not any(c["severity"] == "error" for c in self.items)


def check_provenance(c, inv, evidence, defaults, text_variants):
    """Every value from the PDF has a quote that is in the PDF and supports it."""
    for path, value in leaves(inv):
        if value is None or value == "":
            continue
        if path in defaults:
            continue
        quote = evidence.get(path)
        if quote is None:
            c.error("NO_EVIDENCE", f"{path} = {value!r} has neither a quote from the PDF nor a reason in defaults", path)
            continue
        nq = norm(quote)
        if not nq or not any(nq in t or nq.replace("- ", "") in t for t in text_variants):
            c.error("QUOTE_NOT_IN_PDF", f"quote for {path} is not in the PDF text: {quote!r}", path)
            continue
        why = value_matches_quote(path, value, quote)
        if why:
            c.error("VALUE_NOT_IN_QUOTE", f"{path}: {why} ({quote!r})", path)
        elif (isinstance(value, (int, float)) and not isinstance(value, bool) or ISO_DATE.match(str(value))) \
                and not re.search(r"[^\W\d_]", nq):
            # "14.07.2026" alone could be the issue date or the due date: quote the label too
            c.warn("QUOTE_WITHOUT_LABEL", f"quote for {path} carries no label, only {quote!r}", path)
    for path in evidence:
        if path not in dict(leaves(inv)):
            c.warn("EVIDENCE_UNUSED", f"quote for {path} has no value in the invoice", path)


def cmd_check(a):
    c = Checks()
    ext = load_json(a.extract, "extract")
    if ext is None:
        raise SystemExit(f"{a.extract} not found - run `extract` first.")
    data = load_json(a.extracted, "extracted")
    if data is None:
        raise SystemExit(f"{a.extracted} not found.")
    if ext.get("isLikelyScanned"):
        c.error("SCANNED_PDF", "the PDF has no text layer (scan); not read, no OCR")
    src = data.get("source") or {}
    if src.get("sha256") != ext["sha256"]:
        c.error("SOURCE_MISMATCH", "extracted.json source.sha256 does not match the extracted PDF")

    doc = data.get("invoice") or {}
    evidence = data.get("evidence") or {}
    defaults = data.get("defaults") or {}
    text = "\n".join(ext["pages"])
    t = norm(text)
    text_variants = [t, re.sub(r"(\w)- (\w)", r"\1\2", t)]  # hyphenation at line breaks

    check_provenance(c, doc, evidence, defaults, text_variants)

    # printed amounts, kept before recomputation
    items = doc.get("items") or []
    printed_lines = [it.get("netAmount") for it in items]
    printed = {"subtotal": doc.get("subtotal"), "total": doc.get("total"),
               "tax": {Decimal(str(r["taxRate"])): r.get("taxAmount") for r in doc.get("taxSummary") or []
                       if isinstance(r.get("taxRate"), (int, float))}}
    for i, r in enumerate(doc.get("taxSummary") or []):
        if not isinstance(r.get("taxRate"), (int, float)):
            c.error("MISSING_FIELD", f"taxSummary[{i}].taxRate missing", f"taxSummary[{i}].taxRate")

    # mandatory document fields
    for f in ("invoiceNumber", "issueDate", "currency"):
        if not doc.get(f):
            c.error("MISSING_FIELD", f"{f} missing", f)
    if not (doc.get("buyer") or {}).get("name"):
        c.error("MISSING_FIELD", "buyer.name missing", "buyer.name")
    if not items:
        c.error("MISSING_FIELD", "no line items", "items")
    for i, it in enumerate(items):
        for f in ("description", "quantity", "unitPrice", "taxRate"):
            if it.get(f) in (None, ""):
                c.error("MISSING_FIELD", f"items[{i}].{f} missing", f"items[{i}].{f}")
        if it.get("unitPrice") is not None and Decimal(str(it["unitPrice"])) < 0:
            c.error("NEGATIVE_UNIT_PRICE", f"items[{i}].unitPrice is negative (BR-27): use a negative quantity", f"items[{i}].unitPrice")
    for f in ("issueDate", "dueDate", "deliveryDate"):
        if doc.get(f) and not ISO_DATE.match(str(doc[f])):
            c.error("DATE_FORMAT", f"{f} must be YYYY-MM-DD", f)
    if printed["total"] is None:
        c.error("PRINTED_TOTAL_MISSING", "the printed gross total (invoice.total) must be read from the PDF", "total")
    if not doc.get("dueDate") and not (doc.get("paymentTerms") or {}).get("dueDays"):
        c.warn("NO_DUE_DATE", "neither dueDate nor paymentTerms.dueDays on the document")
    if not doc.get("servicePeriod") and not doc.get("deliveryDate"):
        c.warn("NO_SERVICE_DATE", "no service period or delivery date on the document (in DE required if it differs from the issue date)")
    if doc.get("type") in ("credit_note", "correction"):
        for p, v in leaves(doc):
            if isinstance(v, (int, float)) and not isinstance(v, bool) and v < 0 and not p.endswith("quantity"):
                c.error("CREDIT_NOTE_SIGN", f"{p} is negative: a credit note carries positive amounts, the sign belongs to the type", p)

    # master data that is not on the PDF: asked once, saved with `remember`
    asks = []

    def ask(target, field, required, why, from_pdf=None, key=None, file=None):
        asks.append({k: v for k, v in {
            "target": target, "key": key, "field": field, "required": required, "why": why,
            "fromPdf": from_pdf, "file": file}.items() if v is not None})

    # seller from the profile; the VAT ID on the letterhead must be the profile's
    pdf_seller = doc.get("seller") or {}
    seller = load_json(a.seller, "seller")
    if seller is None:
        c.error("NO_SELLER_PROFILE", f"seller profile {a.seller} not found: ask the user, save with `remember seller`")
        seller = {}
    doc_vat = pdf_seller.get("vatId")
    if doc_vat and seller.get("vatId") and re.sub(r"\s", "", doc_vat).upper() != re.sub(r"\s", "", seller["vatId"]).upper():
        c.error("SELLER_VATID_MISMATCH", f"VAT ID on the PDF ({doc_vat}) is not the seller profile's ({seller['vatId']}): wrong company?", "seller.vatId")
    if not doc_vat:
        c.warn("SELLER_VATID_NOT_ON_PDF", "no seller VAT ID found on the PDF; the profile's is used")
    need = [(f, True, "mandatory seller data") for f in ("name", "street", "postalCode", "city", "countryCode", "vatId")]
    need.append(("bankAccount.iban", a.format == "xrechnung", "payment by bank transfer (BR-DE-1 for XRechnung)"))
    need.append(("bankAccount.bic", False, "payment by bank transfer"))
    for f in ("contact.name", "contact.phone", "contact.email"):
        need.append((f, a.format == "xrechnung", "seller contact (BR-DE-2/5/6/7 for XRechnung)"))
    for f, required, why in need:
        if get_path(seller, f) is not None or (not required and has_path(seller, f)):
            continue  # set, or asked before and answered "none"
        ask("seller", f, required, why, get_path(pdf_seller, f), file=a.seller)
        if required and seller:
            c.error("SELLER_PROFILE_INCOMPLETE", f"seller profile has no {f}", f"seller.{f}")
    if seller and not get_path(seller, "bankAccount.iban") and a.format != "xrechnung":
        c.warn("NO_BANK_ACCOUNT", "seller profile has no bankAccount.iban (needed for bank transfer)")

    # buyer: what the PDF does not print comes from the customer table
    buyer = dict(doc.get("buyer") or {})
    customers = load_json(a.customers, "customers") or {}
    cust = {customer_key(k): v for k, v in customers.items()}.get(customer_key(buyer.get("name")))
    name = buyer.get("name")
    if cust:
        for k in ("name", "street", "postalCode", "city", "countryCode", "vatId", "email"):
            if cust.get(k):
                buyer[k] = cust[k]
    elif a.format == "xrechnung":
        c.error("CUSTOMER_UNKNOWN", f"buyer {name!r} is not in {a.customers}: XRechnung needs the Leitweg-ID from there", "buyer.name")
    else:
        c.warn("CUSTOMER_UNKNOWN", f"buyer {name!r} is not in {a.customers}: no e-mail address, no buyer reference")
    cust = cust or {}
    ref = cust.get("leitwegId") or cust.get("buyerReference")
    if name:
        if "email" not in cust:
            ask("customer", "email", False, "where the e-invoice goes; not printed on the PDF", key=name, file=a.customers)
        if not ref and (a.format == "xrechnung" or not ("leitwegId" in cust or "buyerReference" in cust)):
            ask("customer", "leitwegId", a.format == "xrechnung",
                "Leitweg-ID / buyer reference (BT-10); required by public-sector buyers (BR-DE-15)" if a.format == "xrechnung"
                else "Leitweg-ID or other buyer reference (BT-10), only if the buyer gave you one", key=name, file=a.customers)
    lid = cust.get("leitwegId")
    if lid and not leitweg_ok(re.sub(r"\s", "", str(lid)).upper()):
        msg = f"Leitweg-ID {lid!r} of {name!r} in {a.customers} has a wrong format or wrong check digits"
        if a.format == "xrechnung":
            c.error("INVALID_LEITWEG_ID", msg + ": ask the user, `remember customer ... --set leitwegId=... --replace`", "countrySpecific.buyerReference")
        else:
            c.warn("INVALID_LEITWEG_ID", msg, "countrySpecific.buyerReference")
    if a.format == "xrechnung" and cust and not ref:
        c.error("NO_BUYER_REFERENCE", "XRechnung needs a Leitweg-ID (leitwegId) in the customer table (BR-DE-15)", "countrySpecific.buyerReference")
    for f in ("street", "postalCode", "city", "countryCode"):
        if not buyer.get(f):
            c.error("MISSING_FIELD", f"buyer.{f} missing (PDF or customer table)", f"buyer.{f}")
            if name:
                ask("customer", f, True, "buyer address, not readable from the PDF", key=name, file=a.customers)

    # assemble and recompute
    inv = json.loads(json.dumps(doc))
    inv["seller"] = seller
    inv["buyer"] = buyer
    inv.setdefault("type", "invoice")
    cs = dict(inv.get("countrySpecific") or {})
    cs["countryCode"] = (seller.get("countryCode") or "DE").upper()
    if ref:
        cs["buyerReference"] = ref
    inv["countrySpecific"] = cs
    if c.ok or items:
        try:
            compute(inv)
        except (KeyError, InvalidOperation, TypeError) as e:
            c.error("COMPUTE_FAILED", f"cannot compute amounts: {e}")
    if "subtotal" in inv and inv.get("items"):
        for i, (it, pl) in enumerate(zip(inv["items"], printed_lines)):
            if pl is not None and abs(money(pl) - money(it["netAmount"])) > TOLERANCE:
                c.error("LINE_TOTAL_MISMATCH", f"items[{i}]: printed {money(pl)} != quantity x unit price {money(it['netAmount'])}", f"items[{i}].netAmount")
        for key, label in (("subtotal", "net total"), ("total", "gross total")):
            if printed[key] is not None and abs(money(printed[key]) - money(inv[key])) > TOLERANCE:
                c.error("TOTAL_MISMATCH", f"printed {label} {money(printed[key])} != recomputed {money(inv[key])}", key)
        for row in inv["taxSummary"]:
            p = printed["tax"].get(Decimal(str(row["taxRate"])))
            if p is not None and abs(money(p) - money(row["taxAmount"])) > TOLERANCE:
                c.error("TAX_MISMATCH", f"printed VAT {row['taxRate']:g} % {money(p)} != recomputed {money(row['taxAmount'])}", "taxSummary")
        for r in printed["tax"]:
            if r not in {Decimal(str(row["taxRate"])) for row in inv["taxSummary"]}:
                c.error("TAX_MISMATCH", f"printed VAT rate {r} % has no line items")
    inv = drop_none(inv)

    # duplicate guard: before anything is generated, no API call
    h = payload_hash(inv) if "subtotal" in inv else None
    for row in read_log(a.log):
        if row.get("status") != "ok":
            continue
        if h and row.get("payloadHash") == h:
            c.error("DUPLICATE", f"this invoice was already generated on {row.get('timestamp')} ({row.get('document')})")
        elif row.get("sourceSha256") == ext["sha256"]:
            c.error("DUPLICATE_SOURCE", f"this PDF was already turned into {row.get('document')} on {row.get('timestamp')}")
        elif (row.get("invoiceNumber") == inv.get("invoiceNumber")
              and str(row.get("sellerVatId", "")).upper() == str(seller.get("vatId", "")).upper()):
            c.error("NUMBER_REUSED", f"invoice number {inv.get('invoiceNumber')} was already issued on {row.get('timestamp')} with other content")

    res = {
        "ok": c.ok,
        "extraction": AI_NOTE,
        "format": a.format,
        "country": cs["countryCode"].lower(),
        "source": {"file": ext["file"], "sha256": ext["sha256"]},
        "payloadHash": h,
        "checks": c.items,
        "ask": asks,
        "notFromPdf": {k: v for k, v in defaults.items()},
        "invoice": inv,
    }
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.extracted)), "checked.json")
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({
        "ok": c.ok, "checked": out, "format": a.format,
        "invoiceNumber": inv.get("invoiceNumber"), "type": inv.get("type"), "issueDate": inv.get("issueDate"),
        "dueDate": inv.get("dueDate"), "buyer": buyer.get("name"), "buyerReference": cs.get("buyerReference"),
        "subtotal": inv.get("subtotal"), "tax": [{"rate": r["taxRate"], "amount": r["taxAmount"]} for r in inv.get("taxSummary", [])],
        "total": inv.get("total"), "currency": inv.get("currency"),
        "notFromPdf": res["notFromPdf"],
        "ask": asks,
        "errors": [x for x in c.items if x["severity"] == "error"],
        "warnings": [x for x in c.items if x["severity"] == "warning"],
    }, ensure_ascii=False, indent=1))
    sys.exit(0 if c.ok else 1)


# ── remember ───────────────────────────────────────────────────────────────

SELLER_FIELDS = {"name", "street", "additionalStreet", "postalCode", "city", "countryCode", "vatId", "taxId", "email",
                 "phone", "contact.name", "contact.phone", "contact.email", "bankAccount.iban", "bankAccount.bic",
                 "bankAccount.bankName"}
CUSTOMER_FIELDS = {"name", "street", "postalCode", "city", "countryCode", "vatId", "email", "leitwegId"}
OPTIONAL_NONE = {"email", "leitwegId", "bankAccount.bic", "bankAccount.iban", "contact.name", "contact.phone",
                 "contact.email", "vatId", "phone", "taxId"}


def leitweg_ok(value):
    """Leitweg-ID: Grobadressierung, optional Feinadressierung, check digits (ISO/IEC 7064 Mod 97-10)."""
    if not re.fullmatch(r"\d{2,12}(-[A-Z0-9]{1,30})?-\d{2}", value):
        return False
    return int("".join(str(int(ch, 36)) for ch in value.replace("-", ""))) % 97 == 1


def iban_ok(value):
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", value):
        return False
    return int("".join(str(int(ch, 36)) for ch in value[4:] + value[:4])) % 97 == 1


def clean_value(field, value):
    """Normalise and validate one master-data value; SystemExit with a plain reason if it is wrong."""
    leaf = field.rsplit(".", 1)[-1]
    v = value.strip()
    if leaf in ("iban", "vatId", "bic", "countryCode", "leitwegId"):
        v = re.sub(r"\s", "", v).upper()
    checks = {
        "email": (lambda x: re.fullmatch(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}", x), "not an e-mail address"),
        "iban": (iban_ok, "IBAN check digits do not match"),
        "bic": (lambda x: re.fullmatch(r"[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?", x), "a BIC has 8 or 11 characters"),
        "vatId": (lambda x: re.fullmatch(r"DE\d{9}", x) if x.startswith("DE") else re.fullmatch(r"[A-Z]{2}[0-9A-Z+*.]{2,12}", x),
                  "a VAT ID starts with the country code (DE + 9 digits)"),
        "countryCode": (lambda x: re.fullmatch(r"[A-Z]{2}", x), "ISO country code with 2 letters, e.g. DE"),
        "leitwegId": (leitweg_ok, "not a valid Leitweg-ID (format or check digits, e.g. 04011000-1234512345-06)"),
        "phone": (lambda x: len(re.sub(r"\D", "", x)) >= 5, "not a phone number"),
    }
    test = checks.get(leaf)
    if not v or (test and not test[0](v)):
        raise SystemExit(f"{field}: {value!r} rejected - {test[1] if test else 'empty'}. Nothing was saved.")
    return v


def cmd_remember(a):
    target = a.target
    path = a.file or ("invoice-seller.json" if target == "seller" else "invoice-customers.json")
    allowed = SELLER_FIELDS if target == "seller" else CUSTOMER_FIELDS
    if target == "customer" and not a.key:
        raise SystemExit('remember customer needs the buyer name as printed on the PDF, e.g. remember customer "Beispiel Kunde AG" ...')
    data = load_json(path, target) or {}
    if target == "customer":
        match = next((k for k in data if customer_key(k) == customer_key(a.key)), None)
        rec = data.setdefault(match or re.sub(r"\s+", " ", a.key).strip(), {})
    else:
        rec = data
    changes = []
    for item in a.set or []:
        if "=" not in item:
            raise SystemExit(f"--set needs field=value, got {item!r}")
        field, value = (x.strip() for x in item.split("=", 1))
        if field not in allowed:
            raise SystemExit(f"{field} is not a {target} field. Allowed: {', '.join(sorted(allowed))}")
        if value.lower() == "none":
            if field not in OPTIONAL_NONE:
                raise SystemExit(f"{field} is mandatory and cannot be 'none'.")
            new = None  # asked, the answer was: there is none
        else:
            new = clean_value(field, value)
        *parents, last = field.split(".")
        node = rec
        for part in parents:
            node = node.setdefault(part, {})
        old = node.get(last, "<unset>")
        if last in node and old not in (None, new) and not a.replace:
            raise SystemExit(f"{field} is already {old!r}; pass --replace to change it to {new!r}. Nothing was saved.")
        node[last] = new
        if old != new:
            changes.append({"field": field, "old": old, "new": new})
    pc = rec.get("postalCode")
    if pc and (rec.get("countryCode") or "DE") == "DE" and not re.fullmatch(r"\d{5}", str(pc)):
        raise SystemExit(f"postalCode {pc!r}: a German postal code has 5 digits. Nothing was saved.")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(json.dumps({"saved": path, "target": target, "key": a.key, "changes": changes}, ensure_ascii=False, indent=1))


# ── generate ───────────────────────────────────────────────────────────────

def cmd_generate(a):
    from invoice_api import load_config, post, strip_binary

    chk = load_json(a.checked, "checked")
    if chk is None:
        raise SystemExit(f"{a.checked} not found - run `check` first.")
    if not chk.get("ok"):
        raise SystemExit("checked.json has errors (ok=false). Fix extracted.json and run `check` again.")
    inv = chk["invoice"]
    if payload_hash(inv) != chk.get("payloadHash"):
        raise SystemExit("invoice in checked.json was changed after `check`. Run `check` again.")
    log = a.log or os.path.join(a.out, "log.jsonl")
    for row in read_log(log):
        if row.get("status") == "ok" and row.get("payloadHash") == chk["payloadHash"]:
            raise SystemExit(f"already generated on {row.get('timestamp')}: {row.get('document')} - not generated again.")

    cfg = load_config()
    fmt, country = chk["format"], chk["country"]
    body = {"invoice": inv, "validate": True}
    tpl = a.template_id or cfg.get("INVOICE_XHUB_TEMPLATE_ID")
    if tpl and fmt in ("pdf", "zugferd", "facturx"):
        body["templateId"] = tpl
    status, resp = post(cfg, f"/api/v1/invoice/{country}/{fmt}/generate", body)
    ok = status == 200 and resp.get("success")
    os.makedirs(a.out, exist_ok=True)
    nr = re.sub(r"[^A-Za-z0-9._-]", "_", inv["invoiceNumber"])
    stem = f"{inv['issueDate']}_{nr}_{fmt}_{chk['payloadHash'][:8]}"
    report = {"request": {"country": country, "format": fmt, "templateId": bool(tpl)}, "source": chk["source"],
              "extraction": AI_NOTE,
              "generate": {"http": status, **strip_binary(resp)}}
    doc = None
    if ok:
        ext = ".pdf" if "pdf" in (resp.get("mimeType") or "") else ".xml"
        doc = os.path.join(a.out, stem + ext)
        open(doc, "wb").write(base64.b64decode(resp["data"]))
        json.dump(inv, open(os.path.join(a.out, stem + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if country == "de" and fmt in ("zugferd", "xrechnung"):
            ps, pr = post(cfg, f"/api/v1/invoice/de/{fmt}/parse",
                          {"data": base64.b64encode(open(doc, "rb").read()).decode(), "filename": os.path.basename(doc)})
            back = (pr or {}).get("invoice") or {}
            same = (back.get("invoiceNumber") == inv["invoiceNumber"]
                    and money(back.get("total", 0)) == money(inv["total"])
                    and money(back.get("subtotal", 0)) == money(inv["subtotal"]))
            report["readBack"] = {"http": ps, "format": pr.get("format"), "errors": pr.get("errors"),
                                  "warnings": pr.get("warnings"), "matches": same}
            ok = ok and ps == 200 and not pr.get("errors") and same
    api_hash = resp.get("payloadHash") if isinstance(resp, dict) else None
    report["payloadHashMatchesApi"] = (api_hash == chk["payloadHash"]) if api_hash else None
    report_path = os.path.join(a.out, stem + ".report.json")
    json.dump(report, open(report_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "status": "ok" if ok else "error",
        "extraction": AI_NOTE,
        "sourceFile": chk["source"]["file"], "sourceSha256": chk["source"]["sha256"],
        "payloadHash": chk["payloadHash"], "apiPayloadHash": api_hash,
        "invoiceNumber": inv["invoiceNumber"], "type": inv.get("type"), "issueDate": inv.get("issueDate"),
        "seller": inv["seller"].get("name"), "sellerVatId": inv["seller"].get("vatId"), "buyer": inv["buyer"].get("name"),
        "buyerEmail": inv["buyer"].get("email"), "subtotal": inv["subtotal"], "total": inv["total"],
        "currency": inv.get("currency"), "format": fmt, "document": doc, "report": report_path,
    }
    os.makedirs(os.path.dirname(os.path.abspath(log)), exist_ok=True)
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    val = (resp.get("validation") or {}) if isinstance(resp, dict) else {}
    print(json.dumps({
        "ok": bool(ok), "http": status, "document": doc, "subtotal": inv["subtotal"], "total": inv["total"],
        "validation": val.get("status"),
        "errors": resp.get("complianceErrors") or val.get("errors") or resp.get("errors"),
        "warnings": resp.get("warnings"), "readBack": report.get("readBack"),
        "payloadHashMatchesApi": report["payloadHashMatchesApi"], "buyerEmail": inv["buyer"].get("email"),
        "report": report_path, "log": log,
    }, ensure_ascii=False, indent=1))
    sys.exit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract", help="PDF text per page, sha256, scan detection")
    e.add_argument("pdf")
    e.add_argument("--out", default="work")
    c = sub.add_parser("check", help="verify the read against the PDF, recompute, assemble (offline)")
    c.add_argument("extracted")
    c.add_argument("--extract", required=True)
    c.add_argument("--format", default="zugferd", choices=["zugferd", "xrechnung", "facturx", "pdf"])
    c.add_argument("--seller", default="invoice-seller.json")
    c.add_argument("--customers", default="invoice-customers.json")
    c.add_argument("--log", default=os.path.join("e-invoices", "log.jsonl"))
    c.add_argument("--out")
    r = sub.add_parser("remember", help="save master data the user gave (seller profile, customer table)")
    r.add_argument("target", choices=["seller", "customer"])
    r.add_argument("key", nargs="?", help="customer: buyer name as printed on the PDF")
    r.add_argument("--set", action="append", metavar="FIELD=VALUE", help="e.g. email=ap@example.org, leitwegId=none")
    r.add_argument("--file", help="default invoice-seller.json / invoice-customers.json")
    r.add_argument("--replace", action="store_true", help="allow changing a value that is already saved")
    g = sub.add_parser("generate", help="generate, read back, log (API)")
    g.add_argument("checked")
    g.add_argument("--out", default="e-invoices")
    g.add_argument("--log")
    g.add_argument("--template-id")
    a = ap.parse_args()
    {"extract": cmd_extract, "check": cmd_check, "remember": cmd_remember, "generate": cmd_generate}[a.cmd](a)


if __name__ == "__main__":
    main()
