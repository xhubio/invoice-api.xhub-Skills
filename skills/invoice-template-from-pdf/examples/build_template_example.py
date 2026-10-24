"""Example build script: an invoice layout rebuilt from a measured PDF
(generated from analyze_pdf.py output, tuned with render_check.py).
Copy, change texts/tokens/widths, run: python3 build_template_example.py -> template.json"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from template_helpers import *
C = {"textColor": "#15181B", "labelColor": "#565C63", "mutedColor": "#8B9198", "lineColor": "#E2DFD8",
     "primaryColor": "#0E5F55", "accentSoft": "#E8F1EF", "tint": "#F7F6F2", "tableHeaderBg": "#ffffff"}
Z = {"textSize": 9, "labelSize": 8.6, "smallSize": 8.3, "tinySize": 6.6, "microSize": 6.9, "headingSize": 23,
     "logoSize": 22, "leadSize": 10.4, "letterSize": 9.6, "tableSize": 9, "boxTitleSize": 10.5, "eyebrowSize": 7.8,
     "headerSize": 8.3, "payLabelSize": 8.8}
pg = page(font="Inter", margins=(108, 50.5, 72, 51), colors=C, sizes=Z)
W = 493.5
header = [
    gap(37),
    columns([
        col("60%", [text("Muster Software", "logoSize", bold=True),
                    text("SOFTWARE AUS FRANKFURT", "eyebrowSize", "mutedColor", margin=[0, 0, 0, 0])]),
        col("40%", [text("{{seller.contact.name?}}", "headerSize", "labelColor", align="right", hide="anyEmpty", margin=[0, 0, 0, 2.5]),
                    text("{{seller.phone?}}", "headerSize", "labelColor", align="right", hide="anyEmpty", margin=[0, 0, 0, 2]),
                    text("{{seller.email?}} · {{seller.website?}}", "headerSize", "labelColor", align="right", hide="allEmpty")]),
    ], 5),
    gap(16), solid("#0E5F55", W, 1.5),
]
address = [text("{{seller.name}} · {{seller.street?}} · {{seller.postalCode?}} {{seller.city?}}", "microSize", "mutedColor"),
           solid("#E2DFD8", 270, 0.75), gap(6),
           text("{{buyer.name}}", "letterSize", margin=[0, 0, 0, 2]),
           text("z. Hd. {{buyer.contact.name}}", "letterSize", cond="buyer.contact.name", margin=[0, 0, 0, 2]),
           text("{{buyer.street?}}", "letterSize", hide="anyEmpty", margin=[0, 0, 0, 2]),
           text("{{buyer.postalCode?}} {{buyer.city?}}", "letterSize", hide="allEmpty")]
meta = [meta_row("Rechnungsnummer", "{{invoiceNumber}}", label_width="47%", value_bold=True),
        meta_row("Rechnungsdatum", "{{issueDate|date}}", label_width="47%", value_bold=True),
        meta_row("Leistungsdatum", "{{deliveryDate|date}}", label_width="47%", cond="deliveryDate", value_bold=True),
        meta_row("Ihr Auftrag", "{{orderNumber}}", label_width="47%", cond="orderNumber", value_bold=True),
        meta_row("Kundennummer", "{{customerNumber}}", label_width="47%", cond="customerNumber", value_bold=True),
        meta_row("Ihre USt-IdNr.", "{{buyer.vatId}}", label_width="47%", cond="buyer.vatId", value_bold=True)]
body = [
    columns([col("60%", [gap(12)] + address), col("40%", meta)], 0),
    gap(24),
    text("RECHNUNG", "eyebrowSize", "primaryColor", bold=True, margin=[0, 0, 0, 5]),
    text("{{letter.subject?}}", "headingSize", bold=True, hide="anyEmpty", margin=[0, 0, 0, 4]),
    text("{{letter.subtitle?}}", "leadSize", "labelColor", hide="anyEmpty"),
    gap(16),
    text("{{letter.salutation?}}", "letterSize", hide="anyEmpty", margin=[0, 0, 0, 7]),
    text("{{letter.intro?}}", "letterSize", hide="anyEmpty"),
    gap(16),
    items_table([tcol("position", "POS.", "7%"), tcol("description", "LEISTUNG", "53%"),
                 tcol("quantity", "MENGE", "12%", "right"), tcol("unitPrice", "EINZELPREIS", "14%", "right", True),
                 tcol("netAmount", "BETRAG", "14%", "right", True)], size="tableSize", header_color="mutedColor", padding=(5, 2, 5, 6)),
    columns([col("7%", []), col("93%", [summary()])], 0),
    gap(2), solid("#0E5F55", W, 1.5), gap(24),
    columns([
        col("1%", [solid("#0E5F55", 3, 78)]),
        col("49%", [text("Zahlung", "boxTitleSize", bold=True, margin=[10, 0, 0, 6]),
                    columns([col("44%", [text("Fällig", "payLabelSize", "mutedColor", margin=[10, 0, 0, 4]),
                                         text("Zahlungsziel", "payLabelSize", "mutedColor", margin=[10, 0, 0, 4]),
                                         text("Verwendungszweck", "payLabelSize", "mutedColor", margin=[10, 0, 0, 4])]),
                             col("*", [text("bis {{dueDate|date}}", "payLabelSize", bold=True, margin=[0, 0, 0, 4]),
                                       text("{{paymentTerms.description?}}", "payLabelSize", margin=[0, 0, 0, 4]),
                                       text("{{invoiceNumber}}", "payLabelSize", margin=[0, 0, 0, 4])])], 0)]),
        col("1%", [solid("#0E5F55", 3, 78)]),
        col("49%", [text("Bankverbindung", "boxTitleSize", bold=True, margin=[10, 0, 0, 6]),
                    columns([col("29%", [text(l, "payLabelSize", "mutedColor", margin=[10, 0, 0, 4]) for l in ("Kontoinhaber", "IBAN", "BIC", "Bank")]),
                             col("*", [text(v, "payLabelSize", margin=[0, 0, 0, 4]) for v in
                                       ("{{seller.bankAccount.accountHolder?}}", "{{seller.bankAccount.iban?}}",
                                        "{{seller.bankAccount.bic?}}", "{{seller.bankAccount.bankName?}}")])], 0)]),
    ], 4),
    gap(22),
    text("{{notes}}", "smallSize", "labelColor", cond="notes"),
]
footer = [solid("#E2DFD8", W, 0.75), gap(5), columns([
    col("45%", [text("{{seller.name}} · {{seller.street?}} · {{seller.postalCode?}} {{seller.city?}}", "tinySize", "mutedColor", margin=[0, 0, 0, 2]),
                text("Geschäftsführerin: Erika Muster", "tinySize", "mutedColor")]),
    col("31%", [text("Amtsgericht Frankfurt am Main · HRB 000000", "tinySize", "mutedColor", margin=[0, 0, 0, 2]),
                text("USt-IdNr. {{seller.vatId}}", "tinySize", "mutedColor", cond="seller.vatId")]),
    col("24%", [text("{{seller.bankAccount.bankName?}}", "tinySize", "mutedColor", hide="anyEmpty", margin=[0, 0, 0, 2]),
                text("BIC {{seller.bankAccount.bic?}}", "tinySize", "mutedColor", hide="anyEmpty")])], 0)]
save(template("Muster Software Rechnung DE", pg, header, body, footer, header_height=mm(106), footer_height=mm(72)),
     "template.json")
