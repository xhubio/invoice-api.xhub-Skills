# invoice-api.xhub.io Skills für Claude

[![skills.sh](https://skills.sh/b/xhubio/invoice-api.xhub-Skills)](https://skills.sh/xhubio/invoice-api.xhub-Skills)

E-Rechnungen im Gespräch mit Claude erstellen, prüfen und gestalten – **ZUGFeRD, Factur-X und XRechnung** (EN 16931), direkt aus Claude Code oder Claude Desktop, über [invoice-api.xhub.io](https://invoice-api.xhub.io).

*English version: [README.md](README.md)*

| Skill | Was er macht |
|---|---|
| `invoice-create` | Fragt die Rechnungsdaten ab, rechnet Positionen, Umsatzsteuer und Summen, erzeugt ZUGFeRD/Factur-X/XRechnung mit Validierung, liest das Ergebnis zur Kontrolle wieder ein und legt PDF/XML, JSON und Prüfbericht ab |
| `invoice-read` | Liest eine E-Rechnung (PDF oder XML) aus: Nummer, Absender, Empfänger, Positionen, Summen – und meldet Fehler und Warnungen |
| `invoice-template-from-pdf` | Baut Ihre bisherige Rechnung (PDF aus Word, ERP oder vom Designer) als Vorlage für invoice-api nach: vermisst das Original, baut die Vorlage, rendert sie über die API und vergleicht Seite an Seite, bis sie passt. Prüft Seitenumbrüche und fehlende optionale Felder |

So sprechen Sie Claude an:
- „Erstelle eine Rechnung an Beispiel Handel GmbH über 12 Stunden Entwicklung à 95 € netto, Leistungszeitraum Oktober.“
- „Mach daraus eine XRechnung für die Stadt Beispielstadt, Leitweg-ID 04011000-1234512345-06.“
- „Ist diese XRechnung gültig? Was steht drin?“
- „Baue aus unserer bisherigen Rechnung (rechnung.pdf) eine Vorlage für invoice-api.“

## Voraussetzungen

- Ein Konto bei invoice-api.xhub.io und ein API-Key – es gibt einen kostenlosen Tarif. Jeder API-Aufruf zählt auf das Kontingent Ihres Tarifs.
- Python 3.8 oder neuer. `invoice-create` und `invoice-read` brauchen nur die Standardbibliothek, `invoice-template-from-pdf` zusätzlich `pip install pdfplumber pillow`.

## Installation

### Jeder Agent (skills-CLI, [skills.sh](https://skills.sh/xhubio/invoice-api.xhub-Skills))

```bash
npx skills add xhubio/invoice-api.xhub-Skills
```

Funktioniert mit Claude Code und anderen Agenten, die `SKILL.md` lesen. Einzelner Skill: `--skill invoice-create`.

### Claude Code (Plugin)

```bash
/plugin marketplace add xhubio/invoice-api.xhub-Skills
/plugin install invoice-api@xhubio
```

Alternativ die Ordner aus `skills/` nach `~/.claude/skills/` (für alle Projekte) oder `.claude/skills/` (für ein Projekt) kopieren.

### Claude Desktop / claude.ai

1. Einen Skill-Ordner zippen, z. B. `skills/invoice-create` → `invoice-create.zip`.
2. Unter **Einstellungen → Funktionen → Skills** hochladen.
3. Die Code-Ausführung muss `service.invoice-api.xhub.io` erreichen dürfen. Ist der Netzzugang in Ihrer Organisation eingeschränkt, nehmen Sie diesen Host in die erlaubten Domains auf – sonst meldet das Skript, dass der Dienst nicht erreichbar ist.

## Einrichtung

API-Key als Umgebungsvariable setzen oder eine Datei `.env` im Arbeitsordner anlegen:

```bash
INVOICE_XHUB_API_KEY=sk_live_...
# optional
INVOICE_XHUB_TEMPLATE_ID=<UUID einer gespeicherten PDF-Vorlage>
INVOICE_XHUB_URL=https://service.invoice-api.xhub.io
```

Optional: eine `invoice-seller.json` im Arbeitsordner mit Ihren Firmendaten (`name`, Anschrift, `vatId`, `bankAccount`). `invoice-create` nimmt sie dann als Absender, ohne nachzufragen.

Der Key wird nie ausgegeben und nie in erzeugte Dateien geschrieben. `.env` nicht einchecken (steht in `.gitignore`).

## Gut zu wissen

- **Die API rechnet nicht.** Beträge müssen auf den Cent stimmen. `invoice-create` rechnet sie aus Menge, Einzelpreis und Steuersatz.
- **Datum immer als JJJJ-MM-TT.** In der PDF-Vorlage gibt `{{issueDate|date}}` das deutsche Format aus.
- **Nachlass** als Position mit Menge −1 und positivem Preis, nicht mit negativem Preis (Regel BR-27).
- **Käuferreferenz (BT-10) und Bestellnummer (BT-13)** nur mit Angaben, die Ihr Kunde Ihnen genannt hat – nie mit dem Firmennamen.
- **XRechnung** braucht die Leitweg-ID des Empfängers und beim Absender einen Kontakt mit Name, Telefon und E-Mail.

Mehr in `skills/invoice-create/references/pitfalls.md` und `skills/invoice-template-from-pdf/references/blocktemplate.md`.

## Ohne Claude nutzen

```bash
python3 skills/invoice-create/scripts/create_invoice.py skills/invoice-create/examples/simple-de.json --out ./out
python3 skills/invoice-create/scripts/create_invoice.py skills/invoice-create/examples/xrechnung-de.json --format xrechnung --out ./out
python3 skills/invoice-read/scripts/read_invoice.py ./out/RE-2026-11-001.pdf --validate
```

## Links

- API-Dokumentation: https://docs.invoice-api.xhub.io
- Preise: https://invoice-api.xhub.io/pricing
- Support: pje@xhub.io

## Autor

Patrick Jerominek ([@pa201608](https://github.com/pa201608)) — BeeBack UG (haftungsbeschränkt), [xhub.io](https://xhub.io)

## Lizenz

MIT © BeeBack UG (haftungsbeschränkt) — xhub.io
