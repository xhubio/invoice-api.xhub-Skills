# What `check` reports

`checks[]` in `checked.json`; `ok` is false as soon as one `error` exists. Nothing is generated then.

| Code | Severity | Meaning | What to do |
|---|---|---|---|
| `SCANNED_PDF` | error | no text layer | stop; no OCR |
| `SOURCE_MISMATCH` | error | `source.sha256` is not the extracted PDF | copy `sha256` from the extract output |
| `NO_EVIDENCE` | error | value without quote and without default | add the quote, or remove the value if it is not printed |
| `QUOTE_NOT_IN_PDF` | error | the quote is not in the PDF text | copy it again from `text.txt`; if it is not there, the value is not on the document |
| `VALUE_NOT_IN_QUOTE` | error | the quote does not say the value | **misread**: read the line again |
| `LINE_TOTAL_MISMATCH` | error | printed line amount ≠ quantity × unit price | misread quantity/price, or a discount/unit price per 100 — check the line |
| `TOTAL_MISMATCH` / `TAX_MISMATCH` | error | printed net/VAT/gross ≠ recomputed | a line or a rate is missing or wrong; or the document itself does not add up — tell the user, do not adjust |
| `PRINTED_TOTAL_MISSING` | error | `total` not read | read the gross total |
| `MISSING_FIELD` | error | mandatory field missing | read it, or add it to the customer table (buyer address) |
| `NEGATIVE_UNIT_PRICE` | error | BR-27 | negative quantity, positive price |
| `CREDIT_NOTE_SIGN` | error | negative amount in a credit note | write positive amounts, `type: credit_note` |
| `DATE_FORMAT` | error | not `YYYY-MM-DD` | |
| `NO_SELLER_PROFILE`, `SELLER_PROFILE_INCOMPLETE` | error | `invoice-seller.json` missing/incomplete | ask the user once, save it |
| `SELLER_VATID_MISMATCH` | error | the PDF is from another company than the profile | wrong profile or wrong PDF — ask |
| `SELLER_CONTACT` | error | XRechnung without seller contact name/phone/email | add `contact` to the profile |
| `CUSTOMER_UNKNOWN` | error (XRechnung) / warning | buyer not in the customer table | ask for e-mail and Leitweg-ID, add the entry (key = name as printed) |
| `NO_BUYER_REFERENCE` | error (XRechnung) | customer entry without `leitwegId` | ask the user |
| `DUPLICATE`, `DUPLICATE_SOURCE` | error | same invoice / same PDF already in the log with status ok — **in any format**: an invoice generated as ZUGFeRD is not generated again as XRechnung | nothing to do; it was generated before. One target format per seller |
| `NUMBER_REUSED` | error | same number and seller VAT ID, different content | a corrected invoice needs a new number or a credit note |
| `QUOTE_WITHOUT_LABEL` | warning | number/date quoted without its label | quote the label too |
| `EVIDENCE_UNUSED` | warning | quote for a field that is not in `invoice` | remove it or add the value |
| `SELLER_VATID_NOT_ON_PDF`, `NO_BANK_ACCOUNT`, `NO_DUE_DATE`, `NO_SERVICE_DATE` | warning | show to the user | |

The duplicate guard reads `e-invoices/log.jsonl` (`--log`). `payloadHash` is the SHA-256 of the canonical invoice JSON, computed the same way as the API's `payloadHash`; `generate` records whether both agree (`payloadHashMatchesApi`).
