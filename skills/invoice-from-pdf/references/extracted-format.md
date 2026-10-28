# `extracted.json` — what Claude writes after reading `text.txt`

Complete example for `examples/sample-invoice.pdf`: `examples/extracted.json`.

```json
{
 "source":   { "file": "invoice.pdf", "sha256": "<from extract output>" },
 "invoice":  { ...document fields in API names, plus the printed amounts... },
 "evidence": { "<field path>": "<verbatim snippet from text.txt>" },
 "defaults": { "<field path>": "<why this value is not on the PDF>" }
}
```

Field paths: `invoiceNumber`, `servicePeriod.start`, `buyer.city`, `items[0].unitPrice`, `taxSummary[0].taxAmount`.
**Every** value in `invoice` needs an entry in `evidence` or in `defaults`; the check fails otherwise.

## Fields to read from the document

| Field | BT | Note |
|---|---|---|
| `invoiceNumber` | BT-1 | |
| `type` | BT-3 | `invoice` (default, reason in `defaults`) or `credit_note` with a quote naming it |
| `issueDate`, `dueDate`, `deliveryDate` | BT-2/9/72 | `YYYY-MM-DD`; the quote keeps the printed form |
| `servicePeriod.start` / `.end` | BG-14 | a printed range, or a month ("July 2026") → first and last day |
| `orderNumber` | BT-13 | buyer's PO / order number only |
| `contractNumber`, `projectNumber`, `customerNumber` | BT-12/11 | if printed |
| `currency` | BT-5 | ISO code; quote a snippet with `EUR`/`€` |
| `seller.vatId` | BT-31 | from the letterhead/footer, compared with the seller profile |
| `seller.name`, `street`, `postalCode`, `city`, `bankAccount.iban`/`bic`/`bankName`, `contact.*` | BG-4/5/6, BG-17 | if printed; offered to the user as `fromPdf` while the seller profile is not complete, never sent from here |
| `buyer.name`, `street`, `postalCode`, `city`, `countryCode`, `vatId` | BG-7/8 | address block; `countryCode` usually a default for domestic addresses |
| `items[].description` | BT-153 | |
| `items[].quantity`, `unit`, `unitPrice` | BT-129/130/146 | net unit price; `unit` UN/ECE Rec 20 (`C62` piece, `HUR` hour, `DAY`, `MON`, `KGM`, `MTR`, `LS` lump sum) |
| `items[].taxRate`, `taxCategoryCode` | BT-152/151 | rate often only in the VAT line; `AE` reverse charge / `E` exempt need the printed note |
| `items[].netAmount` | BT-131 | printed line amount — compared, then recomputed |
| `subtotal`, `taxSummary[].taxRate`/`taxAmount`, `total` | BT-109/117/112 | printed totals — compared, then recomputed; `total` is required |
| `paymentTerms.description`, `paymentTerms.dueDays` | BT-20 | |
| `notes` | BT-22 | only text meant for the buyer, quoted |

Not from the PDF: the seller block that is sent (from `invoice-seller.json`), buyer e-mail and `countrySpecific.buyerReference` (from `invoice-customers.json`), line `position`, all computed amounts.

## Quotes

- Copy from `text.txt`. Whitespace and line breaks do not matter (they are collapsed), case does not matter, hyphenation at a line end is joined. Anything else must be identical.
- Keep the label: `"Due date: 13.08.2026"`. A bare number or date gets a warning `QUOTE_WITHOUT_LABEL`, because `13.08.2026` alone could be any date on the page. In a table without labels, quote the whole row.
- A number in the invoice must appear in its quote in German (`1.750,00`) or English (`1,750.00`) notation; signs are ignored. A date must appear as `14.07.2026`, `14.7.26`, `2026-07-14`, `14. Juli 2026`, `July 14, 2026`, or as a month for the first/last day of a period.
- A text value must be contained in its quote (`"54321 Kundenstadt"` supports both `postalCode` and `city`).
- Code fields (`type`, `unit`, `currency`, `countryCode`, `taxCategoryCode`) only need a quote that exists; the mapping word → code is yours.
