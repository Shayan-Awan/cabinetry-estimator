"""Data access for the Phase 1 entities, plus rate-card date resolution.

Queries live here rather than in the Streamlit pages so they can be tested
without running the interface.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlmodel import Session, select

from src import audit, config
from src.models import (
    CompanySettings,
    Customer,
    LineCategory,
    Project,
    PurchaseOrder,
    RateCard,
    RateLine,
    TimeType,
)
from src.money import quantize_money


class RateCardOverlapError(ValueError):
    """Two rate cards for one project would cover the same day."""


class InvalidDateRangeError(ValueError):
    """The end of a range falls before its start."""


# --- Company settings -------------------------------------------------------


def get_company_settings(session: Session) -> CompanySettings:
    """Return the singleton settings row, creating it if it is somehow missing."""
    settings = session.get(CompanySettings, 1)
    if settings is None:
        settings = CompanySettings(
            id=1,
            payment_terms=config.DEFAULT_PAYMENT_TERMS,
            invoice_prefix=config.DEFAULT_INVOICE_PREFIX,
            next_invoice_number=config.DEFAULT_STARTING_INVOICE_NUMBER,
            default_gst_rate=config.DEFAULT_GST_RATE,
            ollama_model=config.DEFAULT_OLLAMA_MODEL,
        )
        session.add(settings)
        session.flush()
    return settings


def save_company_settings(session: Session, **fields: object) -> CompanySettings:
    settings = get_company_settings(session)
    before = {key: getattr(settings, key) for key in fields}
    for key, value in fields.items():
        setattr(settings, key, value)
    session.add(settings)
    audit.record(
        session,
        event_type="settings_updated",
        record_type="company_settings",
        record_id=1,
        summary="Company settings updated",
        old_value=before,
        new_value=fields,
    )
    return settings


def company_settings_complete(settings: CompanySettings) -> bool:
    """Whether enough is filled in to put the company on an invoice."""
    return bool(settings.legal_name.strip() and settings.address.strip())


# --- Customers --------------------------------------------------------------


def list_customers(session: Session) -> list[Customer]:
    return list(session.exec(select(Customer).order_by(Customer.legal_name)))


def get_customer(session: Session, customer_id: int) -> Customer | None:
    return session.get(Customer, customer_id)


def create_customer(session: Session, **fields: object) -> Customer:
    customer = Customer(**fields)
    session.add(customer)
    session.flush()
    audit.record(
        session,
        event_type="customer_created",
        record_type="customer",
        record_id=customer.id,
        summary=f"Customer created: {customer.legal_name}",
        new_value=fields,
    )
    return customer


def update_customer(session: Session, customer_id: int, **fields: object) -> Customer:
    customer = session.get(Customer, customer_id)
    if customer is None:
        raise LookupError(f"No customer with id {customer_id}")
    before = {key: getattr(customer, key) for key in fields}
    for key, value in fields.items():
        setattr(customer, key, value)
    session.add(customer)
    audit.record(
        session,
        event_type="customer_updated",
        record_type="customer",
        record_id=customer_id,
        summary=f"Customer updated: {customer.legal_name}",
        old_value=before,
        new_value=fields,
    )
    return customer


# --- Projects ---------------------------------------------------------------


def list_projects(
    session: Session, customer_id: int | None = None, active_only: bool = False
) -> list[Project]:
    statement = select(Project)
    if customer_id is not None:
        statement = statement.where(Project.customer_id == customer_id)
    if active_only:
        statement = statement.where(Project.is_active == True)  # noqa: E712
    return list(session.exec(statement.order_by(Project.name)))


def get_project(session: Session, project_id: int) -> Project | None:
    return session.get(Project, project_id)


def create_project(session: Session, **fields: object) -> Project:
    project = Project(**fields)
    session.add(project)
    session.flush()
    audit.record(
        session,
        event_type="project_created",
        record_type="project",
        record_id=project.id,
        summary=f"Project created: {project.name}",
        new_value=fields,
    )
    return project


def update_project(session: Session, project_id: int, **fields: object) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise LookupError(f"No project with id {project_id}")
    before = {key: getattr(project, key) for key in fields}
    for key, value in fields.items():
        setattr(project, key, value)
    session.add(project)
    audit.record(
        session,
        event_type="project_updated",
        record_type="project",
        record_id=project_id,
        summary=f"Project updated: {project.name}",
        old_value=before,
        new_value=fields,
    )
    return project


# --- Purchase orders --------------------------------------------------------


def list_purchase_orders(session: Session, project_id: int) -> list[PurchaseOrder]:
    statement = (
        select(PurchaseOrder)
        .where(PurchaseOrder.project_id == project_id)
        .order_by(PurchaseOrder.po_number)
    )
    return list(session.exec(statement))


def find_purchase_order(
    session: Session, project_id: int, po_number: str
) -> PurchaseOrder | None:
    statement = select(PurchaseOrder).where(
        PurchaseOrder.project_id == project_id,
        PurchaseOrder.po_number == po_number,
    )
    return session.exec(statement).first()


def create_purchase_order(session: Session, **fields: object) -> PurchaseOrder:
    start = fields.get("start_date")
    end = fields.get("end_date")
    if start and end and end < start:
        raise InvalidDateRangeError("The PO end date falls before its start date.")
    po = PurchaseOrder(**fields)
    session.add(po)
    session.flush()
    audit.record(
        session,
        event_type="po_created",
        record_type="purchase_order",
        record_id=po.id,
        summary=f"PO created: {po.po_number}",
        new_value=fields,
    )
    return po


def po_remaining_value(po: PurchaseOrder) -> Decimal:
    """Authorised value not yet invoiced. Phase 3 blocks invoices that exceed it."""
    return quantize_money(po.original_value - po.committed_value)


# --- Rate cards -------------------------------------------------------------


def _ranges_overlap(
    a_from: date, a_to: date | None, b_from: date, b_to: date | None
) -> bool:
    """Inclusive overlap test where ``None`` for an end date means open-ended."""
    if a_to is not None and b_from > a_to:
        return False
    if b_to is not None and a_from > b_to:
        return False
    return True


def assert_no_overlap(
    session: Session,
    project_id: int,
    effective_from: date,
    effective_to: date | None,
    exclude_id: int | None = None,
) -> None:
    """Refuse a rate card whose effective period collides with an existing one.

    Overlapping cards would make the billable rate for a given work date
    ambiguous, so this is rejected at write time rather than resolved by
    guesswork at invoice time.
    """
    if effective_to is not None and effective_to < effective_from:
        raise InvalidDateRangeError(
            "The rate card's end date falls before its start date."
        )

    for existing in list_rate_cards(session, project_id):
        if exclude_id is not None and existing.id == exclude_id:
            continue
        if _ranges_overlap(
            effective_from, effective_to, existing.effective_from, existing.effective_to
        ):
            end = existing.effective_to.isoformat() if existing.effective_to else "open"
            raise RateCardOverlapError(
                f"Rate card {existing.name!r} already covers "
                f"{existing.effective_from.isoformat()} to {end}."
            )


def list_rate_cards(session: Session, project_id: int) -> list[RateCard]:
    statement = (
        select(RateCard)
        .where(RateCard.project_id == project_id)
        .order_by(RateCard.effective_from)
    )
    return list(session.exec(statement))


def create_rate_card(
    session: Session,
    *,
    project_id: int,
    name: str,
    effective_from: date,
    effective_to: date | None = None,
    material_markup_pct: Decimal = Decimal("0.0000"),
) -> RateCard:
    assert_no_overlap(session, project_id, effective_from, effective_to)
    card = RateCard(
        project_id=project_id,
        name=name,
        effective_from=effective_from,
        effective_to=effective_to,
        material_markup_pct=material_markup_pct,
    )
    session.add(card)
    session.flush()
    audit.record(
        session,
        event_type="rate_card_created",
        record_type="rate_card",
        record_id=card.id,
        summary=f"Rate card created: {name}",
        new_value={
            "effective_from": effective_from,
            "effective_to": effective_to,
            "material_markup_pct": material_markup_pct,
        },
    )
    return card


def find_effective_rate_card(
    session: Session, project_id: int, work_date: date
) -> RateCard | None:
    """The rate card covering ``work_date``, or ``None`` if the date is uncovered.

    Overlaps are prevented on write, so at most one card can match.
    """
    for card in list_rate_cards(session, project_id):
        if card.effective_from <= work_date and (
            card.effective_to is None or work_date <= card.effective_to
        ):
            return card
    return None


# --- Rate lines -------------------------------------------------------------


def list_rate_lines(session: Session, rate_card_id: int) -> list[RateLine]:
    statement = (
        select(RateLine)
        .where(RateLine.rate_card_id == rate_card_id)
        .order_by(RateLine.category, RateLine.code)
    )
    return list(session.exec(statement))


def add_rate_line(session: Session, **fields: object) -> RateLine:
    line = RateLine(**fields)
    session.add(line)
    session.flush()
    audit.record(
        session,
        event_type="rate_line_added",
        record_type="rate_line",
        record_id=line.id,
        summary=f"Rate line added: {line.category.value} {line.code}",
        new_value=fields,
    )
    return line


def find_rate_line(
    session: Session,
    project_id: int,
    work_date: date,
    category: LineCategory,
    code: str,
) -> RateLine | None:
    """Resolve a billable rate line from the rate card effective on ``work_date``.

    Returns ``None`` when no card covers the date or the card has no matching
    code. Phase 3 turns that into a blocking validation rather than a guess.
    """
    card = find_effective_rate_card(session, project_id, work_date)
    if card is None:
        return None
    statement = select(RateLine).where(
        RateLine.rate_card_id == card.id,
        RateLine.category == category,
        RateLine.code == code,
    )
    return session.exec(statement).first()


def rate_for_time_type(line: RateLine, time_type: TimeType) -> Decimal | None:
    """The agreed rate for a time type, or ``None`` if the card does not set one.

    A missing overtime or double-time rate is never silently replaced with the
    regular rate -- that would under-bill without anyone noticing.
    """
    if time_type is TimeType.REGULAR:
        return line.regular_rate
    if time_type is TimeType.OVERTIME:
        return line.overtime_rate
    if time_type is TimeType.DOUBLE_TIME:
        return line.double_time_rate
    return None
