# invoice-api.xhub.io Skills for Claude

[![skills.sh](https://skills.sh/b/xhubio/invoice-api.xhub-Skills)](https://skills.sh/xhubio/invoice-api.xhub-Skills)

Create, read and validate e-invoices — **ZUGFeRD, Factur-X, XRechnung** (EN 16931) — directly from Claude Code or Claude Desktop, powered by [invoice-api.xhub.io](https://invoice-api.xhub.io).

> German version: [README.de.md](README.de.md)

| Skill | What it does |
|---|---|
| `invoice-create` | Collects invoice data, computes line amounts, VAT and totals, generates ZUGFeRD/Factur-X/XRechnung with validation, reads the result back and saves PDF/XML + JSON + report |
| `invoice-read` | Reads an e-invoice file (PDF or XML), extracts number, parties, lines and totals, and reports validation errors and warnings |
| `invoice-from-pdf` | Turns an ordinary PDF invoice (from Word, Excel or an ERP) into ZUGFeRD/XRechnung: Claude reads the PDF, every value is checked against a verbatim quote from the PDF, totals are recomputed against the printed ones, what the PDF does not say (bank account, buyer e-mail, Leitweg-ID) is asked once and saved, duplicates are refused. The AI counterpart of the [n8n template](https://invoice-api.xhub.io/docs/integrations/n8n/templates/pdf-to-erechnung-per-department) |
| `invoice-template-from-pdf` | Rebuilds your existing invoice PDF as an invoice-api PDF template: measures the original, builds the template, renders it through the API and compares side by side until it matches; checks page breaks and optional fields |

Example prompts:
- "Create an invoice to Beispiel Handel GmbH for 12 hours of development at €95 net, service period October."
- "Turn invoice-0042.pdf into a ZUGFeRD e-invoice."
- "Is this XRechnung valid? What does it contain?"
- "Turn our current invoice (invoice.pdf) into an invoice-api template."

## Requirements

- An invoice-api.xhub.io account and API key — free plan available at [invoice-api.xhub.io](https://invoice-api.xhub.io). Every API call counts against your plan's quota.
- Python 3.8+. `invoice-create` and `invoice-read` use the standard library only; `invoice-from-pdf` needs `pdftotext` (poppler) or `pip install pdfplumber`; `invoice-template-from-pdf` needs `pip install pdfplumber pillow`.

## Installation

### Any agent (skills CLI, [skills.sh](https://skills.sh/xhubio/invoice-api.xhub-Skills))

```bash
npx skills add xhubio/invoice-api.xhub-Skills
```

Works with Claude Code and other agents that read `SKILL.md`. Install a single skill with `--skill invoice-create`.

### Claude Code (plugin)

```bash
/plugin marketplace add xhubio/invoice-api.xhub-Skills
/plugin install invoice-api@xhubio
```

Or copy the folders from `skills/` into `~/.claude/skills/` (all projects) or `.claude/skills/` (one project).

### Claude Desktop / claude.ai

1. Zip a skill folder, e.g. `skills/invoice-create` → `invoice-create.zip`.
2. Upload it under **Settings → Capabilities → Skills**.
3. Code execution must be allowed to reach `service.invoice-api.xhub.io`. If your organisation restricts network access, add this host to the allowed domains, otherwise the script reports that the service cannot be reached.

## Configuration

Set your key as an environment variable, or put a `.env` file into the working directory:

```bash
INVOICE_XHUB_API_KEY=sk_live_...
# optional
INVOICE_XHUB_TEMPLATE_ID=<uuid of a saved PDF template>
INVOICE_XHUB_URL=https://service.invoice-api.xhub.io
```

Optional: an `invoice-seller.json` in the working directory with your company data (`name`, address, `vatId`, `bankAccount`). `invoice-create` then uses it as seller without asking; `invoice-from-pdf` builds it with you on the first PDF (it asks, proposes what the letterhead shows, and saves the answers) and keeps an `invoice-customers.json` the same way (buyer name → e-mail, Leitweg-ID), because neither is printed on a normal PDF invoice.

The key is never printed or written into generated files. Do not commit `.env` (it is in `.gitignore`).

## Scripts without Claude

```bash
python3 skills/invoice-create/scripts/create_invoice.py skills/invoice-create/examples/simple-de.json --out ./out
python3 skills/invoice-create/scripts/create_invoice.py skills/invoice-create/examples/xrechnung-de.json --format xrechnung --out ./out
python3 skills/invoice-read/scripts/read_invoice.py ./out/RE-2026-11-001.pdf --validate

cd skills/invoice-from-pdf/examples
python3 ../scripts/pdf_to_einvoice.py extract sample-invoice.pdf --out work
python3 ../scripts/pdf_to_einvoice.py check extracted.json --extract work/extract.json --out work/checked.json   # offline
python3 ../scripts/pdf_to_einvoice.py generate work/checked.json --out e-invoices
```

Run the repository checks with `python3 tools/check_repo.py` (also runs in CI). Changes: [CHANGELOG.md](CHANGELOG.md).

## Links

- API documentation: https://docs.invoice-api.xhub.io
- Pricing: https://invoice-api.xhub.io/pricing
- Support: pje@xhub.io

## Author

Patrick Jerominek ([@pa201608](https://github.com/pa201608)) — BeeBack UG (haftungsbeschränkt), [xhub.io](https://xhub.io)

## License

MIT © BeeBack UG (haftungsbeschränkt) — xhub.io
