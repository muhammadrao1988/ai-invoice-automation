"""Check the tool against public sample invoices (Hugging Face: AyoubChLin/CompanyDocuments, Apache-2.0).

    uv run python eval_public.py fetch                 # download 20 invoices into samples/public/
    uv run invoices samples/public --out out-public
    uv run python eval_public.py

These invoices share one simple layout, so the correct values are read here with plain pattern matching,
without AI, and compared with what the tool returned.
"""

import json
import re
import sys
import urllib.request
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).parent
FOLDER = ROOT / "samples" / "public"
BASE = "https://huggingface.co/datasets/AyoubChLin/CompanyDocuments/resolve/main/invoices/"
ORDER_IDS = range(10248, 11078, 43)  # 20 invoices spread across the collection
LINE = re.compile(r"^\d+ (?P<name>.+) (?P<qty>\d+) (?P<price>\d+(?:\.\d+)?)$")


def fetch() -> None:
    FOLDER.mkdir(parents=True, exist_ok=True)
    for n in ORDER_IDS:
        urllib.request.urlretrieve(f"{BASE}invoice_{n}.pdf", FOLDER / f"invoice_{n}.pdf")
    print(f"{len(ORDER_IDS)} invoices saved to {FOLDER}")


def truth(path: Path) -> dict:
    text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    lines = [m.groupdict() for row in text.splitlines() if (m := LINE.match(row.strip()))]
    return {
        "invoice_number": re.search(r"Order ID: (\d+)", text)[1],
        "invoice_date": re.search(r"Order Date: ([\d-]+)", text)[1],
        "total": float(re.search(r"TotalPrice ([\d.]+)", text)[1]),
        "lines": [(float(l["qty"]), float(l["price"])) for l in lines],
    }


def main() -> None:
    results = {r["file"]: r for r in json.loads((ROOT / "out-public" / "invoices.json").read_text())}
    files = sorted(FOLDER.glob("*.pdf"))
    values_right = values = passed = sums_agree = flagged_right = 0
    for path in files:
        exp, got = truth(path), results[path.name]
        inv = got["invoice"] or {}
        got_lines = [(l["quantity"], l["unit_price"]) for l in inv.get("lines", [])]
        checks = [str(inv.get("invoice_number")) == exp["invoice_number"], inv.get("invoice_date") == exp["invoice_date"],
                  abs((inv.get("total") or 0) - exp["total"]) <= 0.01, got_lines == exp["lines"]]
        values += len(checks)
        values_right += sum(checks)
        agrees = abs(sum(q * p for q, p in exp["lines"]) - exp["total"]) <= 0.02  # does the invoice add up at all?
        sums_agree += agrees
        passed += got["status"] == "ok"
        flagged_right += (got["status"] == "ok") == agrees
        if not all(checks) or (got["status"] == "ok") != agrees:
            print(f"BAD {path.name}: values {checks}, status {got['status']}, invoice adds up: {agrees}")
    print(f"Invoices: {len(files)}")
    print(f"Values correct (number, date, total, all lines): {values_right}/{values}")
    print(f"Invoices whose own sums agree: {sums_agree}; passed by the tool: {passed}")
    print(f"Pass / flag decision correct: {flagged_right}/{len(files)}")


if __name__ == "__main__":
    fetch() if sys.argv[1:] == ["fetch"] else main()
