"""The complete database schema.

All tables are defined here, including those that stay unused until later
phases. There is no migration tool in this application -- ``create_all`` simply
creates whatever is missing on startup -- so defining the full shape up front
avoids retrofitting columns onto tables that already hold real billing data.

Phase 1 populates: company_settings, customers, projects, purchase_orders,
rate_cards, rate_lines and audit_events. The rest are created empty.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlmodel import Field, SQLModel

from src.money import Money, Percent, Quantity, Rate


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Enumerations -----------------------------------------------------------


class LineCategory(str, Enum):
    LABOUR = "labour"
    EQUIPMENT = "equipment"
    MATERIAL = "material"
    OTHER = "other"


class TimeType(str, Enum):
    REGULAR = "regular"
    OVERTIME = "overtime"
    DOUBLE_TIME = "double_time"


class DocumentType(str, Enum):
    FIELD_TICKET = "field_ticket"
    DAILY_REPORT = "daily_report"
    RECEIPT = "receipt"
    OTHER = "other"
    UNKNOWN = "unknown"


class ExtractionStatus(str, Enum):
    PENDING = "pending"
    RENDERED = "rendered"
    EXTRACTED = "extracted"
    FAILED = "failed"
    MANUAL = "manual"


class ReviewStatus(str, Enum):
    NEEDS_REVIEW = "needs_review"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    PAID = "paid"
    DISPUTED = "disputed"


# --- Phase 1 tables ---------------------------------------------------------


class CompanySettings(SQLModel, table=True):
    """The contractor's own details. Exactly one row ever exists."""

    __tablename__ = "company_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_company_settings_singleton"),
    )

    id: int | None = Field(default=1, primary_key=True)
    legal_name: str = ""
    address: str = ""
    phone: str = ""
    email: str = ""
    gst_number: str = ""
    payment_terms: str = ""
    invoice_prefix: str = ""
    next_invoice_number: int = 1001
    default_gst_rate: Decimal = Field(default=Decimal("0.05"), sa_type=Percent)
    # Which local model to use for extraction. Stored rather than hard-coded so
    # a different tag can be selected without a code change.
    ollama_model: str = "qwen3.5:4b"
    updated_at: datetime = Field(default_factory=utcnow)


class Customer(SQLModel, table=True):
    __tablename__ = "customers"

    id: int | None = Field(default=None, primary_key=True)
    legal_name: str = Field(index=True)
    billing_address: str = ""
    ap_email: str = ""
    notes: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class Project(SQLModel, table=True):
    __tablename__ = "projects"

    id: int | None = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customers.id", index=True)
    name: str
    client_project_number: str = ""
    location: str = ""
    is_active: bool = True
    created_at: datetime = Field(default_factory=utcnow)


class PurchaseOrder(SQLModel, table=True):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        UniqueConstraint("project_id", "po_number", name="uq_po_project_number"),
    )

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id", index=True)
    po_number: str = Field(index=True)
    # What the client authorised in total.
    original_value: Decimal = Field(default=Decimal("0.00"), sa_type=Money)
    # What has been invoiced against it so far. Maintained by Phase 3.
    committed_value: Decimal = Field(default=Decimal("0.00"), sa_type=Money)
    currency: str = "CAD"
    start_date: date | None = None
    end_date: date | None = None
    created_at: datetime = Field(default_factory=utcnow)


class RateCard(SQLModel, table=True):
    """A versioned set of agreed rates for a project.

    ``effective_to`` of ``None`` means open-ended. Two cards for one project may
    never cover the same day -- see ``repository.assert_no_overlap``.
    """

    __tablename__ = "rate_cards"

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id", index=True)
    name: str
    effective_from: date
    effective_to: date | None = None
    material_markup_pct: Decimal = Field(default=Decimal("0.0000"), sa_type=Percent)
    created_at: datetime = Field(default_factory=utcnow)


class RateLine(SQLModel, table=True):
    __tablename__ = "rate_lines"
    __table_args__ = (
        UniqueConstraint("rate_card_id", "category", "code", name="uq_rate_line_code"),
    )

    id: int | None = Field(default=None, primary_key=True)
    rate_card_id: int = Field(foreign_key="rate_cards.id", index=True)
    category: LineCategory
    code: str
    description: str = ""
    regular_rate: Decimal = Field(default=Decimal("0.0000"), sa_type=Rate)
    overtime_rate: Decimal | None = Field(default=None, sa_type=Rate, nullable=True)
    double_time_rate: Decimal | None = Field(default=None, sa_type=Rate, nullable=True)
    unit: str = "hour"


# --- Phase 2 tables (created empty until uploads exist) ---------------------


