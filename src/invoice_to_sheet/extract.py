"""Read one invoice PDF and ask Claude for its data as structured fields."""

import base64
import json
import os
import subprocess
from pathlib import Path

import anthropic

from pydantic import BaseModel, Field
from pypdf import PdfReader

MODEL = os.environ.get("INVOICE_MODEL", "sonnet")  # --engine cli: Claude Code model alias or full model ID
API_MODEL = os.environ.get("INVOICE_API_MODEL", "claude-opus-5-5")  # --engine api
MEDIA_TYPES = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
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


RETRY_NOTE = ("\n\nA first reading failed these checks:\n{hint}\nRead the invoice again carefully. "
              "Still copy the printed numbers; do not change them to make the sums work.")


def ask(engine: str, text: str = "", hint: str = "", picture: Path | None = None) -> Invoice:
    return (ask_api if engine == "api" else ask_claude)(text, hint, picture)


def ask_api(text: str = "", hint: str = "", picture: Path | None = None) -> Invoice:
    """Uses the Claude API with an API key (ANTHROPIC_API_KEY). Each invoice costs a little money."""
    note = RETRY_NOTE.format(hint=hint) if hint else ""
    if picture:
        data = base64.standard_b64encode(picture.read_bytes()).decode("utf-8")
        media_type = MEDIA_TYPES[picture.suffix.lower()]
        kind = "document" if media_type == "application/pdf" else "image"
        content = [{"type": kind, "source": {"type": "base64", "media_type": media_type, "data": data}},
                   {"type": "text", "text": "Return the data of this invoice." + note}]
    else:
        content = f"Invoice text:\n\n{text}{note}"
    try:
        response = anthropic.Anthropic().beta.messages.parse(
            model=API_MODEL,
            max_tokens=16_000,
            system=ROLE,
            output_config={"effort": "medium"},
            # If the model declines a request, the API retries it on a fallback model in the same call.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": content}],
            output_format=Invoice,
        )
    except anthropic.AuthenticationError:
        raise ExtractError("The API key was rejected. Check ANTHROPIC_API_KEY.")
    except anthropic.RateLimitError:
        raise ExtractError("Rate limited by the API. Try again in a minute, or lower --workers.")
    except anthropic.BadRequestError as e:
        raise ExtractError(f"The API refused the request: {e.message[:200]}")
    except anthropic.APIStatusError as e:
        raise ExtractError(f"API error {e.status_code}. Try again later.")
    except anthropic.APIConnectionError:
        raise ExtractError("Could not reach the Claude API. Check the internet connection.")
    except (anthropic.AnthropicError, TypeError) as e:  # the SDK raises TypeError when it finds no credentials
        raise ExtractError(f"Claude API not set up (is ANTHROPIC_API_KEY set?): {str(e)[:120]}")
    if response.stop_reason == "refusal":
        raise ExtractError("The model declined to read this document.")
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise ExtractError("The answer was cut off or incomplete (very long invoice?).")
    return response.parsed_output


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
        task += RETRY_NOTE.format(hint=hint)
    try:
        result = _run_cli(task, tools)
    except FileNotFoundError:
        raise ExtractError("Claude Code is not installed (no `claude` command). Install it, or use --engine api.")
    except subprocess.TimeoutExpired:
        raise ExtractError("Claude Code did not answer within 5 minutes.")
    try:
        out = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise ExtractError(f"Claude Code failed: {(result.stderr or result.stdout).strip()[:200]}")
    if out.get("is_error") or not out.get("structured_output"):
        raise ExtractError(f"Claude Code returned no result: {str(out.get('result'))[:200]}")
    return Invoice.model_validate(out["structured_output"])


def _run_cli(task: str, tools: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["claude", "-p", "--output-format", "json", "--model", MODEL, *tools,
         "--system-prompt", ROLE, "--json-schema", json.dumps(Invoice.model_json_schema())],
        input=task,
        capture_output=True,
        text=True,
        timeout=300,
        env={k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")},
    )
