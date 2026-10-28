---
name: invoice-template-from-pdf
description: Rebuild an existing invoice PDF (from Word, an ERP, a designer) as an invoice-api.xhub.io PDF template (BlockTemplate JSON), so e-invoices (ZUGFeRD/Factur-X) look like the company's own invoices. Measures the original, builds the template, renders it through the API and compares side by side until it matches. Use when the user wants "our invoice layout", a Rechnungsvorlage, template, Briefpapier or corporate design for invoice-api.
---

# Rebuild an invoice PDF as an invoice-api template

> **What it does:** rebuilds your existing invoice layout (from Word, an ERP or a designer) as an invoice-api.xhub.io template, so your e-invoices look like your invoices today. Claude measures the original, builds the template, renders it through the API and compares side by side until it matches, including page breaks.
>
> **You need:** an invoice-api.xhub.io API key, Python 3.8+, `pip install pdfplumber pillow`.
>
> **Try:** *"Turn our current invoice (invoice.pdf) into an invoice-api template."*

Do not eyeball. Measure the original, build with the helpers, render through the API, compare, correct. Repeat at most 5 rounds, then report what is left.

## Setup

- `pip install pdfplumber pillow` (Python 3.8+). Scripts are in `scripts/`.
- `INVOICE_XHUB_API_KEY` as environment variable or `.env` in the working directory. Never print it.
- Each render is one API call (counts against the quota). A full job takes about 8-12 calls.
- Keep the original PDF and everything derived from it (sample data, renders) local; it contains customer data. Never commit it.

## Workflow

1. **Measure** the original:
   ```bash
   python3 scripts/analyze_pdf.py original.pdf --out analysis
   ```
   Look at `analysis/page-1.png`, then read `analysis/analysis.json`: every text line with x/top/size/font/bold/colour, filled areas, rules, images (logo cut out to `analysis/assets/`), palette and font sizes. These numbers are your spec.

2. **Map** every text line to one of three kinds and write the list down before building:
   - *data* -> placeholder (`{{invoiceNumber}}`, `{{buyer.name}}`, `{{issueDate|date}}`, the item table, the totals). See `references/blocktemplate.md` for the placeholder list.
   - *fixed* -> literal text that is the same on every invoice (register court, managing director, slogan).
   - *example content* -> letter subject/intro of this one invoice: make it optional (`{{letter.subject?}}`) or leave it out; ask the user.

3. **Build sample data from the original** (`sample-from-original.json`): the same number, dates, parties, lines and totals as the original, in API format (ISO dates, amounts that add up). Only then can the comparison match texts one to one.

4. **Build the template** with a small Python script using `scripts/template_helpers.py` (start from `examples/build_template_example.py`):
   - Colour tokens and font-size tokens from the palette and font-size list.
   - Page margins and the header/footer heights from the measured positions (rules below).
   - Column widths from x-positions: width % = (next column x - this x) / content width.
   - Logo: `image_file("analysis/assets/image-1.png", w, h)` with the measured w/h. A text logo stays text.
   - Coloured bars/rules/boxes: `solid(hex, w, h)`.

5. **Render and compare**:
   ```bash
   python3 scripts/render_check.py template.json --invoice sample-from-original.json --original original.pdf --out check
   ```
   Open `check/side-by-side.png` (original left, render right) and read the summary: `medianAbsDy`/`medianAbsDx` (target < 3 pt), `worst` lines, `missingInRender`, `extraInRender` (raw `{{...}}` there = unsupported placeholder or filter). Fix the biggest vertical drift first - it accumulates downwards - then widths/wraps, then sizes and weights.

6. **Edge cases**, once it matches:
   ```bash
   python3 scripts/render_check.py template.json --invoice sample-from-original.json --variant minimal --out check
   python3 scripts/render_check.py template.json --invoice sample-from-original.json --variant long --out check
   ```
   minimal: optional rows must disappear without gaps. long: 30 lines, page break, header/footer and table header on every page, totals not orphaned.

7. **Deliver** `template.json` and a short report: what maps to which field, final deviation numbers, and what could not be reproduced (see limits). The user imports the JSON in the invoice-api console (Templates) to get a `templateId`; there is no upload endpoint. Until then it can be used inline via `formatOptions.template`.

## Rules learned from measuring the renderer (2026-10)

| Topic | Behaviour |
|---|---|
| Header/footer height | `header.height`/`footer.height` are read in **mm**. Body starts at max(`margins.top`, header mm x 2.835). Footer starts at page height - max(`margins.bottom`, footer mm x 2.835). Use `mm(pt)`. |
| Header start | header content starts ~5 pt below the page edge, whatever the margin; push it down with `gap()`. |
| Spacer | `spacer(h)` takes about h + 10 pt. Use `gap(pt)`, which corrects this. |
| Margins | `margin` is `[left, top, right, bottom]`. |
| line block | takes ~25 pt incl. built-in margins; use `solid()` for tight rules. |
| Images | keep their aspect ratio; `solid()` generates matching PNGs. |
| Dates | `{{issueDate\|date}}` -> 02.10.2026, `{{issueDate\|date:dd.MM.yy}}`. Works in **text blocks only**; keyvalue prints it raw -> use `meta_row()`. Table and summary format dates/numbers via `dateFormat`/`numberFormat`. |
| Not supported | `:date`, `\|iban`, `\|upper`, `\|currency` in text (empty). IBAN is printed as sent; send it grouped only if the format allows (ZUGFeRD wants it without spaces) - otherwise accept ungrouped. |
| Fonts | `Inter` and `Roboto` work as `defaultFont`. Other fonts: test once; if the render falls back, use the closest available and say so. |
| Content | Body blocks go in `body.blocks`. (Templates saved by the console editor may use `pages[0].blocks` instead; both render.) Extra data fields such as `letter.subject` pass through to the template. |

## Limits - say so in the report

- No background fill behind a summary row or a box; use a left bar (`solid`) or a rule instead.
- No mixed fonts/weights inside one text line (e.g. "xhub" black + "." green): split into columns or accept one colour.
- Item table shows one text column per field; a bold item name plus a grey long description in the same cell is not possible - use `description` only.
- Quantity and unit ("2 Tage") are separate fields; add a `unit` column if needed.
