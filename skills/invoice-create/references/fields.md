# Invoice fields (subset)

Source: invoice-api OpenAPI 1.5.0, `POST /api/v1/invoice/{countryCode}/{format}/generate`, body `{ "invoice": {...}, "validate": true, "templateId": "...", "formatOptions": {...} }`.

Required: `invoiceNumber`, `type`, `issueDate`, `seller`, `buyer`, `items`, `currency`, `subtotal`, `total`, `taxSummary` (amounts are filled by the script).

| Field | Meaning | Note |
|---|---|---|
| `invoiceNumber` | BT-1 | unique, from the user's own sequence |
| `type` | BT-3 | `invoice`, `credit_note`, `correction`, `partial`, … |
| `issueDate` / `dueDate` | BT-2 / BT-9 | `YYYY-MM-DD` |
| `servicePeriod.start` / `.end` | BG-14 | service period; required in DE if it differs from the issue date |
| `deliveryDate` | BT-72 | single delivery/service day |
| `currency` | BT-5 | ISO 4217, e.g. `EUR` |
| `seller.name`, `street`, `postalCode`, `city`, `countryCode` | BG-4/5 | `countryCode` ISO alpha-2 |
| `seller.vatId` | BT-31 | with country prefix, e.g. `DE123456789` |
| `seller.bankAccount.iban` / `.bic` / `.bankName` | BG-17 | needed for bank transfer |
| `seller.contact.name` / `.email` / `.phone` | BG-6 | |
| `buyer.*` | BG-7/8 | `buyer.vatId` = BT-48, only if known |
| `items[].description` | BT-153 | |
| `items[].quantity` / `unit` / `unitPrice` | BT-129/130/146 | unit = UN/ECE Rec 20; unitPrice net, never negative |
| `items[].taxRate` / `taxCategoryCode` | BT-152/151 | `S` standard, `E` exempt (+ `taxExemptionReason`), `AE` reverse charge, `Z` zero |
| `items[].servicePeriod` | BG-26 | per-line period if lines cover different periods |
| `allowancesCharges[]` | BG-20/21 | invoice-level discount (`isCharge: false`) or surcharge |
| `paymentTerms.dueDays` / `.description` | BT-20 | e.g. 14, "Zahlbar innerhalb von 14 Tagen ohne Abzug" |
| `paymentMethods[].type` | BT-81 | `bank_transfer`, `direct_debit`, `credit_card`, … |
| `customerNumber` | | customer number at the seller |
| `orderNumber` | BT-13 | buyer's purchase order number only |
| `contractNumber` / `projectNumber` | BT-12 / BT-11 | |
| `countrySpecific.countryCode` | | must match the invoice country, e.g. `DE` |
| `countrySpecific.buyerReference` | BT-10 | Leitweg-ID (XRechnung) or a reference the buyer gave |
| `notes` | BT-22 | free text shown on the invoice |

Full reference: https://docs.invoice-api.xhub.io/api-reference/invoices/generate
