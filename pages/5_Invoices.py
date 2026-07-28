"""Invoices — placeholder until Phase 3."""

from __future__ import annotations

import streamlit as st

from src.ui import phase_placeholder, start_page

start_page("Invoices", icon="🧾")

phase_placeholder(
    3,
    "Group approved tickets into an invoice, preview the lines and totals, "
    "approve it, and generate the invoice PDF, the merged backup PDF and a JSON "
    "export.",
)

st.subheader("How invoices will be calculated")
st.write(
    "- Amounts, GST and totals are computed by ordinary Python code using "
    "`Decimal`. The model never supplies a rate or a total.\n"
    "- Rates come from the rate card effective on the ticket's work date.\n"
    "- Invoice lines are **rolled up by rate code and time type** for the "
    "period; the per-ticket detail goes in the merged backup PDF.\n"
    "- Blocking validation issues prevent approval. Warnings can be overridden "
    "only with a written reason.\n"
    "- Nothing is emailed or submitted automatically."
)
