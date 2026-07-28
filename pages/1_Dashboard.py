"""Dashboard — what needs attention.

Phase 1 can only report on setup data. The ticket and invoice panels are added
by the phases that create those records.
"""

from __future__ import annotations

import streamlit as st

from src import audit, repository as repo
from src.database import get_session
from src.ui import start_page

start_page("Dashboard", icon="📊")

with get_session() as session:
    customers = repo.list_customers(session)
    projects = repo.list_projects(session)
    active_projects = [p for p in projects if p.is_active]
    settings = repo.get_company_settings(session)
    events = audit.recent(session, limit=15)
    cards_by_project = {p.id: repo.list_rate_cards(session, p.id) for p in projects}

columns = st.columns(4)
columns[0].metric("Customers", len(customers))
columns[1].metric("Projects", len(projects))
columns[2].metric("Active projects", len(active_projects))
columns[3].metric("Rate cards", sum(len(c) for c in cards_by_project.values()))

if not repo.company_settings_complete(settings):
    st.warning(
        "Company details are incomplete. Invoices cannot be generated without a "
        "legal name and address — fill them in on **Settings and Backup**."
    )

uncovered = [p for p in projects if not cards_by_project.get(p.id)]
if uncovered:
    st.info(
        "Projects with no rate card yet: "
        + ", ".join(sorted(p.name for p in uncovered))
        + ". Tickets on these projects cannot be priced."
    )

st.subheader("Awaiting review")
st.caption("Field tickets appear here once uploads and extraction exist (Phase 2).")

st.subheader("Invoices")
st.caption("Draft, submitted and unpaid invoices appear here in Phase 3.")

st.divider()
st.subheader("Recent activity")
if events:
    st.dataframe(
        [
            {
                "When": event.occurred_at.strftime("%Y-%m-%d %H:%M"),
                "Event": event.event_type,
                "Details": event.summary,
            }
            for event in events
        ],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.caption("Nothing recorded yet.")
