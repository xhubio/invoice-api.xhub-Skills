# Changelog

All notable changes to this repository. Versions follow `.claude-plugin/plugin.json`.

## 0.1.0 — 2026-10-24

First public version.

- `invoice-create`: collect invoice data, compute line amounts, VAT and totals, generate ZUGFeRD/Factur-X/XRechnung via invoice-api.xhub.io with validation, read the result back, save document + JSON + report. Local checks for date format, negative unit prices (BR-27) and misused buyer reference (BT-10). Tested with ZUGFeRD (EN 16931) and XRechnung (UBL).
- `invoice-read`: read and check an e-invoice (PDF or XML), optional format validation.
- `invoice-template-from-pdf`: rebuild an existing invoice PDF as BlockTemplate — measure (`analyze_pdf.py`), build (`template_helpers.py`), render and compare side by side (`render_check.py`), edge cases (optional fields missing, 30 lines / page breaks). Documents measured renderer behaviour (section heights in mm, spacer overhead, margin order, `|date` filter).
- Claude Code plugin manifest and marketplace file; repository check (`tools/check_repo.py`) in CI.
