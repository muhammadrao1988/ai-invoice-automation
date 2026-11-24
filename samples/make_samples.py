"""Create the sample invoices (invented suppliers) and the expected answers used by eval.py.

    uv run python samples/make_samples.py

Four layouts, three number and date styles, and a few awkward cases on purpose:
two tax rates, discounts, a supplier's own wrong total, and a scan with no text.
"""

import json
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

HERE = Path(__file__).parent
OUT = HERE / "invoices"
W, H = A4

# layout: table | plain | german | reordered.  lines: (description, quantity, unit price, tax rate %)
INVOICES = [
    dict(file="01-northfield-office.pdf", supplier="Northfield Office Supplies Ltd", number="NF-2026-0412",
         date=date(2026, 11, 3), currency="EUR", layout="table",
         lines=[("A4 copy paper, box of 5 reams", 6, 24.50, 23), ("Ballpoint pens, pack of 50", 3, 11.90, 23),
                ("Desk organiser, black", 4, 18.75, 23)]),
    dict(file="02-harbour-print.pdf", supplier="Harbour Print & Sign", number="INV-7731",
         date=date(2026, 11, 5), currency="EUR", layout="plain", discount=10.00,
         lines=[("Business cards, 500 pcs", 2, 39.00, 23), ("Roll-up banner 85x200 cm", 1, 89.00, 23)]),
    dict(file="03-bergmann-buerobedarf.pdf", supplier="Bergmann Bürobedarf GmbH", number="RE-2026-1187",
         date=date(2026, 11, 6), currency="EUR", layout="german",
         lines=[("Kopierpapier A4, 500 Blatt", 20, 4.95, 19), ("Tonerkartusche schwarz", 2, 64.90, 19),
                ("Ordner breit, grau", 15, 2.49, 19), ("Schreibtischlampe LED", 1, 39.90, 19)]),
    dict(file="04-summit-cloud.pdf", supplier="Summit Cloud Services Inc.", number="SC-100482",
         date=date(2026, 11, 1), currency="USD", layout="reordered",
         lines=[("Cloud server, standard plan (month)", 3, 48.00, 8.25), ("Managed backups (month)", 3, 12.00, 8.25),
                ("Support hours", 2, 95.00, 8.25)]),
    dict(file="05-greenleaf-catering.pdf", supplier="Greenleaf Catering", number="GC-2291",
         date=date(2026, 11, 7), currency="EUR", layout="table",
         lines=[("Lunch buffet per person", 24, 14.50, 13.5), ("Soft drinks, case of 24", 3, 16.80, 23),
                ("Coffee and tea service", 1, 45.00, 13.5)]),
    # The supplier added it up wrong: the printed total is 25.00 too high. The tool must flag this, not fix it.
    dict(file="06-atlas-freight.pdf", supplier="Atlas Freight Co.", number="AF-55610",
         date=date(2026, 11, 8), currency="EUR", layout="plain", total_error=25.00,
         lines=[("Pallet delivery, Dublin to Cork", 2, 135.00, 23), ("Tail-lift surcharge", 2, 22.50, 23)]),
    dict(file="07-lumen-electrical.pdf", supplier="Lumen Electrical Wholesale", number="LEW-08841",
         date=date(2026, 11, 10), currency="EUR", layout="table",
         lines=[("Cable 2.5 mm, per metre", 12.5, 1.84, 23), ("Socket, double, white", 10, 6.35, 23),
                ("LED panel 60x60", 8, 27.90, 23), ("Junction box IP65", 14, 3.20, 23),
                ("Cable ties, pack of 100", 5, 2.95, 23), ("Circuit breaker 16A", 6, 9.40, 23)]),
    dict(file="08-mueller-werkzeuge.pdf", supplier="Müller & Söhne Werkzeuge", number="2026-004417",
         date=date(2026, 11, 11), currency="EUR", layout="german", discount=50.00,
         lines=[("Akku-Bohrschrauber 18 V", 3, 289.00, 19), ("Bit-Satz 32-teilig", 5, 24.90, 19),
                ("Werkzeugkoffer leer", 2, 121.50, 19)]),
    dict(file="09-pixelworks-design.pdf", supplier="Pixelworks Design Studio", number="PW-0098",
         date=date(2026, 11, 12), currency="EUR", layout="plain",
         lines=[("Logo design, fixed price", 1, 650.00, 0)]),
    dict(file="10-karachi-packaging.pdf", supplier="Karachi Packaging Traders", number="KPT/26/1930",
         date=date(2026, 11, 13), currency="PKR", layout="table",
         lines=[("Corrugated carton 12x10x8 in", 500, 78.00, 18), ("Packing tape 2 in, brown", 120, 145.00, 18),
                ("Bubble wrap roll 50 m", 15, 2350.00, 18)]),
    # A scan: the PDF holds only a picture of the page, so the tool has to look at it instead of reading text.
    dict(file="11-old-mill-stationery-scan.pdf", supplier="Old Mill Stationery", number="OM-3307",
         date=date(2026, 11, 14), currency="EUR", layout="table", scan=True,
         lines=[("Notebooks A5, pack of 10", 4, 12.00, 23), ("Whiteboard markers, set of 4", 6, 5.50, 23)]),
    dict(file="12-brightside-cleaning.pdf", supplier="Brightside Cleaning Services", number="BCS-2026-0457",
         date=date(2026, 11, 15), currency="GBP", layout="reordered",
         lines=[("Office cleaning, hours", 7.5, 18.00, 20), ("Window cleaning, visit", 1, 60.00, 20),
                ("Cleaning supplies", 1, 23.40, 20)]),
]


