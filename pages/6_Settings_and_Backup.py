"""Company settings, invoice numbering, and local diagnostics."""

from __future__ import annotations

import streamlit as st

from src import config, repository as repo
from src.database import get_session, pragma
from src.ui import percent_input, phase_placeholder, start_page

start_page("Settings and Backup", icon="⚙️")

with get_session() as session:
    settings = repo.get_company_settings(session)

company_tab, billing_tab, system_tab = st.tabs(["Company", "Billing", "System"])

with company_tab:
    st.caption("These details appear on every invoice you generate.")
    with st.form("company"):
        legal_name = st.text_input("Legal name", value=settings.legal_name)
        address = st.text_area("Address", value=settings.address)
        phone = st.text_input("Phone", value=settings.phone)
        email = st.text_input("Email", value=settings.email)
        gst_number = st.text_input("GST number", value=settings.gst_number)
        if st.form_submit_button("Save company details"):
            with get_session() as session:
                repo.save_company_settings(
                    session,
                    legal_name=legal_name.strip(),
                    address=address.strip(),
                    phone=phone.strip(),
                    email=email.strip(),
                    gst_number=gst_number.strip(),
                )
            st.success("Saved.")
            st.rerun()

with billing_tab:
    with st.form("billing"):
        payment_terms = st.text_input("Payment terms", value=settings.payment_terms)
        invoice_prefix = st.text_input("Invoice number prefix", value=settings.invoice_prefix)
        next_number = st.number_input(
            "Next invoice number",
            min_value=1,
            step=1,
            value=int(settings.next_invoice_number),
            help="Used when the first invoice is generated in Phase 3.",
        )
        gst_rate = percent_input(
            "GST rate %",
            settings.default_gst_rate,
            key="gst",
            help="Alberta is 5%. There is no provincial sales tax to add.",
        )
        if st.form_submit_button("Save billing settings"):
            if gst_rate is None or gst_rate < 0:
                st.error("Enter a GST rate of zero or more.")
            else:
                with get_session() as session:
                    repo.save_company_settings(
                        session,
                        payment_terms=payment_terms.strip(),
                        invoice_prefix=invoice_prefix.strip(),
                        next_invoice_number=int(next_number),
                        default_gst_rate=gst_rate,
                    )
                st.success("Saved.")
                st.rerun()

with system_tab:
    st.subheader("Local model")
    with st.form("model"):
        model_name = st.text_input(
            "Ollama model",
            value=settings.ollama_model,
            help=(
                "Must be a tag that accepts images, since field tickets are "
                "often photographed. Used from Phase 2."
            ),
        )
        if st.form_submit_button("Save model name"):
            with get_session() as session:
                repo.save_company_settings(session, ollama_model=model_name.strip())
            st.success("Saved.")
            st.rerun()

    st.caption(
        f"Extraction will call `{config.OLLAMA_BASE_URL}` — loopback only. A "
        "health check and a vision self-test are added in Phase 2, so an "
        "unavailable or text-only model reports a clear message instead of "
        "failing mid-extraction."
    )

    st.divider()
    st.subheader("Storage")
    st.write(f"Database: `{config.database_path()}`")
    st.write(f"Data directory: `{config.data_dir()}`")

    checks = {
        "Journal mode (expect wal)": pragma("journal_mode"),
        "Foreign keys (expect 1)": pragma("foreign_keys"),
    }
    for label, value in checks.items():
        st.write(f"- {label}: `{value}`")

    st.divider()
    st.subheader("Backup and restore")
    phase_placeholder(
        4,
        "Create a timestamped ZIP of the database, original documents and "
        "generated files, and restore one after an explicit confirmation that "
        "takes a safety backup first.",
    )
    st.caption(
        f"Until then, back up by copying the whole `{config.data_dir().name}` "
        "folder while the application is closed."
    )
