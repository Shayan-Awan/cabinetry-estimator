"""Field Ticket-to-Invoice — application entry point.

Run with:

    streamlit run app.py

The server binds to 127.0.0.1 (see .streamlit/config.toml). On first launch the
data directories and SQLite database are created automatically; there is no
migration step for the user to run.
"""

from __future__ import annotations

import streamlit as st

from src import config, repository as repo
from src.database import get_session
from src.ui import start_page

start_page("Field Ticket-to-Invoice", icon="🧾")

st.write(
    "A local tool for turning signed field tickets into a draft invoice and an "
    "ordered backup package. Everything stays on this laptop."
)

with get_session() as session:
    settings = repo.get_company_settings(session)
    customers = repo.list_customers(session)
    projects = repo.list_projects(session)
    rate_cards = [
        card for project in projects for card in repo.list_rate_cards(session, project.id)
    ]

st.subheader("Getting started")

steps = [
    (
        repo.company_settings_complete(settings),
        "Enter your company details",
        "Settings and Backup",
    ),
    (bool(customers), "Add a customer", "Customers and Projects"),
    (bool(projects), "Add a project", "Customers and Projects"),
    (bool(rate_cards), "Enter a purchase order and rate card", "Rates and POs"),
]

for done, label, where in steps:
    mark = "✅" if done else "⬜"
    st.write(f"{mark} {label} — *{where}*")

if all(done for done, _, _ in steps):
    st.success("Setup is complete. Ticket upload and extraction arrive in Phase 2.")

st.divider()
st.caption(
    f"Data is stored under `{config.data_dir()}`. Back it up before relying on it "
    "for billing. This build covers Phase 1 (foundation) only."
)
