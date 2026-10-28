---
name: invoice-from-pdf
description: Turn an existing PDF invoice (written in Word, Excel or an ERP, no embedded XML) into an e-invoice (ZUGFeRD/Factur-X PDF or XRechnung XML) with invoice-api.xhub.io. Claude reads the PDF, every value is checked against a verbatim quote from the PDF, totals are recomputed and compared with the printed ones, buyer e-mail and Leitweg-ID come from a customer table, duplicates are refused. Use when the user has a normal PDF Rechnung and wants it as E-Rechnung, ZUGFeRD or XRechnung, asks to convert Word/Excel invoices, or wants "PDF zur E-Rechnung".
---

# PDF invoice → e-invoice with invoice-api.xhub.io

You read the PDF; the script `scripts/pdf_to_einvoice.py` checks your read. A language model reads invoices well and now and then a little wrong, which is the worst error an invoice can have. So **every value you take from the PDF carries a verbatim quote**, and the script refuses anything it cannot find in the PDF text or that does not add up. Never work around a failed check by changing a quote or a printed total; fix the read.

## Before you start

- `INVOICE_XHUB_API_KEY` (environment variable or `.env` in the working directory) is needed for `generate` only; `extract` and `check` run offline. Never print the key.
- **Seller profile** `invoice-seller.json` (same file `invoice-create` uses): name, address, `vatId`, `bankAccount`, `contact` (name, phone, email; required for XRechnung). The PDF's letterhead is only compared with it, never copied.
- **Customer table** `invoice-customers.json`: buyer name as printed → `email`, `leitwegId` (BT-10), optional address/`vatId` that win over the PDF. Neither e-mail nor Leitweg-ID is on a normal PDF invoice. Without an entry, XRechnung stops; ZUGFeRD goes through with a warning. See `examples/`.
- Several companies or departments: one seller profile and customer table each, passed with `--seller` / `--customers`.
- Every `generate` counts against the quota. `extract` and `check` are free; iterate there.
- Only process PDFs the user gave you. They hold personal and business data.

## Workflow (per PDF)

1. **Extract** the text:
   ```bash
   python3 scripts/pdf_to_einvoice.py extract invoice.pdf --out work/
   ```
   Exit 3 = scan without text layer: stop and tell the user. No OCR, and do not read the page image instead; nothing could be verified.
   One PDF = one invoice. If `text.txt` shows several invoices, ask the user to split the PDF.
2. **Read** `work/text.txt` and write `work/extracted.json` as described in `references/extracted-format.md`:
   - `source` = `file` and `sha256` from the extract output.
   - `invoice`: only what is **on the document**, in API field names (`references/extracted-format.md`). Include the printed amounts: `items[].netAmount`, `subtotal`, `taxSummary[]` (`taxRate`, `taxAmount`), and always `total`.
   - `evidence`: for every value, the shortest verbatim snippet from `text.txt` that contains it **with its label** (`"Invoice date: 14.07.2026"`, not `"14.07.2026"`). Copy, do not retype or translate.
   - `defaults`: every value that is not printed (unit code, quantity 1 for a lump sum, buyer country) with a one-line reason. Nothing else.
   - Leave out anything you cannot find. Do not guess a due date, an order number or a VAT rate.
3. **Check** (offline):
   ```bash
   python3 scripts/pdf_to_einvoice.py check work/extracted.json --extract work/extract.json --format zugferd
   ```
   Errors and what they mean: `references/checks.md`. `QUOTE_NOT_IN_PDF`, `VALUE_NOT_IN_QUOTE`, `LINE_TOTAL_MISMATCH`, `TOTAL_MISMATCH` mean your read is wrong: look at the text again. `SELLER_VATID_MISMATCH` means the PDF is from another company; `DUPLICATE`/`NUMBER_REUSED` mean it was already generated. Do not "fix" these by editing data.
4. **Show the user** the summary from the check output: number, date, buyer, net, VAT, gross, Leitweg-ID, and **every entry of `notFromPdf`** (what you added), plus warnings. Wait for a go unless they already said to proceed.
5. **Generate:**
   ```bash
   python3 scripts/pdf_to_einvoice.py generate work/checked.json --out e-invoices
   ```
   `--format` was fixed at the check: `zugferd` (PDF/A-3 with XML, usual for B2B), `xrechnung` (public sector), `facturx`. Optional `--template-id` or `INVOICE_XHUB_TEMPLATE_ID` for the layout (see skill `invoice-template-from-pdf`). `ok: true` = generated, validated, read back with the same number and totals, and a line in `e-invoices/log.jsonl`.
6. **Report** the file, totals, validation, that the data was read by AI and confirmed by the user, `buyerEmail` (from the customer table) and the log path. Sending the e-invoice is the user's step; do not claim it was sent.

Several PDFs: run steps 1–3 for all, show one table of the results, generate the ones with `ok: true` after one go, and list the rejected ones with their reason.

## Rules

- The amounts sent are recomputed from quantity × unit price per rate; the printed ones must match within 2 cents, otherwise nothing is generated.
- A credit note has `type: credit_note` and **positive** amounts (the sign belongs to the type; BR-27 forbids negative unit prices). The quote for `type` must contain the word (Gutschrift, Credit note, Rechnungskorrektur, Storno).
- A discount line is a negative quantity with a positive unit price.
- `orderNumber` (BT-13) only if printed as the buyer's order/PO number. `countrySpecific.buyerReference` (BT-10) comes from the customer table, never from the PDF's own text.
- A month in the text ("services for July 2026") gives `servicePeriod` first to last day; quote that sentence.
- Never edit `checked.json`; `generate` refuses a changed invoice.
