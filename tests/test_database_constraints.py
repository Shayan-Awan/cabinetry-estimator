"""The schema's guarantees only hold if SQLite is configured to enforce them."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from src import database, repository as repo
from src.models import CompanySettings, LineCategory, Project, RateLine


class TestPragmas:
    def test_wal_is_enabled(self, db):
        assert database.pragma("journal_mode") == "wal"

    def test_foreign_keys_are_enforced(self, db):
        # SQLite defaults this to OFF per connection; without the connect
        # listener every foreign key in the schema would be decorative.
        assert database.pragma("foreign_keys") == 1


class TestForeignKeys:
    def test_project_requires_an_existing_customer(self, session):
        session.add(Project(customer_id=999, name="Orphan"))
        with pytest.raises(IntegrityError):
            session.flush()

    def test_rate_line_requires_an_existing_card(self, session):
        session.add(
            RateLine(rate_card_id=999, category=LineCategory.LABOUR, code="X")
        )
        with pytest.raises(IntegrityError):
            session.flush()


class TestUniqueness:
    def test_company_settings_is_a_singleton(self, session):
        assert session.get(CompanySettings, 1) is not None
        session.add(CompanySettings(id=2, legal_name="Second company"))
        with pytest.raises(IntegrityError):
            session.flush()

    def test_po_number_is_unique_within_a_project(self, session, project):
        repo.create_purchase_order(
            session,
            project_id=project.id,
            po_number="45002381",
            original_value=Decimal("100.00"),
        )
        with pytest.raises(IntegrityError):
            repo.create_purchase_order(
                session,
                project_id=project.id,
                po_number="45002381",
                original_value=Decimal("200.00"),
            )

    def test_same_po_number_is_allowed_on_a_different_project(self, session, project):
        other = repo.create_project(
            session, customer_id=project.customer_id, name="Plant 5 Turnaround"
        )
        repo.create_purchase_order(
            session,
            project_id=project.id,
            po_number="45002381",
            original_value=Decimal("100.00"),
        )
        second = repo.create_purchase_order(
            session,
            project_id=other.id,
            po_number="45002381",
            original_value=Decimal("100.00"),
        )
        assert second.id is not None

    def test_rate_code_is_unique_within_a_card(self, session, rate_card):
        with pytest.raises(IntegrityError):
            repo.add_rate_line(
                session,
                rate_card_id=rate_card.id,
                category=LineCategory.LABOUR,
                code="JM-WELD",
                regular_rate=Decimal("90.0000"),
            )


class TestAuditTrail:
    def test_changes_are_recorded(self, session, project):
        from src import audit

        events = audit.recent(session)
        types = [event.event_type for event in events]
        assert "project_created" in types
        assert "customer_created" in types

    def test_audit_records_before_and_after_values(self, session, project):
        from src import audit

        repo.update_project(session, project.id, location="Conklin")
        latest = audit.recent(session, limit=1)[0]
        assert latest.event_type == "project_updated"
        assert "Fort McMurray" in (latest.old_value_json or "")
        assert "Conklin" in (latest.new_value_json or "")
