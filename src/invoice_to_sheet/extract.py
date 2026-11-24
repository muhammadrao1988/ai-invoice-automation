"""Read one invoice PDF and ask Claude for its data as structured fields."""

import json
import os
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field
from pypdf import PdfReader

MODEL = os.environ.get("INVOICE_MODEL", "sonnet")  # Claude Code model alias or full model ID
MIN_TEXT_CHARS = 40  # less than this means a scan or picture: there is no text to read

ROLE = """You read one supplier invoice and return its data.
Rules:
- Copy every number exactly as it is printed on the invoice. Never correct, round or recalculate a number,
  even when the invoice's own arithmetic looks wrong.
- Convert number formats to plain decimals (German "1.234,50" becomes 1234.50).
- Dates as YYYY-MM-DD.
- `tax` is the sum of all tax amounts on the invoice. `discount` is a positive number, or 0 when there is none.
- Many invoices do not print every value. If a value is not printed, return null for numbers and an empty string
  for text. Never calculate a missing value yourself (no line totals from quantity x price, no subtotal from lines).
- `supplier` is the business that issued the invoice; `customer` is who it is addressed to. Do not mix them up."""


class Line(BaseModel):
    description: str
    quantity: float
    unit_price: float
    line_total: float | None = Field(description="As printed; null if the invoice prints no amount per line")


class Invoice(BaseModel):
    supplier: str = Field(description="Who issued the invoice; empty if not printed")
    customer: str = Field(default="", description="Who the invoice is addressed to; empty if not printed")
    invoice_number: str
    invoice_date: str = Field(description="YYYY-MM-DD")
    currency: str = Field(description="ISO code such as EUR, USD, PKR")
    lines: list[Line]
    subtotal: float | None = Field(description="Before discount and tax, as printed; null if not printed")
    discount: float | None = Field(default=None, description="Positive number as printed; null if none")
    tax: float | None = Field(description="Sum of all tax amounts as printed; null if no tax is printed")
    total: float = Field(description="Final amount to pay, as printed")
    notes: str = ""


class ExtractError(Exception):
    pass


def pdf_text(path: Path) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages).strip()


def ask_claude(text: str = "", hint: str = "", picture: Path | None = None) -> Invoice:
    """Uses the Claude Code login (subscription). API keys are removed so they are never used by accident.

    Text invoices are sent as text, with no tools. A scan or photo is opened by Claude with the Read tool,
    which is the only tool allowed, so text inside a document cannot make it do anything else.
    """
    if picture:
        task = f"Open the invoice file {picture.resolve()} with the Read tool and look at it, then return its data."
        tools = ["--tools", "Read", "--allowedTools", "Read", "--add-dir", str(picture.resolve().parent)]
    else:
        task = f"Invoice text:\n\n{text}"
        tools = ["--tools", ""]
    if hint:
        task += f"\n\nA first reading failed these checks:\n{hint}\nRead the invoice again carefully. " \
                "Still copy the printed numbers; do not change them to make the sums work."
    result = subprocess.run(
        ["claude", "-p", "--output-format", "json", "--model", MODEL, *tools,
         "--system-prompt", ROLE, "--json-schema", json.dumps(Invoice.model_json_schema())],
        input=task,
        capture_output=True,
        text=True,
        timeout=300,
        env={k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")},
    )
    try:
        out = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise ExtractError(f"Claude CLI failed: {(result.stderr or result.stdout).strip()[:200]}")
    if out.get("is_error") or not out.get("structured_output"):
        raise ExtractError(f"Claude CLI returned no result: {str(out.get('result'))[:200]}")
    return Invoice.model_validate(out["structured_output"])
