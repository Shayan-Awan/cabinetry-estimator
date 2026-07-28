"""Purchase orders and versioned rate cards.

Rates entered here are the only rates that can be billed. A rate printed on a
field ticket is extracted for comparison in later phases, but never replaces
what was agreed here.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import streamlit as st

from src import repository as repo
from src.database import get_session
from src.models import LineCategory
from src.money import format_money
from src.repository import InvalidDateRangeError, RateCardOverlapError
from src.ui import decimal_input, percent_input, require_project, start_page

start_page("Rates and Purchase Orders", icon="💲")

with get_session() as session:
    project_id = require_project(session)

if project_id is None:
    st.stop()

po_tab, rate_tab = st.tabs(["Purchase orders", "Rate cards"])

with po_tab:
    with get_session() as session:
        orders = repo.list_purchase_orders(session, project_id)
        rows = [
            {
                "PO number": po.po_number,
                "Original value": format_money(po.original_value, po.currency),
                "Invoiced to date": format_money(po.committed_value, po.currency),
                "Remaining": format_money(repo.po_remaining_value(po), po.currency),
                "Start": po.start_date.isoformat() if po.start_date else "—",
                "End": po.end_date.isoformat() if po.end_date else "—",
            }
            for po in orders
        ]

    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.caption("No purchase orders for this project yet.")

    st.subheader("Add a purchase order")
    with st.form("add_po", clear_on_submit=True):
        po_number = st.text_input("PO number")
        original_value = decimal_input(
            "Original value", scale=2, key="po_value", placeholder="250000.00"
        )
        currency = st.text_input("Currency", value="CAD", max_chars=3)
        use_dates = st.checkbox("This PO has start and end dates", value=True)
        start = st.date_input("Start date", value=date.today()) if use_dates else None
        end = st.date_input("End date", value=date.today()) if use_dates else None
        if st.form_submit_button("Save purchase order"):
            if not po_number.strip():
                st.error("A PO number is required.")
            elif original_value is None:
                st.error("An original value is required.")
            elif original_value < 0:
                st.error("The PO value cannot be negative.")
            else:
                try:
                    with get_session() as session:
                        repo.create_purchase_order(
                            session,
                            project_id=project_id,
                            po_number=po_number.strip(),
                            original_value=original_value,
                            currency=currency.strip().upper() or "CAD",
                            start_date=start,
                            end_date=end,
                        )
                    st.success(f"Saved PO {po_number.strip()}.")
                    st.rerun()
                except InvalidDateRangeError as exc:
                    st.error(str(exc))
                except Exception as exc:  # unique constraint on (project, po_number)
                    st.error(f"Could not save that PO: {exc}")

with rate_tab:
    with get_session() as session:
        cards = repo.list_rate_cards(session, project_id)
        lines_by_card = {card.id: repo.list_rate_lines(session, card.id) for card in cards}

    st.subheader("Rate cards")
    if cards:
        for card in cards:
            end = card.effective_to.isoformat() if card.effective_to else "open-ended"
            markup = card.material_markup_pct * 100
            with st.expander(
                f"{card.name} — {card.effective_from.isoformat()} to {end} "
                f"({len(lines_by_card[card.id])} rates)"
            ):
                st.caption(f"Material markup: {markup.normalize():f}%")
                lines = lines_by_card[card.id]
                if lines:
                    st.dataframe(
                        [
                            {
                                "Category": line.category.value,
                                "Code": line.code,
                                "Description": line.description,
                                "Unit": line.unit,
                                "Regular": f"{line.regular_rate:,.4f}",
                                "Overtime": (
                                    f"{line.overtime_rate:,.4f}"
                                    if line.overtime_rate is not None
                                    else "not set"
                                ),
                                "Double time": (
                                    f"{line.double_time_rate:,.4f}"
                                    if line.double_time_rate is not None
                                    else "not set"
                                ),
                            }
                            for line in lines
                        ],
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.caption("No rates on this card yet.")
    else:
        st.caption("No rate cards for this project yet.")

    st.subheader("Add a rate card")
    st.caption(
        "Effective periods may not overlap: two cards covering the same day "
        "would make the billable rate for that day ambiguous."
    )
    with st.form("add_rate_card", clear_on_submit=True):
        name = st.text_input("Name", placeholder="2026 Rates")
        effective_from = st.date_input("Effective from", value=date(date.today().year, 1, 1))
        open_ended = st.checkbox("Open-ended (no end date)", value=True)
        effective_to = None if open_ended else st.date_input("Effective to", value=date.today())
        markup = percent_input(
            "Material markup %", Decimal("0"), key="markup", help="Applied to material costs."
        )
        if st.form_submit_button("Save rate card"):
            if not name.strip():
                st.error("A name is required.")
            else:
                try:
                    with get_session() as session:
                        repo.create_rate_card(
                            session,
                            project_id=project_id,
                            name=name.strip(),
                            effective_from=effective_from,
                            effective_to=None if open_ended else effective_to,
                            material_markup_pct=markup or Decimal("0.0000"),
                        )
                    st.success(f"Saved rate card {name.strip()}.")
                    st.rerun()
                except (RateCardOverlapError, InvalidDateRangeError) as exc:
                    st.error(str(exc))

    if cards:
        st.subheader("Add a rate to a card")
        with st.form("add_rate_line", clear_on_submit=True):
            card_id = st.selectbox(
                "Rate card",
                options=[c.id for c in cards],
                format_func=lambda cid: next(c.name for c in cards if c.id == cid),
            )
            category = st.selectbox(
                "Category",
                options=list(LineCategory),
                format_func=lambda c: c.value.replace("_", " ").title(),
            )
            code = st.text_input("Code", placeholder="JM-WELD")
            description = st.text_input("Description", placeholder="Journeyman Welder")
            unit = st.text_input("Unit", value="hour")
            regular = decimal_input("Regular rate", scale=4, key="rl_reg", placeholder="87.5000")
            overtime = decimal_input(
                "Overtime rate", scale=4, key="rl_ot", placeholder="leave blank if not agreed"
            )
            double_time = decimal_input(
                "Double-time rate", scale=4, key="rl_dt", placeholder="leave blank if not agreed"
            )
            st.caption(
                "A blank overtime or double-time rate stays blank. It is never "
                "filled in from the regular rate, because that would silently "
                "under-bill overtime."
            )
            if st.form_submit_button("Save rate"):
                if not code.strip():
                    st.error("A code is required.")
                elif regular is None:
                    st.error("A regular rate is required.")
                elif regular < 0 or (overtime or 0) < 0 or (double_time or 0) < 0:
                    st.error("Rates cannot be negative.")
                else:
                    try:
                        with get_session() as session:
                            repo.add_rate_line(
                                session,
                                rate_card_id=card_id,
                                category=category,
                                code=code.strip(),
                                description=description.strip(),
                                unit=unit.strip() or "hour",
                                regular_rate=regular,
                                overtime_rate=overtime,
                                double_time_rate=double_time,
                            )
                        st.success(f"Saved rate {code.strip()}.")
                        st.rerun()
                    except Exception as exc:  # unique (card, category, code)
                        st.error(f"Could not save that rate: {exc}")
