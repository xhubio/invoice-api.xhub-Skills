# BlockTemplate reference (invoice-api.xhub.io)

Used by `POST /api/v1/invoice/{country}/{format}/generate` (`templateId` or inline `formatOptions.template`, formats `pdf`, `zugferd`, `facturx`) and `POST /api/v1/pdf/generate`. Priority: `templateId` > inline template > built-in country template.

## Top level

```json
{ "name": "...", "version": "1.0.0", "editorVersion": "v2", "templateType": "custom", "locale": "de-DE", "lengthUnit": "pt",
  "page": { "size": "A4", "orientation": "portrait", "defaultFont": "Inter",
            "margins": { "top": 108, "right": 51, "bottom": 72, "left": 51 },
            "fontSizes": { "textSize": 9, "...": 0 }, "colorScheme": { "textColor": "#15181B", "...": "" } },
  "header": { "blocks": [], "height": 37, "repeatOnAllPages": true },
  "body":   { "blocks": [] },
  "footer": { "blocks": [], "height": 25, "repeatOnAllPages": true } }
```
`header.height`/`footer.height`: millimetres (measured). Tokens in `fontSizes`/`colorScheme` are referenced as `{"token": "textSize"}`.

## Blocks

| type | data fields | block fields |
|---|---|---|
| `text` | `content`, `fontSize`, `color`, `bold`, `alignment` (left/center/right), `hideMode` (`anyEmpty`/`allEmpty`), `margin` [l,t,r,b] | `condition` (data path) |
| `image` | `src` (data URI), `width`, `height`, `alignment` | |
| `line` | `color` (hex), `thickness`, `margin` | |
| `spacer` | `height` | `condition` |
| `columns` | `columns[]` (`width` "%"/"*", `blocks`, `cells[{blocks}]`), `columnGap` | `condition` |
| `keyvalue` | `items[]` (`label`, `value`, `valueAlign`, `optionalMode: "optional-hidden"`), `layout`, `labelWidth`, `fontSize`, `labelColor`, `valueColor`, `labelBold` | |
| `table` | `dataSource: "{{items}}"`, `columns[]` (`field`, `header`, `width`, `align`, `format: "currency"`, `currencySymbol`), `layout` (`lightHorizontalLines`, …), `fontSize`, `cellPadding`, `numberFormat`, `dateFormat`, `locale`, `showHeader`, `repeatHeader`, `headerFillColor`, `headerTextColor` | |
| `summary` | `headerRows[]`, `dynamicRows` (`dataSource: "{{taxSummary}}"`, `labelTemplate: "Umsatzsteuer {{taxRate:percent}}"`), `footerRows[]` (`bold`), `widths`, `separatorBeforeFooter`, `allowanceChargeLabels`, `numberFormat`, `locale` | |
| `qrcode` | `content` (e.g. `{{epcQrPayload?}}`), `size`, `eccLevel`, `alignment` | |

## Placeholders

Invoice fields as in the API: `{{invoiceNumber}}`, `{{issueDate}}`, `{{dueDate}}`, `{{deliveryDate}}`, `{{servicePeriod.start}}`, `{{orderNumber}}`, `{{customerNumber}}`, `{{seller.name}}`, `{{seller.street}}`, `{{seller.postalCode}}`, `{{seller.city}}`, `{{seller.vatId}}`, `{{seller.email}}`, `{{seller.phone}}`, `{{seller.website}}`, `{{seller.contact.name}}`, `{{seller.bankAccount.iban|bic|bankName|accountHolder}}`, `{{buyer.*}}`, `{{paymentTerms.description}}`, `{{paymentTerms.dueDays}}`, `{{subtotal}}`, `{{total}}`, `{{notes}}`, `{{items}}`, `{{taxSummary}}`. Extra fields sent in the invoice (e.g. `letter.subject`) are available too.

- `?` suffix: optional, renders empty instead of failing: `{{buyer.street?}}`
- Filters (text blocks only): `|date` (dd.MM.yyyy), `|date:FORMAT`
- In summary labels: `{{taxRate:percent}}`

## Measured layout behaviour

See the table in `SKILL.md` (“Rules learned from measuring the renderer”). Re-measure with a probe template if renders behave differently after an API update.
