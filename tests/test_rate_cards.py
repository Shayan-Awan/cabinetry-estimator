"""Rate cards decide what gets billed, so their date handling must be exact."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src import repository as repo
from src.models import LineCategory, TimeType
from src.repository import InvalidDateRangeError, RateCardOverlapError


class TestOverlapRejection:
    @pytest.mark.parametrize(
        "start,end",
        [
            (date(2026, 1, 1), date(2026, 12, 31)),  # identical
            (date(2026, 6, 1), date(2026, 6, 30)),  # fully contained
            (date(2025, 1, 1), date(2026, 1, 1)),  # touches the first day
            (date(2026, 12, 31), date(2027, 6, 30)),  # touches the last day
            (date(2025, 1, 1), None),  # open-ended, swallows the card
        ],
    )
    def test_overlapping_periods_are_refused(self, session, project, rate_card, start, end):
        with pytest.raises(RateCardOverlapError):
            repo.create_rate_card(
                session,
                project_id=project.id,
                name="Conflicting",
                effective_from=start,
                effective_to=end,
            )

    @pytest.mark.parametrize(
        "start,end",
        [
            (date(2027, 1, 1), None),  # starts the day after
            (date(2027, 1, 1), date(2027, 12, 31)),
            (date(2025, 1, 1), date(2025, 12, 31)),  # ends the day before
        ],
    )
    def test_adjacent_periods_are_allowed(self, session, project, rate_card, start, end):
        card = repo.create_rate_card(
            session,
            project_id=project.id,
            name="Adjacent",
            effective_from=start,
            effective_to=end,
        )
        assert card.id is not None

    def test_other_projects_are_unaffected(self, session, project, rate_card):
        other = repo.create_project(
            session, customer_id=project.customer_id, name="Plant 5 Turnaround"
        )
        card = repo.create_rate_card(
            session,
            project_id=other.id,
            name="Same dates, different project",
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 12, 31),
        )
        assert card.id is not None

    def test_backwards_range_is_refused(self, session, project):
        with pytest.raises(InvalidDateRangeError):
            repo.create_rate_card(
                session,
                project_id=project.id,
                name="Backwards",
                effective_from=date(2026, 12, 31),
                effective_to=date(2026, 1, 1),
            )


class TestEffectiveLookup:
    @pytest.mark.parametrize(
        "work_date",
        [date(2026, 1, 1), date(2026, 7, 20), date(2026, 12, 31)],
    )
    def test_finds_the_card_covering_the_work_date(
        self, session, project, rate_card, work_date
    ):
        found = repo.find_effective_rate_card(session, project.id, work_date)
        assert found is not None and found.id == rate_card.id

    @pytest.mark.parametrize("work_date", [date(2025, 12, 31), date(2027, 1, 1)])
    def test_returns_none_outside_every_period(self, session, project, rate_card, work_date):
        # Phase 3 turns this into a blocking validation rather than a guess.
        assert repo.find_effective_rate_card(session, project.id, work_date) is None

    def test_open_ended_card_covers_the_distant_future(self, session, project):
        repo.create_rate_card(
            session,
            project_id=project.id,
            name="Open ended",
            effective_from=date(2026, 1, 1),
            effective_to=None,
        )
        assert repo.find_effective_rate_card(session, project.id, date(2099, 1, 1)) is not None

    def test_picks_the_right_card_when_several_exist(self, session, project, rate_card):
        later = repo.create_rate_card(
            session,
            project_id=project.id,
            name="2027 Rates",
            effective_from=date(2027, 1, 1),
            effective_to=None,
        )
        found_2026 = repo.find_effective_rate_card(session, project.id, date(2026, 7, 20))
        found_2027 = repo.find_effective_rate_card(session, project.id, date(2027, 7, 20))
        assert found_2026.id == rate_card.id
        assert found_2027.id == later.id


class TestRateResolution:
    def test_resolves_a_rate_line_for_a_work_date(self, session, project, rate_card):
        line = repo.find_rate_line(
            session, project.id, date(2026, 7, 20), LineCategory.LABOUR, "JM-WELD"
        )
        assert line is not None
        assert line.regular_rate == Decimal("87.5000")

    def test_returns_none_for_an_unknown_code(self, session, project, rate_card):
        assert (
            repo.find_rate_line(
                session, project.id, date(2026, 7, 20), LineCategory.LABOUR, "NOPE"
            )
            is None
        )

    def test_returns_none_when_no_card_covers_the_date(self, session, project, rate_card):
        assert (
            repo.find_rate_line(
                session, project.id, date(2030, 1, 1), LineCategory.LABOUR, "JM-WELD"
            )
            is None
        )

    def test_category_must_match(self, session, project, rate_card):
        assert (
            repo.find_rate_line(
                session, project.id, date(2026, 7, 20), LineCategory.EQUIPMENT, "JM-WELD"
            )
            is None
        )

    def test_time_type_rates_are_read_from_the_card(self, session, project, rate_card):
        line = repo.find_rate_line(
            session, project.id, date(2026, 7, 20), LineCategory.LABOUR, "JM-WELD"
        )
        assert repo.rate_for_time_type(line, TimeType.REGULAR) == Decimal("87.5000")
        assert repo.rate_for_time_type(line, TimeType.OVERTIME) == Decimal("131.2500")

    def test_unset_double_time_stays_unset(self, session, project, rate_card):
        """An unagreed premium rate must not fall back to the regular rate.

        Falling back would quietly bill double time at straight time.
        """
        line = repo.find_rate_line(
            session, project.id, date(2026, 7, 20), LineCategory.LABOUR, "JM-WELD"
        )
        assert repo.rate_for_time_type(line, TimeType.DOUBLE_TIME) is None
