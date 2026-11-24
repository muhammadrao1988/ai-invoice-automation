# AI invoice automation

Typing invoices into a spreadsheet is slow, and the mistakes are the kind nobody notices until month end. This is
the first project in a series where I take a manual job and automate it with Claude Code.

You give it a folder of invoices (PDFs, scans or phone photos). It gives you one spreadsheet, and it tells you which
invoices you should look at yourself.

```
$ uv run invoices samples/invoices

12 invoices read in 25 seconds.
11 passed every check.
1 need a look:
  - 06-atlas-freight.pdf: Subtotal 315.00 - discount 0.00 + tax 72.45 = 387.45, but the total says 412.45.
```

That last line is the part I care about. The supplier added up their own invoice wrong, and the tool did not
quietly "fix" it. It told me.

## How it works

1. **Read.** Text PDFs are read as text. A scan or a photo has no text, so Claude looks at the page itself.
2. **Pick out the data.** Supplier, customer, invoice number, date, currency, every line, tax and total.
3. **Check.** Plain Python, no AI, adds up the lines, discount and tax and compares them with what is printed.
4. **Read again.** If a sum is off, the invoice is read one more time with the failed check as a hint.
5. **Flag.** If it is still off, the row is marked "Please check". A number is never changed to make a sum work.
6. **Write.** One Excel file: an "Invoices" sheet and a "Lines" sheet.

The idea behind steps 3 to 5: I don't trust an AI answer just because it looks right, so the tool has to prove its
own work with arithmetic, and say so when it can't.

## Setup

You need Python 3.12 or newer and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/muhammadrao1988/ai-invoice-automation.git
cd ai-invoice-automation
uv sync
```

Then pick **one** of the two ways to reach Claude.

### Option A: your Claude subscription (what I use)

No API key and no extra bill. The tool calls the Claude Code command line, which uses your Claude login.

1. Install Claude Code: see the [official guide](https://code.claude.com/docs).
2. Run `claude` once in a terminal and sign in with your Claude account (type `/login` if it does not ask).
3. Check that it answers: `claude -p "say hello"`
4. Run the tool: `uv run invoices samples/invoices`

On a server or in CI, where you cannot sign in through a browser, run `claude setup-token` on your own machine.
It creates a long-lived token for your subscription and tells you how to pass it to the other machine (as the
`CLAUDE_CODE_OAUTH_TOKEN` environment variable). Treat that token like a password.

In this mode the tool ignores any `ANTHROPIC_API_KEY` in your environment, on purpose, so you never get an API bill
by accident.

### Option B: an API key

Use this if you have no subscription, or want to run it inside your own product. You pay per invoice.

1. Create a key in the [Claude Console](https://platform.claude.com/).
2. Set it and run with `--engine api`:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
uv run invoices samples/invoices --engine api
```

Keep the key out of the repository. Honest note: I built this mode from the official SDK documentation, and I have
checked that it fails cleanly without a key or with a wrong one, but I have not yet run it with a paid key.

### Settings

| Setting | Default | What it does |
|---|---|---|
| `--engine cli` / `--engine api` | `cli` | Subscription login or API key (also `INVOICE_ENGINE`) |
| `--out` | `out` | Folder for the spreadsheet |
| `--workers` | `4` | How many invoices are read at the same time |
| `INVOICE_MODEL` | `sonnet` | Model for the subscription mode |
| `INVOICE_API_MODEL` | `claude-opus-5-5` | Model for the API mode |

## Does it actually work?

I tested it three ways, and the second one humbled me.

| Test set | Invoices | Time | Values correct | Pass / flag decision correct |
|---|---|---|---|---|
| My own samples (`samples/invoices`) | 12 | 25 s | 96 of 96 fields, 35 of 35 lines | 12 of 12 |
| Public text invoices | 20 | 33 s | 80 of 80 | 20 of 20 |
| Public invoice pictures (FATURA) | 8 | 42 s | 21 of 21 printed amounts | 8 of 8 |

**My own samples.** Twelve invented suppliers in four layouts: English, German and American number and date styles,
two tax rates, discounts, one supplier's wrong total, and one scan. `uv run python eval.py` compares the result with
the known answers.

**Public text invoices.** Twenty invoices from the Hugging Face dataset
[AyoubChLin/CompanyDocuments](https://huggingface.co/datasets/AyoubChLin/CompanyDocuments) (Apache-2.0). My first
version scored 100% on my own samples and then passed **0 of 20** of these. It read them fine. The problem was me:
I had assumed every invoice prints a supplier name, line totals and a subtotal, and these print none of them, so
everything was flagged. Now only printed values are checked, missing ones are calculated, and a "Notes" column says
which. Lesson I keep relearning: test data you write yourself is too kind.

```bash
uv run python eval_public.py fetch
uv run invoices samples/public --out out-public
uv run python eval_public.py
```

**Public invoice pictures.** Eight JPG images in eight layouts from the FATURA collection (I used the Hugging Face
copy `mathieu1256/FATURA2-invoices`; I could not confirm its licence on the original page, so the pictures are not
in this repository). Every amount the tool read matches the collection's labels. All eight were flagged, and that is
correct: the collection is computer-made with random numbers, so the invoices do not add up (one prints
186.67 + 8.39 tax as a total of 192.84), and two have no invoice number.

## What it does not do yet

- It has seen 40 invoices, all clean. Real ones from many suppliers are messier; expect more "Please check" rows.
- Pictures were tested on 9 clean, straight images. No blurry or tilted phone photos yet.
- For the picture test, only totals were verified. The labels do not cover the table rows.
- A passed check means the invoice's own sums agree. A misread supplier name would still pass.
- For pictures in subscription mode, Claude opens the file with one tool (Read) and nothing else. Still, treat
  documents from unknown senders with normal care.

## What's next

This is episode one of a series: manual work turned into automation, then a chatbot done properly (evals,
hallucination, guardrails). Ideas and bug reports are welcome in the issues.

Built by [Muhammad Rao](https://github.com/muhammadrao1988) with Claude Code. MIT licence.
