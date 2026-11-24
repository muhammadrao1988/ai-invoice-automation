# AI invoice automation

An AI tool that turns a folder of invoices into a checked spreadsheet in seconds, built with Claude Code.

Reads a folder of invoices (PDFs, scans and photos) into one spreadsheet, checks every total, and tells you which invoices a person
should look at.

## The problem
Typing invoices into a spreadsheet by hand is slow, and typing mistakes are easy to miss.

## What it does
1. **Read:** opens each PDF and takes out its text. A scan or a photo (PDF without text, JPG, PNG) has no text,
   so Claude looks at the page itself.
2. **Pick out the data:** Claude returns supplier, invoice number, date, currency, each line, tax and total.
3. **Check:** plain code (no AI) adds up the lines, the discount and the tax, and compares them with the printed totals.
4. **Read again:** if a sum does not match, the invoice is read once more, with the failed check as a hint.
5. **Flag:** what still does not match is marked "Please check". The tool never changes a number to make a sum work.
6. **Write:** one Excel file with an "Invoices" sheet and a "Lines" sheet.

## Run
```bash
uv run invoices samples/invoices      # results in ./out/invoices.xlsx
uv run python eval.py                 # compare with the known correct answers
uv run python eval_public.py fetch    # optional: download 20 public sample invoices, then
uv run invoices samples/public --out out-public && uv run python eval_public.py
uv run python samples/make_samples.py # rebuild the sample invoices
```
It uses your Claude Code login (subscription). API keys in the environment are ignored on purpose.
Set `INVOICE_MODEL` to use another model (default: `sonnet`).

## Results (2026-11-24)
| Test set | Invoices | Time | Values correct | Pass / flag decision correct |
|---|---|---|---|---|
| Own samples (`samples/invoices`) | 12 | 25 s | 96 of 96 fields, 35 of 35 lines | 12 of 12 (11 passed, including the scan; 1 flagged: a supplier's wrong total) |
| Public samples (`samples/public`) | 20 | 33 s | 80 of 80 | 20 of 20 (all passed) |
| Public invoice pictures (FATURA) | 8 | 42 s | 21 of 21 printed amounts | 8 of 8 (all flagged, correctly: see below) |

- **Own samples:** invented suppliers in four layouts, with English, German and American number and date styles,
  two tax rates, discounts, one invoice whose own total is wrong, and one scan. Checked by `eval.py`.
- **Public samples:** 20 invoices from the Hugging Face dataset `AyoubChLin/CompanyDocuments` (Apache-2.0), fetched by
  `uv run python eval_public.py fetch`. They print no supplier, no line totals and no tax. The correct values are
  read with plain pattern matching, without AI, by `eval_public.py`.

- **Invoice pictures:** 8 JPG images from the FATURA collection, taken from the Hugging Face copy
  `mathieu1256/FATURA2-invoices` (listed there as CC BY 4.0; not confirmed on the original page, so the pictures are
  not included here). Eight different layouts. Every subtotal, tax and total the tool read matches the collection's
  own labels. All 8 were flagged, and that is correct: these invoices are computer-made with random amounts, so
  their own sums do not agree (for example 186.67 + 8.39 tax printed as a total of 192.84), and two print no
  invoice number. The labels do not cover the table rows, so the invoice lines were not verified.
- The first set now has 96 fields and 35 lines because the scan is read too.

### What the public samples taught
The first version passed 0 of these 20. It read them correctly, but it treated every value that an invoice does not
print (line totals, subtotal, supplier) as an error. Now only printed values are checked; missing ones are
calculated and listed in a "Notes" column.

## Limits
- Tested on 40 invoices: 12 made for this project, 20 public ones that share one simple layout, and 8 public pictures. Real invoices
  from many suppliers are messier; expect more "Please check" rows.
- Scans and photos are read by looking at the page. That is slower and less certain than reading text; the
  "Notes" column says when an invoice was read from a picture. Tested on 9 pictures only, all clean and straight.
- For pictures, Claude uses one tool (Read) to open the file. No other tool is allowed, but treat documents from
  unknown senders with the usual care.
- A passed check means the invoice's own sums agree. It does not prove every value was read correctly
  (a wrong supplier name would still pass).
