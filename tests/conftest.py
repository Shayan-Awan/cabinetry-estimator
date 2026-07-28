"""Shared test fixtures.

Each test gets its own database in a temporary directory, so nothing touches
the real ``data/`` folder.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlmodel import Session

from src import config, database, repository as repo
from src.models import LineCategory


@pytest.fixture
def db(tmp_path, monkeypatch):
    """An initialised, empty database isolated to this test."""
    monkeypatch.setenv("FIELD_TICKET_DATA_DIR", str(tmp_path / "data"))
    database.dispose_engines()
    database.init_db()
    yield
    database.dispose_engines()


@pytest.fixture
def session(db):
    """A session the test controls.

    Deliberately not ``database.get_session()``: that commits on exit, which
    fails during teardown for the tests that provoke an IntegrityError on
    purpose. Here the test decides when to commit.
    """
    session = Session(database.get_engine(), expire_on_commit=False)
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def project(session):
    """A customer with one project, the minimum context for rates and POs."""
    customer = repo.create_customer(session, legal_name="Acme Energy Ltd")
    return repo.create_project(
        session,
        customer_id=customer.id,
        name="Plant 4 Maintenance",
        location="Fort McMurray",
    )


@pytest.fixture
def rate_card(session, project):
    """A rate card effective for all of 2026 with one labour rate."""
    card = repo.create_rate_card(
        session,
        project_id=project.id,
        name="2026 Rates",
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 12, 31),
    )
    repo.add_rate_line(
        session,
        rate_card_id=card.id,
        category=LineCategory.LABOUR,
        code="JM-WELD",
        description="Journeyman Welder",
        regular_rate=Decimal("87.5000"),
        overtime_rate=Decimal("131.2500"),
        double_time_rate=None,
    )
    return card


@pytest.fixture
def data_dirs():
    return config.all_data_dirs
