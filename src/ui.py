"""Shared Streamlit helpers.

Keeps the per-page boilerplate (bootstrap, the review notice, decimal-safe
inputs) in one place.
"""

from __future__ import annotations

from decimal import Decimal

import streamlit as st

from src import config
from src.database import init_db
from src.money import MoneyError, parse_decimal, quantize


def start_page(title: str, icon: str = "📋") -> None:
    """Configure the page, ensure the database exists, and show the notice."""
    st.set_page_config(page_title=f"{title} — {config.APP_NAME}", page_icon=icon, layout="wide")
    init_db()
    st.title(title)
    st.caption(f"⚠️ {config.REVIEW_NOTICE}")


def decimal_input(
    label: str,
    value: Decimal | None = None,
    *,
    scale: int = 2,
    key: str | None = None,
    help: str | None = None,
    placeholder: str = "0.00",
) -> Decimal | None:
    """A text field that yields an exact ``Decimal``.

    ``st.number_input`` returns a ``float``, which must never reach a monetary
    value, so money and rates are entered as text and parsed here.
    """
    raw = st.text_input(
        label,
        value="" if value is None else str(value),
        key=key,
        help=help,
        placeholder=placeholder,
    )
    if not raw.strip():
        return None
    try:
        return quantize(parse_decimal(raw), scale)
    except MoneyError as exc:
        st.error(str(exc))
        return None


def percent_input(
    label: str, value: Decimal | None = None, *, key: str | None = None, help: str | None = None
) -> Decimal | None:
    """Enter a percentage (``5`` means 5%); returns the fraction (``0.05``)."""
    shown = None if value is None else value * 100
    raw = st.text_input(
        label,
        value="" if shown is None else f"{shown.normalize():f}",
        key=key,
        help=help,
        placeholder="5",
    )
    if not raw.strip():
        return None
    try:
        return quantize(parse_decimal(raw) / 100, 4)
    except MoneyError as exc:
        st.error(str(exc))
        return None


def phase_placeholder(phase: int, summary: str) -> None:
    """Marks a screen that is intentionally not built yet."""
    st.info(
        f"**Arrives in Phase {phase}.**\n\n{summary}\n\n"
        "The foundation this screen depends on is in place; the screen itself "
        "is built in a later, separately approved phase."
    )


def require_project(session) -> int | None:
    """Project picker shared by the ticket-oriented screens."""
    from src import repository as repo

    projects = repo.list_projects(session)
    if not projects:
        st.warning("Create a customer and a project first, on **Customers and Projects**.")
        return None
    customers = {c.id: c.legal_name for c in repo.list_customers(session)}
    chosen = st.selectbox(
        "Project",
        options=[p.id for p in projects],
        format_func=lambda pid: next(
            f"{customers.get(p.customer_id, 'Unknown')} — {p.name}"
            for p in projects
            if p.id == pid
        ),
    )
    return chosen
