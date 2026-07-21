"""TripSkeleton date and night-allocation invariant tests."""

from datetime import date

import pytest
from pydantic import ValidationError

from src.models import (
    CityStay,
    FlightWindowOption,
    TripSkeleton,
    allocate_city_stays,
    build_trip_skeleton,
)


def test_fourteen_day_trip_allocates_thirteen_nights_across_cities():
    skeleton = build_trip_skeleton(
        cities=["warszawa", "wroclaw", "krakow", "gdansk"],
        start_date=date(2026, 8, 20),
        duration_days=14,
    )

    assert skeleton.end_date == date(2026, 9, 2)
    assert skeleton.total_nights == 13
    assert [stay.nights for stay in skeleton.stays] == [4, 3, 3, 3]
    assert skeleton.stays[0].check_in == date(2026, 8, 20)
    assert skeleton.stays[-1].check_out == date(2026, 9, 2)


def test_duration_is_generic_not_hardcoded_to_fourteen_days():
    skeleton = build_trip_skeleton(
        cities=["paris", "lyon"],
        start_date=date(2026, 10, 1),
        duration_days=9,
    )

    assert skeleton.duration_days == 9
    assert skeleton.total_nights == 8
    assert skeleton.end_date == date(2026, 10, 9)
    assert [stay.nights for stay in skeleton.stays] == [4, 4]


def test_allocation_rejects_more_cities_than_available_nights():
    with pytest.raises(ValueError, match="cannot cover"):
        allocate_city_stays(
            ["a", "b", "c"],
            start_date=date(2026, 1, 1),
            duration_days=3,
        )


def test_skeleton_rejects_non_contiguous_stays():
    with pytest.raises(ValidationError, match="contiguous"):
        TripSkeleton(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 5),
            duration_days=5,
            total_nights=4,
            entry_city="a",
            exit_city="b",
            stays=[
                CityStay(
                    sequence=1,
                    city="a",
                    check_in=date(2026, 1, 1),
                    check_out=date(2026, 1, 3),
                    nights=2,
                ),
                CityStay(
                    sequence=2,
                    city="b",
                    check_in=date(2026, 1, 4),
                    check_out=date(2026, 1, 6),
                    nights=2,
                ),
            ],
        )


def test_skeleton_preserves_selected_flight_dates_and_price():
    flight = FlightWindowOption(
        departure_date=date(2026, 8, 25),
        return_date=date(2026, 9, 7),
        total_amount="742.50",
        currency="EUR",
        origin="BOG",
        destination="WAW",
    )
    skeleton = build_trip_skeleton(
        cities=["warszawa", "krakow"],
        start_date=flight.departure_date,
        duration_days=14,
        selected_flight=flight,
    )

    assert skeleton.end_date == flight.return_date
    assert skeleton.selected_flight.total_amount == "742.50"


def test_round_trip_reserves_final_night_at_entry_gateway():
    skeleton = build_trip_skeleton(
        cities=["warszawa", "wroclaw", "krakow", "gdansk"],
        start_date=date(2026, 8, 25),
        duration_days=14,
        return_to_entry=True,
    )

    assert skeleton.entry_city == "warszawa"
    assert skeleton.exit_city == "warszawa"
    assert [stay.city for stay in skeleton.stays] == [
        "warszawa",
        "wroclaw",
        "krakow",
        "gdansk",
        "warszawa",
    ]
    assert [stay.nights for stay in skeleton.stays] == [3, 3, 3, 3, 1]
    assert skeleton.stays[-1].check_out == skeleton.end_date