def money(x: float, german: bool = False) -> str:
    s = f"{x:,.2f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".") if german else s


def qty(x: float, german: bool = False) -> str:
    s = f"{x:g}"
    return s.replace(".", ",") if german else s


def totals(inv: dict) -> dict:
    lines = [dict(description=d, quantity=q, unit_price=p, line_total=round(q * p, 2), rate=r)
             for d, q, p, r in inv["lines"]]
    subtotal = round(sum(l["line_total"] for l in lines), 2)
    discount = inv.get("discount", 0.0)
    share = (subtotal - discount) / subtotal  # the discount lowers each rate's taxable amount equally
    taxes = {}
    for l in lines:
        taxes[l["rate"]] = taxes.get(l["rate"], 0) + l["line_total"] * share
    taxes = {r: round(base * r / 100, 2) for r, base in sorted(taxes.items()) if r}
    tax = round(sum(taxes.values()), 2)
    total = round(subtotal - discount + tax + inv.get("total_error", 0.0), 2)
    return dict(lines=lines, subtotal=subtotal, discount=discount, taxes=taxes, tax=tax, total=total)


def rows(inv: dict, t: dict) -> list[str]:
    """The invoice as lines of text; each layout uses different words, column order and number style."""
    cur, layout, d = inv["currency"], inv["layout"], inv["date"]
    out = [inv["supplier"], ""]
    if layout == "table":
        out += ["INVOICE", f"Invoice no: {inv['number']}", f"Date: {d.strftime('%d %B %Y')}", f"Currency: {cur}", "",
                f"{'Description':<40}{'Qty':>8}{'Unit price':>14}{'Amount':>14}"]
        out += [f"{l['description']:<40}{qty(l['quantity']):>8}{money(l['unit_price']):>14}{money(l['line_total']):>14}"
                for l in t["lines"]]
        out += ["", f"{'Subtotal':>62}{money(t['subtotal']):>14}"]
        if t["discount"]:
            out.append(f"{'Discount':>62}{'-' + money(t['discount']):>14}")
        out += [f"{'VAT ' + format(r, 'g') + '%':>62}{money(a):>14}" for r, a in t["taxes"].items()]
        out.append(f"{'Total ' + cur:>62}{money(t['total']):>14}")
    elif layout == "plain":
        out += [f"Invoice {inv['number']}   dated {d.strftime('%d/%m/%Y')}", "", "For the following:"]
        out += [f"  {qty(l['quantity'])} x {l['description']} @ {money(l['unit_price'])} = {money(l['line_total'])}"
                for l in t["lines"]]
        out += ["", f"Net amount: {cur} {money(t['subtotal'])}"]
        if t["discount"]:
            out.append(f"Less loyalty discount: {cur} {money(t['discount'])}")
        if t["taxes"]:
            out += [f"VAT at {r:g}%: {cur} {money(a)}" for r, a in t["taxes"].items()]
        else:
            out.append("VAT: not charged (reverse charge)")
        out.append(f"Amount due: {cur} {money(t['total'])}")
    elif layout == "german":
        out += ["RECHNUNG", f"Rechnungsnummer: {inv['number']}", f"Datum: {d.strftime('%d.%m.%Y')}", "",
                f"{'Menge':<8}{'Bezeichnung':<40}{'Einzelpreis':>14}{'Gesamt':>14}"]
        out += [f"{qty(l['quantity'], True):<8}{l['description']:<40}{money(l['unit_price'], True) + ' €':>14}"
                f"{money(l['line_total'], True) + ' €':>14}" for l in t["lines"]]
        out += ["", f"{'Zwischensumme':>62}{money(t['subtotal'], True) + ' €':>14}"]
        if t["discount"]:
            out.append(f"{'Rabatt':>62}{'-' + money(t['discount'], True) + ' €':>14}")
        out += [f"{'MwSt. ' + format(r, 'g') + ' %':>62}{money(a, True) + ' €':>14}" for r, a in t["taxes"].items()]
        out.append(f"{'Gesamtbetrag':>62}{money(t['total'], True) + ' €':>14}")
    else:  # reordered: amount first, American date
        out += [f"Invoice #{inv['number']}", f"Issued {d.strftime('%b')} {d.day}, {d.year}", "",
                f"{'Amount':>12}  {'Qty':>6}  {'Item':<38}{'Rate':>10}"]
        out += [f"{money(l['line_total']):>12}  {qty(l['quantity']):>6}  {l['description']:<38}{money(l['unit_price']):>10}"
                for l in t["lines"]]
        out += ["", f"Subtotal ({cur}): {money(t['subtotal'])}"]
        out += [f"Sales tax {r:g}%: {money(a)}" for r, a in t["taxes"].items()]
        out.append(f"Balance due ({cur}): {money(t['total'])}")
    footer = "Zahlbar innerhalb von 30 Tagen. Vielen Dank für Ihren Auftrag." if layout == "german" \
        else "Payment within 30 days. Thank you for your business."
    return out + ["", footer]


