---
name: invoice-create
description: Create a German or EU e-invoice (ZUGFeRD/Factur-X PDF or XRechnung XML) with invoice-api.xhub.io from conversation data, validate it and save the file. Use when the user asks to write, issue or generate an invoice, Rechnung, E-Rechnung, XRechnung or ZUGFeRD, or to bill a customer.
---

# Create an e-invoice with invoice-api.xhub.io

The script `scripts/create_invoice.py` does the API work. Your job is to collect correct data, build the JSON, run the script and report the result honestly.

## Before you start

- An API key is required: `INVOICE_XHUB_API_KEY` as environment variable or in a `.env` file in the working directory. Optional: `INVOICE_XHUB_TEMPLATE_ID` (saved PDF template) and `INVOICE_XHUB_URL`. Never print, log or write the key anywhere.
- If a file `invoice-seller.json` exists in the working directory, use it as the `seller` object (name, address, VAT ID, bank account) instead of asking.
- Every call counts against the user's quota. Do not generate test runs "just to see"; fix data locally first.

## Workflow

1. **Collect the data.** Ask only for what is missing; do not invent anything.
   - Invoice number: the next free number of the user's own sequence. Ask if you cannot see it. Never reuse a number that was already sent.
   - Issue date (default today), payment terms (e.g. 14 days), service period or delivery date.
   - Seller: legal name, street, postal code, city, country, VAT ID (`vatId`) and bank account (IBAN/BIC) for bank transfer.
   - Buyer: legal name and address. Buyer VAT ID only if the user gives it.
   - Lines: description, quantity, unit (UN/ECE Rec 20: `C62` piece, `HUR` hour, `DAY` day, `MON` month), net unit price, tax rate.
   - Prices: clarify **net or gross** if unclear. The API expects net unit prices.
2. **Build the JSON** following `references/fields.md` and `examples/simple-de.json`. Leave out amounts: the script computes them.
3. **Check the pitfalls** in `references/pitfalls.md` against your JSON.
4. **Show the user a short summary** (buyer, lines, net, VAT, gross, dates) and get a go before generating, unless they already said to just do it.
5. **Run:**
   ```bash
   python3 scripts/create_invoice.py invoice.json --format zugferd --out ./invoices
   ```
   `--format`: `zugferd` (PDF with embedded XML, the usual choice for B2B), `xrechnung` (XML, required by public-sector buyers: needs a Leitweg-ID in `countrySpecific.buyerReference` and a seller contact with name, phone and email; see `examples/xrechnung-de.json`), `facturx`, `pdf`. `--country` defaults to `de`.
6. **Read the output.** `ok: true` means: created, schema/Schematron validation passed, and (for zugferd/xrechnung) the file was read back with the same number and totals. On `ok: false` show the errors in plain words, fix the JSON and run again with the same invoice number (it was not issued yet).
7. **Report** the file path, totals and validation result. Mention warnings. Do not claim the invoice was sent; sending is the user's step.

## Rules

- The API never calculates. Line net = quantity × unit price, tax per rate on the summed net, rounded to cents. The script does this; with `--no-compute` you must supply all amounts yourself.
- Dates are always `YYYY-MM-DD`.
- A discount is a line with **negative quantity** and positive unit price, or an invoice-level entry in `allowancesCharges`. A negative unit price is rejected (BR-27).
- `countrySpecific.buyerReference` (BT-10) and `orderNumber` (BT-13) only carry references **the buyer gave you** (Leitweg-ID, cost centre, purchase order number). Never the buyer's name, never your own text. Otherwise leave them out.
- Use `servicePeriod` (`start`, `end`) for subscriptions and services over a period; `deliveryDate` for a single day.
- Free text for the customer goes into `notes`.
