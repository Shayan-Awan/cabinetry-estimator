# Field Ticket-to-Invoice

A single-user application for turning signed field tickets into a draft invoice
and an ordered backup package. It runs entirely on one laptop: no server, no
cloud account, no Docker, and no document ever leaves the machine.

> **Status: Phase 1 of 4 (local foundation).**
> You can enter company details, customers, projects, purchase orders and rate
> cards. Ticket upload, AI extraction, validation and invoice generation arrive
> in Phases 2–4.

**AI extraction must be reviewed by a person.** The model assists with data
entry. It never chooses a rate, calculates a total, judges a signature, or
sends anything to a client.

---

## Requirements

- Python 3.11 or newer (3.12 recommended)
- About 16 GB of RAM if you want the local model to be usable
- [Ollama](https://ollama.com) — not needed until Phase 2

---

## Setup — Windows

Open PowerShell in the folder where you want the application to live.

```powershell
git clone <repository-url> field-ticket-invoice
cd field-ticket-invoice

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

If PowerShell refuses to run the activation script, allow it for this session:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

Then start the application:

```powershell
streamlit run app.py
```

Open <http://127.0.0.1:8501> in a browser. On first launch the `data\` folder
and the database are created automatically — there is no migration step to run.

## Setup — macOS and Linux

```bash
git clone <repository-url> field-ticket-invoice
cd field-ticket-invoice

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

## The local model (needed from Phase 2)

```bash
ollama pull qwen3.5:4b
```

> **Check this before Phase 2 starts.** Field tickets are frequently
> photographed rather than exported as text, so the model must accept **images**,
> not just text. Several model families on Ollama publish vision under a separate
> tag from the base text model. If `qwen3.5:4b` turns out to be text-only, or the
> tag is unavailable, pick a small vision-capable tag instead and set it under
> **Settings and Backup → System → Ollama model** — no code change is needed.
>
> On a laptop with 8 GB of RAM, use a smaller tag; with 32 GB, still start small
> and only move up if accuracy proves inadequate.

Ollama listens on `127.0.0.1:11434` by default. Leave it that way.

---

## What Phase 1 gives you

| Screen | What it does |
|---|---|
| **Home** | Setup checklist and where your data lives |
| **Dashboard** | Record counts and anything blocking setup |
| **Customers and Projects** | Create and edit customers and their projects |
| **Rates and POs** | Purchase orders, and versioned rate cards with labour, equipment and material rates |
| **Upload and Review** | Placeholder — Phase 2 |
| **Invoices** | Placeholder — Phase 3 |
| **Settings and Backup** | Company details, GST rate, invoice numbering, model name, storage diagnostics |

### Two rules worth knowing

**Rates come from the rate card, never from the ticket.** A rate printed on a
field ticket is extracted only so it can be compared against what was agreed. It
never becomes the billed rate. A rate card with no overtime rate stays blank
rather than falling back to the regular rate, because that would quietly
under-bill overtime.

**Rate card periods may not overlap.** Two cards covering the same day would
make the billable rate for that day ambiguous, so the overlap is refused when you
save it rather than resolved by guesswork at invoice time.

---

## Your data

Everything lives under `data/`, which is excluded from git:

```
data/
├── app.db            SQLite database (WAL mode, foreign keys enforced)
├── originals/        uploaded documents, byte-for-byte, never modified
├── rendered_pages/   page images rendered from PDFs
├── generated/        invoice PDFs, backup PDFs, JSON exports
└── backups/          timestamped ZIP backups
```

Until the backup screen is built in Phase 4, back up by **closing the
application and copying the whole `data/` folder.**

### Money is never a float

Currency, rates and quantities are `Decimal` throughout and are stored in the
database as exact integers in minor units. Rounding happens in one place, with
one policy (`ROUND_HALF_UP` to two decimal places). `src/money.py` refuses to
convert a `float`, and refuses to store a value carrying more precision than its
column, rather than rounding it silently.

---

## Privacy

- The interface binds to `127.0.0.1` only (`.streamlit/config.toml`) and has no
  login. **Do not expose it to the office network or the internet.** If it is
  ever shared beyond one laptop, authentication and encryption become mandatory
  first.
- Streamlit's usage statistics are disabled.
- No cloud SDK, analytics or crash reporting is installed.
- The audit log records which fields changed, never document contents.
- Uploaded originals are never overwritten; filenames are sanitised and path
  traversal is refused.

---

## Running the tests

```bash
python -m pytest -q
```

The suite covers decimal exactness and rounding boundaries, foreign key and
uniqueness enforcement, rate card overlap and effective-date resolution, and
first-launch bootstrapping. Tests use a temporary database and never touch
`data/`.

---

## Not in this application, on purpose

Multiple organisations or users, login, cloud storage or OCR, Docker,
PostgreSQL, Redis, background workers, Fieldglass/SAP/Ariba/QuickBooks/Sage
integrations, automatic invoice emailing, change-order detection, mobile apps,
handwriting authentication, and a general-purpose chatbot.