class Document(SQLModel, table=True):
    __tablename__ = "documents"

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id", index=True)
    original_filename: str
    stored_filename: str
    document_type: DocumentType = DocumentType.UNKNOWN
    # SHA-256 of the original bytes; used to reject duplicate uploads.
    checksum: str = Field(index=True)
    uploaded_at: datetime = Field(default_factory=utcnow)
    page_count: int = 0
    extraction_status: ExtractionStatus = ExtractionStatus.PENDING


class FieldTicket(SQLModel, table=True):
    __tablename__ = "field_tickets"

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id", index=True)
    document_id: int | None = Field(default=None, foreign_key="documents.id")
    ticket_number: str | None = Field(default=None, index=True)
    work_date: date | None = None
    po_number: str | None = None
    location: str = ""
    work_description: str = ""
    client_signature_present: bool = False
    contractor_signature_present: bool = False
    extraction_confidence: Decimal | None = Field(
        default=None, sa_type=Percent, nullable=True
    )
    review_status: ReviewStatus = ReviewStatus.NEEDS_REVIEW
    invoice_id: int | None = Field(default=None, foreign_key="invoices.id", index=True)
    created_at: datetime = Field(default_factory=utcnow)


class TicketLine(SQLModel, table=True):
    __tablename__ = "ticket_lines"

    id: int | None = Field(default=None, primary_key=True)
    field_ticket_id: int = Field(foreign_key="field_tickets.id", index=True)
    category: LineCategory
    description: str = ""
    resource_name: str = ""  # worker or equipment identifier
    quantity: Decimal = Field(default=Decimal("0.000"), sa_type=Quantity)
    time_type: TimeType = TimeType.REGULAR
    unit: str = "hour"
    # What the ticket appeared to say, kept only for comparison.
    extracted_rate: Decimal | None = Field(default=None, sa_type=Rate, nullable=True)
    # What will actually be billed: always resolved from the rate card.
    approved_rate: Decimal | None = Field(default=None, sa_type=Rate, nullable=True)
    calculated_amount: Decimal | None = Field(default=None, sa_type=Money, nullable=True)
    rate_line_id: int | None = Field(default=None, foreign_key="rate_lines.id")
    source_page: int | None = None
    source_text: str = ""
    extraction_confidence: Decimal | None = Field(
        default=None, sa_type=Percent, nullable=True
    )


class ValidationResult(SQLModel, table=True):
    __tablename__ = "validation_results"

    id: int | None = Field(default=None, primary_key=True)
    field_ticket_id: int = Field(foreign_key="field_tickets.id", index=True)
    rule_code: str
    severity: Severity
    message: str
    resolved: bool = False
    resolution_note: str = ""
    created_at: datetime = Field(default_factory=utcnow)


# --- Phase 3 tables ---------------------------------------------------------


class Invoice(SQLModel, table=True):
    __tablename__ = "invoices"

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id", index=True)
    invoice_number: str = Field(unique=True, index=True)
    period_start: date | None = None
    period_end: date | None = None
    subtotal: Decimal = Field(default=Decimal("0.00"), sa_type=Money)
    gst_amount: Decimal = Field(default=Decimal("0.00"), sa_type=Money)
    total: Decimal = Field(default=Decimal("0.00"), sa_type=Money)
    gst_rate: Decimal = Field(default=Decimal("0.05"), sa_type=Percent)
    status: InvoiceStatus = InvoiceStatus.DRAFT
    invoice_pdf_path: str = ""
    backup_pdf_path: str = ""
    created_at: datetime = Field(default_factory=utcnow)
    approved_at: datetime | None = None


class InvoiceLine(SQLModel, table=True):
    """One rolled-up billing line on the invoice.

    Ticket lines are aggregated by (category, code, time_type) for the invoice
    period; the per-ticket detail lives in the merged backup PDF.
    """

    __tablename__ = "invoice_lines"

    id: int | None = Field(default=None, primary_key=True)
    invoice_id: int = Field(foreign_key="invoices.id", index=True)
    category: LineCategory
    code: str = ""
    description: str = ""
    time_type: TimeType = TimeType.REGULAR
    unit: str = "hour"
    quantity: Decimal = Field(default=Decimal("0.000"), sa_type=Quantity)
    rate: Decimal = Field(default=Decimal("0.0000"), sa_type=Rate)
    amount: Decimal = Field(default=Decimal("0.00"), sa_type=Money)
    sort_order: int = 0


# --- Audit ------------------------------------------------------------------


class AuditEvent(SQLModel, table=True):
    """Append-only history. Rows are written once and never changed."""

    __tablename__ = "audit_events"

    id: int | None = Field(default=None, primary_key=True)
    occurred_at: datetime = Field(default_factory=utcnow, index=True)
    event_type: str
    record_type: str
    record_id: int | None = None
    summary: str = ""
    old_value_json: str | None = None
    new_value_json: str | None = None
