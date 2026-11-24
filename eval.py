"""Compare the tool's results with the known correct answers for the sample invoices.

    uv run invoices samples/invoices
    uv run python eval.py

Two questions: are the values right, and did the tool flag exactly the invoices it should flag?
"""

import json
from pathlib import Path

ROOT = Path(__file__).parent
FIELDS = ["supplier", "invoice_number", "invoice_date", "currency", "subtotal", "discount", "tax", "total"]


def same(a, b) -> bool:
    if isinstance(b, (int, float)):
        return abs(float(a or 0) - b) <= 0.01
    return str(a).strip().lower() == str(b).strip().lower()


def main() -> None:
    expected = json.loads((ROOT / "samples" / "expected.json").read_text())
    results = {r["file"]: r for r in json.loads((ROOT / "out" / "invoices.json").read_text())}
    right = total = lines_right = lines_total = flags_right = 0
    for file, exp in expected.items():
        got = results.get(file)
        status = got["status"] if got else "missing"
        flag_ok = status == exp["status"]
        flags_right += flag_ok
        wrong = []
        inv = got and got["invoice"]
        if inv:
            for f in FIELDS:
                total += 1
                if same(inv[f], exp[f]):
                    right += 1
                else:
                    wrong.append(f"{f}: got {inv[f]!r}, expected {exp[f]!r}")
            lines_total += len(exp["lines"])
            for got_line, exp_line in zip(inv["lines"], exp["lines"]):
                if all(same(got_line[k], exp_line[k]) for k in ("quantity", "unit_price", "line_total")):
                    lines_right += 1
                else:
                    wrong.append(f"line {exp_line['description']!r}: got {got_line}")
        mark = "ok " if flag_ok and not wrong else "BAD"
        print(f"{mark} {file:36} status {status:5} (expected {exp['status']})" + ("".join(f"\n      {w}" for w in wrong)))
    print(f"\nFields correct:  {right}/{total}")
    print(f"Lines correct:   {lines_right}/{lines_total}")
    print(f"Flags correct:   {flags_right}/{len(expected)}  (flagged exactly the invoices that need a person)")


if __name__ == "__main__":
    main()
