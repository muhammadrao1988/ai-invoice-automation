"""invoices <folder>: read every invoice (PDF, scan or photo) in a folder into one spreadsheet, and check each one."""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import sheet
from .check import review
from .extract import MIN_TEXT_CHARS, ExtractError, ask_claude, pdf_text

FILE_TYPES = {".pdf", ".jpg", ".jpeg", ".png"}
MAX_READS = 2  # one normal reading, then one careful re-reading if the sums do not match


def process(path: Path) -> dict:
    """Read, check, and re-read once if a check fails. Never guesses: what still fails is flagged."""
    result = {"file": path.name, "status": "check", "invoice": None, "problems": [], "notes": [], "attempts": 0}
    text = ""
    if path.suffix.lower() == ".pdf":
        try:
            text = pdf_text(path)
        except Exception as e:
            result["problems"] = [f"Could not open the PDF: {e}"]
            return result
    picture = path if len(text) < MIN_TEXT_CHARS else None  # a scan or photo: Claude looks at the page itself

    hint = ""
    for attempt in range(1, MAX_READS + 1):
        result["attempts"] = attempt
        try:
            invoice = ask_claude(text, hint, picture)
        except ExtractError as e:
            result["problems"] = [str(e)]
            return result
        found, notes = review(invoice)
        if picture:
            notes.insert(0, "Read from a picture (scan or photo).")
        result["invoice"], result["problems"], result["notes"] = invoice, found, notes
        if not found:
            result["status"] = "ok"
            return result
        hint = "\n".join(f"- {p}" for p in found)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Read PDF invoices into one spreadsheet and check every total.")
    parser.add_argument("folder", help="Folder with invoice PDFs")
    parser.add_argument("--out", default="out", help="Folder for the results (default ./out)")
    parser.add_argument("--workers", type=int, default=4, help="Invoices read at the same time (default 4)")
    args = parser.parse_args()

    files = sorted(p for p in Path(args.folder).iterdir() if p.suffix.lower() in FILE_TYPES)
    if not files:
        raise SystemExit(f"No invoices (PDF, JPG, PNG) in {args.folder}")
    print(f"Reading {len(files)} invoices …")
    start = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(process, files))
    seconds = time.time() - start

    out = Path(args.out)
    sheet.write(results, out / "invoices.xlsx")
    (out / "invoices.json").write_text(json.dumps(
        [{**r, "invoice": r["invoice"].model_dump() if r["invoice"] else None} for r in results], indent=1))

    ok = [r for r in results if r["status"] == "ok"]
    reread = [r for r in ok if r["attempts"] > 1]
    to_check = [r for r in results if r["status"] != "ok"]
    print(f"\n{len(files)} invoices read in {seconds:.0f} seconds.")
    print(f"{len(ok)} passed every check" + (f" ({len(reread)} after a second, careful reading)." if reread else "."))
    if to_check:
        print(f"{len(to_check)} need a look:")
        for r in to_check:
            print(f"  - {r['file']}: {' '.join(r['problems'])}")
    print(f"\nSpreadsheet: {(out / 'invoices.xlsx').resolve()}")
