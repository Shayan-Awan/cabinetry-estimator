"""Customers and the projects that belong to them."""

from __future__ import annotations

import streamlit as st

from src import repository as repo
from src.database import get_session
from src.ui import start_page

start_page("Customers and Projects", icon="🏗️")

customers_tab, projects_tab = st.tabs(["Customers", "Projects"])

with customers_tab:
    with get_session() as session:
        customers = repo.list_customers(session)

    if customers:
        st.dataframe(
            [
                {
                    "Customer": c.legal_name,
                    "AP email": c.ap_email,
                    "Billing address": c.billing_address,
                }
                for c in customers
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("No customers yet.")

    st.subheader("Add a customer")
    with st.form("add_customer", clear_on_submit=True):
        legal_name = st.text_input("Legal name", help="As it should appear on the invoice.")
        billing_address = st.text_area("Billing address")
        ap_email = st.text_input("Accounts payable email")
        notes = st.text_area("Notes")
        if st.form_submit_button("Save customer"):
            if not legal_name.strip():
                st.error("A legal name is required.")
            else:
                with get_session() as session:
                    repo.create_customer(
                        session,
                        legal_name=legal_name.strip(),
                        billing_address=billing_address.strip(),
                        ap_email=ap_email.strip(),
                        notes=notes.strip(),
                    )
                st.success(f"Saved {legal_name.strip()}.")
                st.rerun()

    if customers:
        st.subheader("Edit a customer")
        target = st.selectbox(
            "Customer",
            options=[c.id for c in customers],
            format_func=lambda cid: next(c.legal_name for c in customers if c.id == cid),
            key="edit_customer_pick",
        )
        current = next(c for c in customers if c.id == target)
        with st.form("edit_customer"):
            name = st.text_input("Legal name", value=current.legal_name)
            address = st.text_area("Billing address", value=current.billing_address)
            email = st.text_input("Accounts payable email", value=current.ap_email)
            note = st.text_area("Notes", value=current.notes)
            if st.form_submit_button("Update customer"):
                with get_session() as session:
                    repo.update_customer(
                        session,
                        target,
                        legal_name=name.strip(),
                        billing_address=address.strip(),
                        ap_email=email.strip(),
                        notes=note.strip(),
                    )
                st.success("Updated.")
                st.rerun()

with projects_tab:
    with get_session() as session:
        customers = repo.list_customers(session)
        projects = repo.list_projects(session)

    if not customers:
        st.warning("Add a customer before creating a project.")
    else:
        names = {c.id: c.legal_name for c in customers}

        if projects:
            st.dataframe(
                [
                    {
                        "Customer": names.get(p.customer_id, "Unknown"),
                        "Project": p.name,
                        "Client project #": p.client_project_number,
                        "Location": p.location,
                        "Active": "Yes" if p.is_active else "No",
                    }
                    for p in projects
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("No projects yet.")

        st.subheader("Add a project")
        with st.form("add_project", clear_on_submit=True):
            customer_id = st.selectbox(
                "Customer",
                options=[c.id for c in customers],
                format_func=lambda cid: names[cid],
            )
            name = st.text_input("Project name")
            client_number = st.text_input("Client project number")
            location = st.text_input("Location")
            if st.form_submit_button("Save project"):
                if not name.strip():
                    st.error("A project name is required.")
                else:
                    with get_session() as session:
                        repo.create_project(
                            session,
                            customer_id=customer_id,
                            name=name.strip(),
                            client_project_number=client_number.strip(),
                            location=location.strip(),
                        )
                    st.success(f"Saved {name.strip()}.")
                    st.rerun()

        if projects:
            st.subheader("Edit a project")
            target = st.selectbox(
                "Project",
                options=[p.id for p in projects],
                format_func=lambda pid: next(p.name for p in projects if p.id == pid),
                key="edit_project_pick",
            )
            current = next(p for p in projects if p.id == target)
            with st.form("edit_project"):
                name = st.text_input("Project name", value=current.name)
                client_number = st.text_input(
                    "Client project number", value=current.client_project_number
                )
                location = st.text_input("Location", value=current.location)
                is_active = st.checkbox("Active", value=current.is_active)
                if st.form_submit_button("Update project"):
                    with get_session() as session:
                        repo.update_project(
                            session,
                            target,
                            name=name.strip(),
                            client_project_number=client_number.strip(),
                            location=location.strip(),
                            is_active=is_active,
                        )
                    st.success("Updated.")
                    st.rerun()
