"""Money must be exact. These tests guard the two rules in src/money.py."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src import repository as repo
from src.money import (
    Money,
    MoneyError,
    Percent,
    Quantity,
    Rate,
    format_money,
    parse_decimal,
    quantize_money,
    to_decimal,
)


class TestCoercion:
    def test_float_is_rejected(self):
        # Decimal(0.1) is 0.1000000000000000055511151231257827; allowing floats
        # in would let that reach an invoice.
        with pytest.raises(MoneyError, match="float"):
            to_decimal(0.1)

    def test_bool_is_rejected(self):
        with pytest.raises(MoneyError):
            to_decimal(True)

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("1234.50", Decimal("1234.50")),
            ("$1,234.50", Decimal("1234.50")),
            ("  87.5  ", Decimal("87.5")),
            ("-40.00", Decimal("-40.00")),
            ("0", Decimal("0")),
        ],
    )
    def test_parses_human_input(self, text, expected):
        assert parse_decimal(text) == expected

    @pytest.mark.parametrize("text", ["", "   ", "abc", "12.3.4", "$"])
    def test_rejects_garbage(self, text):
        with pytest.raises(MoneyError):
            parse_decimal(text)


class TestRounding:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("2.675", "2.68"),  # ROUND_HALF_EVEN would give 2.67
            ("2.665", "2.67"),
            ("0.125", "0.13"),
            ("0.135", "0.14"),
            ("-2.675", "-2.68"),  # ties go away from zero
            ("1.004", "1.00"),
            ("1.005", "1.01"),
        ],
    )
    def test_half_up_at_the_boundary(self, value, expected):
        assert quantize_money(value) == Decimal(expected)

    def test_addition_does_not_drift(self):
        total = sum((Decimal("0.10") for _ in range(10)), Decimal("0"))
        assert total == Decimal("1.00")
        # The same arithmetic in binary floating point does not land on 1.0.
        assert sum(0.10 for _ in range(10)) != 1.0

    def test_formats_for_display(self):
        assert format_money(Decimal("1234.5")) == "$1,234.50 CAD"
        assert format_money(Decimal("-40")) == "-$40.00 CAD"


class TestScaledStorage:
    @pytest.mark.parametrize(
        "column,value,minor_units",
        [
            (Money(), Decimal("1234.50"), 123450),
            (Money(), Decimal("-40.00"), -4000),
            (Money(), Decimal("0"), 0),
            (Rate(), Decimal("87.5000"), 875000),
            (Quantity(), Decimal("10.500"), 10500),
            (Percent(), Decimal("0.0500"), 500),
        ],
    )
    def test_stores_exact_minor_units(self, column, value, minor_units):
        assert column.process_bind_param(value, None) == minor_units
        assert column.process_result_value(minor_units, None) == value

    def test_none_round_trips(self):
        assert Money().process_bind_param(None, None) is None
        assert Money().process_result_value(None, None) is None

    def test_excess_precision_is_refused_not_silently_rounded(self):
        # Rounding here would hide a real decision, e.g. a rate keyed with more
        # precision than the column carries.
        with pytest.raises(MoneyError, match="decimal places"):
            Money().process_bind_param(Decimal("1.005"), None)
        with pytest.raises(MoneyError, match="decimal places"):
            Rate().process_bind_param(Decimal("87.55555"), None)


class TestDatabaseRoundTrip:
    def test_money_survives_the_database_unchanged(self, session, project):
        value = Decimal("250000.01")
        po = repo.create_purchase_order(
            session, project_id=project.id, po_number="45002381", original_value=value
        )
        session.commit()
        session.expire_all()

        reloaded = repo.find_purchase_order(session, project.id, "45002381")
        assert reloaded.original_value == value
        assert isinstance(reloaded.original_value, Decimal)
        assert repo.po_remaining_value(reloaded) == value
        assert po.id == reloaded.id

    def test_many_small_amounts_sum_exactly(self, session, project):
        """Ten $0.10 lines must total exactly $1.00, not 0.9999999999999999."""
        for index in range(10):
            repo.create_purchase_order(
                session,
                project_id=project.id,
                po_number=f"PO-{index}",
                original_value=Decimal("0.10"),
            )
        session.commit()

        orders = repo.list_purchase_orders(session, project.id)
        total = sum((po.original_value for po in orders), Decimal("0"))
        assert total == Decimal("1.00")

    def test_rate_precision_is_preserved(self, session, rate_card):
        lines = repo.list_rate_lines(session, rate_card.id)
        assert lines[0].regular_rate == Decimal("87.5000")
        assert lines[0].overtime_rate == Decimal("131.2500")
