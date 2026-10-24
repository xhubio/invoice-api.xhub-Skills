"""Small builder for invoice-api BlockTemplates. Import it in a build script:

    import sys; sys.path.insert(0, "path/to/scripts")
    from template_helpers import *

    tpl = template("Muster GmbH Rechnung", page(margins=(60, 51, 60, 51),
                   colors={"textColor": "#1A1A1A", "mutedColor": "#777777", "primaryColor": "#0E5F55"},
                   sizes={"textSize": 9, "smallSize": 8, "headingSize": 20, "tableSize": 9}),
                   header=[...], body=[...], footer=[...])
    save(tpl, "template.json")

All lengths are PDF points. Colours and font sizes are referenced by token name
(defined once in page()); use hex only where the block requires it (line).

Measured renderer behaviour (invoice-api, 2026-10) - see references/blocktemplate.md:
- margin on blocks is [left, top, right, bottom] (pdfmake order)
- spacer(h) takes about h + 10 pt  -> use gap(pt) instead of spacer()
- line() takes about 25 pt incl. built-in margins -> use solid() for tight rules
- header starts ~5 pt below the page edge; body starts at
  max(margins.top, header_height_mm * 2.835); footer starts at
  page height - max(margins.bottom, footer_height_mm * 2.835)
- header/footer heights in template() are given in MM (renderer behaviour)
- placeholder filters: {{date|date}} -> 02.10.2026, {{date|date:dd.MM.yy}};
  filters work in text blocks only, NOT in keyvalue -> use meta_row()
"""
import base64
import json
import struct
import zlib

__all__ = ["gap", "meta_row", "mm", "page", "template", "save", "text", "image", "image_file", "solid", "line", "spacer", "columns", "col",
           "keyvalue", "kv", "items_table", "tcol", "summary", "qrcode", "epc_qr"]


# ---------- page / template ----------
def page(size="A4", orientation="portrait", font="Roboto", margins=(60, 51, 60, 51), colors=None, sizes=None):
    """margins = (top, right, bottom, left) in pt."""
    t, r, b, l = margins
    base_colors = {"textBg": "#ffffff", "textColor": "#1A1A1A", "labelColor": "#555555", "mutedColor": "#888888",
                   "lineColor": "#E0E0E0", "primaryColor": "#1A1A1A", "tableHeaderBg": "#ffffff"}
    base_sizes = {"textSize": 9, "labelSize": 8.5, "smallSize": 8, "tinySize": 6.5, "headingSize": 20,
                  "leadSize": 10.5, "letterSize": 9.5, "tableSize": 9}
    base_colors.update(colors or {})
    base_sizes.update(sizes or {})
    return {"size": size, "orientation": orientation, "defaultFont": font,
            "margins": {"top": t, "right": r, "bottom": b, "left": l},
            "fontSizes": base_sizes, "colorScheme": base_colors}


def mm(pt):
    """pt -> mm, for header_height/footer_height."""
    return round(pt / 2.835, 2)


def template(name, pg, header=None, body=None, footer=None, header_height=40, footer_height=20,
             description="", locale="de-DE"):
    """header_height / footer_height are in MM (that is how the renderer reads them).
    Body starts at max(margins.top, header_height*2.835 pt)."""
    return {"name": name, "description": description, "version": "1.0.0", "editorVersion": "v2",
            "templateType": "custom", "locale": locale, "lengthUnit": "pt", "page": pg,
            "header": {"blocks": header or [], "height": header_height, "repeatOnAllPages": True},
            "body": {"blocks": body or []},
            "footer": {"blocks": footer or [], "height": footer_height, "repeatOnAllPages": True}}


