"""Upload and Review — placeholder until Phase 2."""

from __future__ import annotations

import streamlit as st

from src import config
from src.ui import phase_placeholder, start_page

start_page("Upload and Review", icon="📤")

phase_placeholder(
    2,
    "Upload field tickets and supporting documents as PDF, JPG or PNG; the "
    "original is preserved and checksummed, pages are rendered for viewing, and "
    "a local model extracts billing fields for you to check side by side with "
    "the document.",
)

st.subheader("Planned limits")
st.write(
    f"- {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB per file\n"
    f"- {config.MAX_PAGES_PER_PACKAGE} pages per ticket package\n"
    f"- {', '.join(sorted(config.ALLOWED_EXTENSIONS))} only\n"
    f"- pages rendered at {config.RENDER_DPI} DPI\n"
    "- one extraction at a time"
)

st.subheader("Before Phase 2 begins")
st.warning(
    "Confirm on this laptop that the configured model pulls and accepts images:\n\n"
    f"`ollama pull {config.DEFAULT_OLLAMA_MODEL}`\n\n"
    "Some model tags are text-only, with vision published under a separate "
    "tag. If the configured tag cannot read images, photographed tickets "
    "cannot be extracted. The model name is editable on **Settings and Backup**."
)
