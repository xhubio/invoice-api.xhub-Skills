# Pitfalls seen in real invoices

| Symptom | Cause | Fix |
|---|---|---|
| `400 INVALID_DATE` | date like `19.10.2026` | always `YYYY-MM-DD` |
| `422 BR-27` "Item net price shall NOT be negative" | discount line with negative `unitPrice` | `quantity: -1` with positive `unitPrice`, or `allowancesCharges` |
| `422 BR-CO-…` sum rules | amounts sent do not add up (the API never recalculates) | let the script compute, or recalculate to the cent |
| Buyer's accounting cannot match the invoice | BT-10 filled with the buyer's company name, BT-13 with own free text | only references the buyer provided; otherwise leave out |
| Missing service period in DE | only `deliveryDate` sent for a monthly subscription | send `servicePeriod.start`/`end` |
| XRechnung rejected by public buyer | no Leitweg-ID | `countrySpecific.buyerReference` = Leitweg-ID |
| Invoice number used twice | regenerated after sending | regenerate only before sending; after sending issue a correction or credit note |
| Template rows missing (e.g. customer number) | optional template fields are hidden when the value is empty | send `customerNumber`, `buyer.vatId` if they should appear |
| XRechnung rejected for missing seller contact | BR-DE-2: seller contact (BG-6) needs name, phone and email | `seller.contact` with `name`, `phone`, `email` |
| Warning `BUSINESS_PROCESS_DEFAULTED` (PEPPOL-EN16931-R001) on XRechnung | no `businessProcess` (BT-23) sent; the default was written | harmless; send `businessProcess` only if the buyer asks for a specific one |
