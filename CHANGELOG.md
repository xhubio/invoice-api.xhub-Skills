# Changelog

All notable changes to this repository. Versions follow `.claude-plugin/plugin.json`.

## Unreleased

- `skills.sh.json`: grouped repo page on skills.sh with a short explanation per group.
- Every `SKILL.md` starts with a short user-facing intro (what it does, what you need, an example prompt), shown on the skill pages of skills.sh.
- `invoice-from-pdf`: missing master data is asked once and saved. `check` lists it in `ask[]` (with the letterhead's values as suggestions); the new `remember` command saves the user's answers to `invoice-seller.json` / `invoice-customers.json`, validated (e-mail, IBAN and Leitweg-ID check digits, BIC, VAT ID, postal code), never overwriting without `--replace`; `none` records an optional field the buyer does not have. The example Leitweg-ID is now the KoSIT test ID `991-33333TEST-33` (the old one had wrong check digits).
- `invoice-from-pdf`: duplicate guard documented as format-independent (one target format per seller).

## 0.2.0 — 2026-10-28

- New skill `invoice-from-pdf`: an ordinary PDF invoice (Word, Excel, ERP) becomes ZUGFeRD/Factur-X/XRechnung. Claude reads the text; `pdf_to_einvoice.py` checks the read: every value needs a verbatim quote that is in the PDF and states the value, line amounts and totals are recomputed against the printed ones (2 cent tolerance), the seller VAT ID on the PDF must match the seller profile, buyer e-mail and Leitweg-ID come from `invoice-customers.json`, credit notes carry positive amounts, scans are rejected (no OCR). Duplicate guard before any API call via a JSON-Lines log (`payloadHash` computed like the API's, source SHA-256, invoice number + seller VAT ID). Offline example with a misread variant runs in CI.

## 0.1.0 — 2026-10-24

First public version.

- `invoice-create`: collect invoice data, compute line amounts, VAT and totals, generate ZUGFeRD/Factur-X/XRechnung via invoice-api.xhub.io with validation, read the result back, save document + JSON + report. Local checks for date format, negative unit prices (BR-27) and misused buyer reference (BT-10). Tested with ZUGFeRD (EN 16931) and XRechnung (UBL).
- `invoice-read`: read and check an e-invoice (PDF or XML), optional format validation.
- `invoice-template-from-pdf`: rebuild an existing invoice PDF as BlockTemplate — measure (`analyze_pdf.py`), build (`template_helpers.py`), render and compare side by side (`render_check.py`), edge cases (optional fields missing, 30 lines / page breaks). Documents measured renderer behaviour (section heights in mm, spacer overhead, margin order, `|date` filter).
- Claude Code plugin manifest and marketplace file; repository check (`tools/check_repo.py`) in CI.
