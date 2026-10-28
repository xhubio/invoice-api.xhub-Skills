---
name: invoice-from-pdf
description: Turn an existing PDF invoice (written in Word, Excel or an ERP, no embedded XML) into an e-invoice (ZUGFeRD/Factur-X PDF or XRechnung XML) with invoice-api.xhub.io. Claude reads the PDF, every value is checked against a verbatim quote from the PDF, totals are recomputed and compared with the printed ones, buyer e-mail and Leitweg-ID come from a customer table, duplicates are refused. Use when the user has a normal PDF Rechnung and wants it as E-Rechnung, ZUGFeRD or XRechnung, asks to convert Word/Excel invoices, or wants "PDF zur E-Rechnung".
---

# PDF invoice → e-invoice with invoice-api.xhub.io

> **What it does:** turns the PDF invoices you already write in Word, Excel or your ERP into ZUGFeRD or XRechnung. Claude reads the PDF; a script checks every value against a verbatim quote from the PDF and recomputes the totals, so a misread is refused instead of sent. What the PDF does not say (your bank account, the buyer's e-mail address, a Leitweg-ID) Claude asks once and saves for next time; duplicates are caught before any API call.
>
> **You need:** an invoice-api.xhub.io API key, Python 3.8+, `pdftotext` or `pip install pdfplumber`.
>
> **Try:** *"Turn invoice-0042.pdf into a ZUGFeRD e-invoice."*

You read the PDF; the script `scripts/pdf_to_einvoice.py` checks your read. A language model reads invoices well and now and then a little wrong, which is the worst error an invoice can have. So **every value you take from the PDF carries a verbatim quote**, and the script refuses anything it cannot find in the PDF text or that does not add up. Never work around a failed check by changing a quote or a printed total; fix the read.

## Before you start

- `INVOICE_XHUB_API_KEY` (environment variable or `.env` in the working directory) is needed for `generate` only; `extract` and `check` run offline. Never print the key.
- **Seller profile** `invoice-seller.json` (same file `invoice-create` uses): name, address, `vatId`, `bankAccount`, `contact` (name, phone, email; required for XRechnung). Once saved, the PDF's letterhead is only compared with it.
- **Customer table** `invoice-customers.json`: buyer name as printed → `email`, `leitwegId` (BT-10), optional address/`vatId` that win over the PDF. Neither e-mail nor Leitweg-ID is on a normal PDF invoice. See `examples/`.
- Both files may be missing at the start: `check` lists what is missing in `ask[]`, you ask the user and save the answers with `remember` (step 4). Never write these files by hand.
- Several companies or departments: one seller profile and customer table each, passed with `--seller` / `--customers`.
- One target format per seller. The duplicate guard knows an invoice by its content, not its format: once generated as ZUGFeRD, it is refused as XRechnung.
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
4. **Ask for missing master data** if `ask[]` is not empty, all of it in **one** message, then save and check again:
   - Group by target: the seller (once per company) and each customer (once per buyer).
   - Where `fromPdf` is set, offer it: "On the PDF: IBAN DE02 1203 … — use it?" The user confirms; you do not save a suggestion unasked.
   - Mark `required: false` entries as optional; "none" is a valid answer (saved as `none`, never asked again).
   - Save exactly what the user said:
     ```bash
     python3 scripts/pdf_to_einvoice.py remember seller --set name="Musterfirma GmbH" --set bankAccount.iban="DE02 1203 0000 0000 2020 51" --set contact.phone="+49 30 1234567"
     python3 scripts/pdf_to_einvoice.py remember customer "Beispiel Kunde AG" --set email=ap@example.org --set leitwegId=none
     ```
     The customer key is the buyer name **as printed on the PDF**. `remember` checks e-mail, IBAN and Leitweg-ID check digits, VAT ID and BIC format and saves nothing if one value is wrong: tell the user which one and ask again. A saved value is changed only with `--replace`, after the user said so.
   - Only master data is saved. Values of this one invoice (due date, order number) are never stored; if they are missing, ask and put them into `extracted.json` under `defaults` with "given by the user".
   - Run `check` again until `ask[]` has no `required` entries and `ok` is true.
5. **Show the user** the summary from the check output: number, date, buyer, net, VAT, gross, Leitweg-ID, and **every entry of `notFromPdf`** (what you added), plus warnings. Wait for a go unless they already said to proceed.
6. **Generate:**
   ```bash
   python3 scripts/pdf_to_einvoice.py generate work/checked.json --out e-invoices
   ```
   `--format` was fixed at the check: `zugferd` (PDF/A-3 with XML, usual for B2B), `xrechnung` (public sector), `facturx`. Optional `--template-id` or `INVOICE_XHUB_TEMPLATE_ID` for the layout (see skill `invoice-template-from-pdf`). `ok: true` = generated, validated, read back with the same number and totals, and a line in `e-invoices/log.jsonl`.
7. **Report** the file, totals, validation, that the data was read by AI and confirmed by the user, `buyerEmail` (from the customer table) and the log path. Sending the e-invoice is the user's step; do not claim it was sent.

Several PDFs: run steps 1–3 for all, ask the missing master data of all of them in one message, show one table of the results, generate the ones with `ok: true` after one go, and list the rejected ones with their reason.

## Rules

- The amounts sent are recomputed from quantity × unit price per rate; the printed ones must match within 2 cents, otherwise nothing is generated.
- A credit note has `type: credit_note` and **positive** amounts (the sign belongs to the type; BR-27 forbids negative unit prices). The quote for `type` must contain the word (Gutschrift, Credit note, Rechnungskorrektur, Storno).
- A discount line is a negative quantity with a positive unit price.
- `orderNumber` (BT-13) only if printed as the buyer's order/PO number. `countrySpecific.buyerReference` (BT-10) comes from the customer table, never from the PDF's own text.
- A month in the text ("services for July 2026") gives `servicePeriod` first to last day; quote that sentence.
- Never edit `checked.json`; `generate` refuses a changed invoice.
