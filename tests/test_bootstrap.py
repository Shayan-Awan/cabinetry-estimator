"""First launch must produce a working database without any user action."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlmodel import SQLModel, text

from src import config, database, repository as repo
from src.storage import resolve_within, safe_filename


class TestInitialisation:
    def test_creates_every_data_directory(self, db):
        for directory in config.all_data_dirs():
            assert directory.is_dir(), f"{directory} was not created"

    def test_creates_every_table(self, db):
        with database.get_engine().connect() as connection:
            rows = connection.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
            present = {row[0] for row in rows}
        expected = set(SQLModel.metadata.tables)
        assert expected <= present, f"missing tables: {expected - present}"

    def test_is_safe_to_run_twice(self, db):
        """Startup calls init_db() on every launch, not only the first."""
        database.init_db()
        database.init_db()
        with database.get_session() as session:
            assert repo.get_company_settings(session) is not None

    def test_seeds_usable_billing_defaults(self, db):
        with database.get_session() as session:
            settings = repo.get_company_settings(session)
        assert settings.default_gst_rate == Decimal("0.0500")  # Alberta GST
        assert settings.next_invoice_number == config.DEFAULT_STARTING_INVOICE_NUMBER
        assert settings.ollama_model == config.DEFAULT_OLLAMA_MODEL

    def test_company_details_start_incomplete(self, db):
        with database.get_session() as session:
            settings = repo.get_company_settings(session)
        assert not repo.company_settings_complete(settings)

    def test_uses_the_configured_data_directory(self, db, tmp_path):
        assert config.database_path().is_relative_to(tmp_path)
        assert config.database_path().exists()


class TestPathSafety:
    def test_strips_directory_components(self):
        assert safe_filename("../../etc/passwd") == "passwd"

    def test_handles_windows_separators(self):
        assert "\\" not in safe_filename(r"..\..\windows\system32\evil.pdf")

    def test_falls_back_when_nothing_survives(self):
        assert safe_filename("...") == "document"
        assert safe_filename("") == "document"

    def test_keeps_a_reasonable_name_intact(self):
        assert safe_filename("Ticket FT-1042.pdf") == "Ticket_FT-1042.pdf"

    def test_resolve_within_allows_children(self, db):
        target = resolve_within(config.originals_dir(), "ticket.pdf")
        assert target.parent == config.originals_dir().resolve()

    def test_resolve_within_blocks_traversal(self, db):
        with pytest.raises(ValueError, match="escapes"):
            resolve_within(config.originals_dir(), "../../etc/passwd")