def draw_pdf(path: Path, text_rows: list[str]) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    y = H - 60
    for i, row in enumerate(text_rows):
        c.setFont("Courier-Bold" if i == 0 else "Courier", 13 if i == 0 else 8.5)
        c.drawString(50, y, row)
        y -= 20 if i == 0 else 14
    c.save()


def draw_scan(path: Path, text_rows: list[str]) -> None:
    img = Image.new("L", (1240, 1754), 245)  # A4 at 150 dpi, slightly grey like a scan
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=19)
    for i, row in enumerate(text_rows):
        draw.text((90, 110 + i * 30), row, fill=40, font=font)
    img = img.rotate(1.2, fillcolor=245)
    c = canvas.Canvas(str(path), pagesize=A4)
    c.drawImage(ImageReader(img), 0, 0, width=W, height=H)
    c.save()


def main() -> None:
    OUT.mkdir(exist_ok=True)
    expected = {}
    for inv in INVOICES:
        t = totals(inv)
        text_rows = rows(inv, t)
        (draw_scan if inv.get("scan") else draw_pdf)(OUT / inv["file"], text_rows)
        expected[inv["file"]] = dict(
            supplier=inv["supplier"], invoice_number=inv["number"], invoice_date=inv["date"].isoformat(),
            currency=inv["currency"], subtotal=t["subtotal"], discount=t["discount"], tax=t["tax"], total=t["total"],
            lines=[{k: l[k] for k in ("description", "quantity", "unit_price", "line_total")} for l in t["lines"]],
            status="check" if inv.get("total_error") else "ok",
        )
    (HERE / "expected.json").write_text(json.dumps(expected, indent=1, ensure_ascii=False))
    print(f"{len(INVOICES)} sample invoices written to {OUT}")


if __name__ == "__main__":
    main()
