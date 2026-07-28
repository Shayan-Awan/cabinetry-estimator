"""Paths, limits and defaults for the local application.

Everything is relative to the repository root so the application can be copied
to another laptop and run without editing configuration.
"""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

APP_NAME = "Field Ticket-to-Invoice"

# Shown on every page. AI extraction assists data entry; it does not decide
# what gets billed.
REVIEW_NOTICE = "AI extraction must be reviewed by a person."

# --- Locations --------------------------------------------------------------
# FIELD_TICKET_DATA_DIR lets the test suite point at a temporary directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    override = os.environ.get("FIELD_TICKET_DATA_DIR")
    return Path(override).resolve() if override else PROJECT_ROOT / "data"


def database_path() -> Path:
    return data_dir() / "app.db"


def originals_dir() -> Path:
    """Uploaded documents, byte-for-byte as received. Never modified."""
    return data_dir() / "originals"


def rendered_pages_dir() -> Path:
    """Page images rendered from PDFs for visual extraction and review."""
    return data_dir() / "rendered_pages"


def generated_dir() -> Path:
    """Invoice PDFs, backup PDFs and JSON exports produced by the app."""
    return data_dir() / "generated"


def backups_dir() -> Path:
    """Timestamped ZIP backups of the database and documents."""
    return data_dir() / "backups"


def all_data_dirs() -> tuple[Path, ...]:
    return (
        data_dir(),
        originals_dir(),
        rendered_pages_dir(),
        generated_dir(),
        backups_dir(),
    )


# --- Upload limits (enforced from Phase 2) ----------------------------------
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_PAGES_PER_PACKAGE = 10
RENDER_DPI = 150
ALLOWED_EXTENSIONS = frozenset({".pdf", ".jpg", ".jpeg", ".png"})
ALLOWED_MIME_TYPES = frozenset(
    {"application/pdf", "image/jpeg", "image/png"}
)

# --- Local model (used from Phase 2) ----------------------------------------
# Loopback only. The model name is stored in company settings so it can be
# changed without editing code -- see the setup notes in README.md about
# confirming the chosen tag accepts images.
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
DEFAULT_OLLAMA_MODEL = "qwen3.5:4b"
OLLAMA_TIMEOUT_SECONDS = 300

# Extractions below this confidence are surfaced as warnings for review.
LOW_CONFIDENCE_THRESHOLD = Decimal("0.80")

# --- Billing defaults -------------------------------------------------------
# Alberta has no provincial sales tax, so 5% GST is the whole tax picture for a
# Wood Buffalo contractor. Editable in Settings.
DEFAULT_GST_RATE = Decimal("0.05")
DEFAULT_PAYMENT_TERMS = "Net 30"
DEFAULT_INVOICE_PREFIX = "INV-"
DEFAULT_STARTING_INVOICE_NUMBER = 1001
