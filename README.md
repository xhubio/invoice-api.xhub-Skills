# invoice-api.xhub.io Skills for Claude

Create, read and validate e-invoices — **ZUGFeRD, Factur-X, XRechnung** (EN 16931) — directly from Claude Code or Claude Desktop, powered by [invoice-api.xhub.io](https://invoice-api.xhub.io).

> **Deutsch:** siehe [README.de.md](README.de.md). E-Rechnungen im Gespräch mit Claude erstellen und prüfen. Claude sammelt die Rechnungsdaten, rechnet die Beträge, erzeugt die ZUGFeRD-PDF oder XRechnung über invoice-api.xhub.io, validiert sie und liest das Ergebnis zur Kontrolle wieder ein.

| Skill | What it does |
|---|---|
| `invoice-create` | Collects invoice data, computes line amounts, VAT and totals, generates ZUGFeRD/Factur-X/XRechnung with validation, reads the result back and saves PDF/XML + JSON + report |
| `invoice-read` | Reads an e-invoice file (PDF or XML), extracts number, parties, lines and totals, and reports validation errors and warnings |
| `invoice-template-from-pdf` | Rebuilds your existing invoice PDF as an invoice-api PDF template: measures the original, builds the template, renders it through the API and compares side by side until it matches; checks page breaks and optional fields |

Example prompts:
- „Erstelle eine Rechnung an Beispiel Handel GmbH über 12 Stunden Entwicklung à 95 € netto, Leistungszeitraum Oktober.“
- "Is this XRechnung valid? What does it contain?"
- „Baue aus unserer bisherigen Rechnung (rechnung.pdf) eine Vorlage für invoice-api.“

## Requirements

- An invoice-api.xhub.io account and API key — free plan available at [invoice-api.xhub.io](https://invoice-api.xhub.io). Every API call counts against your plan's quota.
- Python 3.8+. `invoice-create` and `invoice-read` use the standard library only; `invoice-template-from-pdf` additionally needs `pip install pdfplumber pillow`.

## Installation

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

Optional: an `invoice-seller.json` in the working directory with your company data (`name`, address, `vatId`, `bankAccount`). `invoice-create` then uses it as seller without asking.

The key is never printed or written into generated files. Do not commit `.env` (it is in `.gitignore`).

## Scripts without Claude

```bash
python3 skills/invoice-create/scripts/create_invoice.py skills/invoice-create/examples/simple-de.json --out ./out
python3 skills/invoice-create/scripts/create_invoice.py skills/invoice-create/examples/xrechnung-de.json --format xrechnung --out ./out
python3 skills/invoice-read/scripts/read_invoice.py ./out/RE-2026-11-001.pdf --validate
```

Run the repository checks with `python3 tools/check_repo.py` (also runs in CI). Changes: [CHANGELOG.md](CHANGELOG.md).

## Links

- API documentation: https://docs.invoice-api.xhub.io
- Pricing: https://invoice-api.xhub.io/pricing
- Support: pje@xhub.io

## License

MIT © BeeBack UG (haftungsbeschränkt) — xhub.io