def save(tpl, path):
    json.dump(tpl, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path


# ---------- blocks ----------
def _cond(b, cond):
    if cond:
        b["condition"] = cond
    return b


def text(content, size="textSize", color="textColor", bold=False, align="left", cond=None, hide=None, margin=None):
    """content may contain placeholders: {{buyer.name}}, optional {{buyer.street?}}.
    hide: 'anyEmpty' or 'allEmpty' hides the line when (any/all) placeholders are empty.
    cond: data path; block is only rendered when it has a value, e.g. 'buyer.contact.name'.
    margin: [left, top, right, bottom] in pt (pdfmake order)."""
    d = {"content": content, "fontSize": {"token": size}, "color": {"token": color}, "bold": bold, "alignment": align}
    if hide:
        d["hideMode"] = hide
    if margin:
        d["margin"] = margin
    return _cond({"type": "text", "data": d}, cond)


def image(src, width, height, align="left"):
    return {"type": "image", "data": {"src": src, "width": width, "height": height, "alignment": align}}


def image_file(path, width, height, align="left"):
    mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
    return image(f"data:{mime};base64," + base64.b64encode(open(path, "rb").read()).decode(), width, height, align)


def _png(rgb, w=4, h=4):
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def solid(hex_color, width, height, align="left"):
    """A filled bar or thin coloured rule as image block - use for coloured areas,
    accent bars and rules that 'line' cannot draw exactly. The renderer keeps the
    image's aspect ratio, so the PNG is generated with the same proportions
    (4 px per pt)."""
    h = hex_color.lstrip("#")
    rgb = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    pw, ph = max(1, round(width * 4)), max(1, round(height * 4))
    return image("data:image/png;base64," + base64.b64encode(_png(rgb, pw, ph)).decode(), width, height, align)


def line(hex_color="#E0E0E0", thickness=0.75, margin=None):
    d = {"color": hex_color, "thickness": thickness}
    if margin:
        d["margin"] = margin
    return {"type": "line", "data": d}


def spacer(height, cond=None):
    return _cond({"type": "spacer", "data": {"height": height}}, cond)


def col(width, blocks):
    """width like '60%' or '*'."""
    return {"width": width, "blocks": blocks, "cells": [{"blocks": json.loads(json.dumps(blocks))}]}


def columns(cols, gap=10, cond=None):
    return _cond({"type": "columns", "data": {"columns": cols, "columnGap": gap}}, cond)


def kv(label, value, align="right", optional=False):
    """One row for keyvalue(). optional=True hides the row when the value is empty."""
    r = {"label": label, "value": value, "valueAlign": align}
    if optional:
        r["optionalMode"] = "optional-hidden"
    return r


def keyvalue(rows, label_width=90, size="labelSize", label_color="mutedColor", value_color="textColor",
             label_bold=False, layout="vertical"):
    return {"type": "keyvalue", "data": {"items": rows, "layout": layout, "fontSize": {"token": size},
            "labelBold": label_bold, "labelColor": {"token": label_color}, "labelWidth": label_width,
            "valueColor": {"token": value_color}}}


def tcol(field, header, width, align="left", currency=False):
    """Table column. field: position, description, quantity, unit, unitPrice, netAmount, taxRate, ..."""
    c = {"field": field, "header": header, "width": width, "align": align}
    if currency:
        c.update({"format": "currency", "currencySymbol": True})
    return c


def items_table(cols, size="tableSize", header_bg="tableHeaderBg", header_color="mutedColor",
                layout="lightHorizontalLines", padding=(6, 6, 6, 6), locale="de-DE",
                decimal=",", group=".", date_format="dd.MM.yyyy"):
    """layout: lightHorizontalLines | noBorders | headerLineOnly | allBorders (as supported by the renderer)."""
    t, r, b, l = padding
    return {"type": "table", "data": {"dataSource": "{{items}}", "columns": cols, "layout": layout,
            "locale": locale, "fontSize": {"token": size}, "showHeader": True, "repeatHeader": True,
            "cellPadding": {"top": t, "right": r, "bottom": b, "left": l},
            "numberFormat": {"group": group, "decimal": decimal}, "dateFormat": date_format,
            "headerFillColor": {"token": header_bg}, "headerTextColor": {"token": header_color}}}


def summary(net_label="Summe netto", tax_label="Umsatzsteuer {{taxRate:percent}}", total_label="Rechnungsbetrag",
            size="tableSize", widths=("*", "auto"), locale="de-DE", decimal=",", group=".",
            label_color="textColor", value_color="textColor"):
    row = lambda label, value, bold=False: {"label": label, "value": value, "valueAlign": "right",
                                            "valueFormat": "currency", "currencySymbol": True, **({"bold": True} if bold else {})}
    return {"type": "summary", "data": {
        "widths": list(widths), "locale": locale, "fontSize": {"token": size}, "dateFormat": "dd.MM.yyyy",
        "numberFormat": {"group": group, "decimal": decimal},
        "headerRows": [row(net_label, "{{subtotal}}")],
        "dynamicRows": {"dataSource": "{{taxSummary}}", "valueField": "taxAmount", "valueFormat": "currency",
                        "labelTemplate": tax_label, "currencySymbol": True},
        "footerRows": [row(total_label, "{{total}}", True)], "separatorBeforeFooter": True,
        "labelColor": {"token": label_color}, "valueColor": {"token": value_color},
        "allowanceChargeLabels": {"allowance": "Nachlass", "charge": "Zuschlag",
                                  "netAfter": "Netto nach Nachlässen und Zuschlägen"}}}


def qrcode(content, size=90, align="center"):
    return {"type": "qrcode", "data": {"content": content, "size": size, "eccLevel": "M", "alignment": align}}


def epc_qr(size=90):
    """GiroCode placeholder - renders only if the payload field is filled."""
    return qrcode("{{epcQrPayload?}}", size)


def gap(pt):
    """Vertical gap of about `pt` points between blocks. Returns a block.
    Small gaps (< 11 pt) become an empty text with bottom margin; larger ones a
    spacer corrected for the renderer's ~10 pt overhead (measured: spacer(10) = 21 pt,
    spacer(20) = 32 pt)."""
    if pt < 11:
        return {"type": "text", "data": {"content": " ", "fontSize": 1, "margin": [0, 0, 0, max(0, pt - 1.2)]}}
    return spacer(round(max(0.0, (pt - 9.7) / 1.12), 1))


def meta_row(label, value, cond=None, label_width="48%", size="labelSize", label_color="mutedColor",
             value_color="textColor", value_bold=False, bottom=5):
    """One label/value row as columns of text blocks, so filters like
    {{issueDate|date}} work (keyvalue does not apply filters). cond hides the
    whole row when the data path is empty, e.g. cond='deliveryDate'."""
    return columns([
        col(label_width, [text(label, size, label_color, margin=[0, 0, 0, bottom])]),
        col("*", [text(value, size, value_color, bold=value_bold, align="right", margin=[0, 0, 0, bottom])]),
    ], 0, cond=cond)
