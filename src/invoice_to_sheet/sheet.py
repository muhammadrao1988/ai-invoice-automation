"""Write the results to one Excel file: a sheet of invoices and a sheet of invoice lines."""

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from .check import line_amount

HEAD = Font(bold=True)
CHECK_FILL = PatternFill("solid", start_color="FFF2CC")  # soft yellow for rows a person should look at


def write(results: list[dict], path: Path) -> None:
    wb = Workbook()
    inv_ws = wb.active
    inv_ws.title = "Invoices"
    inv_ws.append(["File", "Status", "Supplier", "Customer", "Invoice no.", "Date", "Currency",
                   "Subtotal", "Discount", "Tax", "Total", "Reads", "What to check", "Notes"])
    line_ws = wb.create_sheet("Lines")
    line_ws.append(["File", "Invoice no.", "Description", "Quantity", "Unit price", "Line total"])
    for ws in (inv_ws, line_ws):
        for cell in ws[1]:
            cell.font = HEAD
        ws.freeze_panes = "A2"

    for r in results:
        inv = r["invoice"]
        status = "OK" if r["status"] == "ok" else "Please check"
        if inv:
            inv_ws.append([r["file"], status, inv.supplier, inv.customer, inv.invoice_number, inv.invoice_date,
                           inv.currency, inv.subtotal, inv.discount, inv.tax, inv.total, r["attempts"],
                           " ".join(r["problems"]), " ".join(r["notes"])])
            for line in inv.lines:
                line_ws.append([r["file"], inv.invoice_number, line.description, line.quantity,
                                line.unit_price, line_amount(line)])
        else:
            inv_ws.append([r["file"], status, *[""] * 9, r["attempts"], " ".join(r["problems"]), ""])
        if r["status"] != "ok":
            for cell in inv_ws[inv_ws.max_row]:
                cell.fill = CHECK_FILL

    for ws, widths in ((inv_ws, [26, 13, 28, 24, 16, 12, 9, 11, 10, 10, 11, 7, 70, 60]), (line_ws, [26, 16, 44, 10, 11, 11])):
        for i, w in enumerate(widths):
            ws.column_dimensions[chr(65 + i)].width = w
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
