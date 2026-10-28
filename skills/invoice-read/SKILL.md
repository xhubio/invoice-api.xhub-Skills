---
name: invoice-read
description: Read and check an incoming or outgoing e-invoice file (ZUGFeRD/Factur-X PDF, XRechnung or CII XML) with invoice-api.xhub.io - extract number, parties, lines and totals, and report validation errors. Use when the user shares an e-invoice, asks whether an invoice is valid, wants its data extracted, or wants to check a generated invoice before sending.
---

# Read and check an e-invoice with invoice-api.xhub.io

> **What it does:** reads a ZUGFeRD, Factur-X or XRechnung file and tells you in plain words what is in it (number, parties, lines, totals) and whether it is valid, with the rule ID of every error or warning.
>
> **You need:** an invoice-api.xhub.io API key (free plan available), Python 3.8+.
>
> **Try:** *"Is this XRechnung valid? What does it contain?"*

The script `scripts/read_invoice.py` sends the file to the parse endpoint and prints a summary.

## Before you start

- Requires `INVOICE_XHUB_API_KEY` (environment variable or `.env` in the working directory). Never print the key.
- Only send files the user gave you or created in this session. Invoices contain personal and business data.

## Workflow

1. Run:
   ```bash
   python3 scripts/read_invoice.py path/to/invoice.pdf            # read + parse findings
   python3 scripts/read_invoice.py path/to/invoice.xml --validate # plus format rules (1 extra call)
   python3 scripts/read_invoice.py invoice.pdf --json data.json   # save extracted data
   ```
   A PDF is read as ZUGFeRD/Factur-X. An XML is tried as XRechnung, then as ZUGFeRD/CII. Force with `--format`.
2. Report in plain words:
   - **Readable?** `detectedFormat` (e.g. `ZUGFERD_EN16931`). An `infos` entry `EXTRACTED_FROM_PDF` means the PDF carries real XML. A PDF without embedded XML is not an e-invoice.
   - **Content:** number, dates, seller, buyer, net, VAT, gross, lines.
   - **Findings:** every entry in `errors` (blocking) and `warnings` (rule ID such as `BR-CO-15` plus message). With `--validate`, list each failed profile.
3. If the user wants to book or pay the invoice, point out mismatches (totals vs. lines, missing VAT ID, missing bank account) but do not decide for them.
