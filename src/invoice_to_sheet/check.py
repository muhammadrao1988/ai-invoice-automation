"""Arithmetic checks on a read invoice. No AI here: plain sums, so the result can be trusted.

Only printed values are checked. A value the invoice does not print is calculated and listed in the notes.
"""

from .extract import Invoice

TOLERANCE = 0.02  # rounding differences of a cent or two are normal


def line_amount(line) -> float:
    return line.line_total if line.line_total is not None else round(line.quantity * line.unit_price, 2)


def review(inv: Invoice) -> tuple[list[str], list[str]]:
    """Returns (problems, notes). Problems send the invoice to a person; notes only explain."""
    problems: list[str] = []
    notes: list[str] = []
    if not inv.lines:
        problems.append("No invoice lines were found.")
    for n, line in enumerate(inv.lines, 1):
        expected = round(line.quantity * line.unit_price, 2)
        if line.line_total is not None and abs(expected - line.line_total) > TOLERANCE:
            problems.append(f"Line {n}: {line.quantity:g} x {line.unit_price:.2f} = {expected:.2f}, "
                            f"but the line total says {line.line_total:.2f}.")
    if inv.lines and all(line.line_total is None for line in inv.lines):
        notes.append("Line totals are not printed; calculated from quantity x unit price.")

    lines_sum = round(sum(line_amount(line) for line in inv.lines), 2)
    if inv.subtotal is None:
        subtotal = lines_sum
        notes.append("Subtotal is not printed; calculated from the lines.")
    else:
        subtotal = inv.subtotal
        if abs(lines_sum - subtotal) > TOLERANCE:
            problems.append(f"Lines add up to {lines_sum:.2f}, but the subtotal says {subtotal:.2f}.")
    discount, tax = inv.discount or 0, inv.tax or 0
    if inv.tax is None:
        notes.append("No tax is printed.")
    expected_total = round(subtotal - discount + tax, 2)
    if abs(expected_total - inv.total) > TOLERANCE:
        problems.append(f"Subtotal {subtotal:.2f} - discount {discount:.2f} + tax {tax:.2f} "
                        f"= {expected_total:.2f}, but the total says {inv.total:.2f}.")
    for name in ("invoice_number", "invoice_date"):
        if not getattr(inv, name):
            problems.append(f"Missing {name.replace('_', ' ')}.")
    if not inv.supplier:
        notes.append("No supplier name is printed.")
    return problems, notes
