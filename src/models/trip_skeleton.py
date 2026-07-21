"""Exact trip dates and city-stay allocation contracts."""

from __future__ import annotations

from datetime import date, timedelta

from pydantic import BaseModel, Field, model_validator


class FlightWindowOption(BaseModel):
    """Cheapest provider offer found for one departure/return date pair."""

    departure_date: date
    return_date: date
    total_amount: str
    currency: str = "USD"
    offer_id: str = ""
    airline_name: str = ""
    origin: str = ""
    destination: str = ""


class FlightWindowSearchResult(BaseModel):
    """Transparent coverage and ranked options for a flexible date window."""

    origin: str
    destination: str
    earliest_departure: date
    latest_return: date
    duration_days: int = Field(ge=1, le=365)
    total_valid_pairs: int = Field(ge=0)
    searched_pairs: int = Field(ge=0)
    coverage_complete: bool
    failed_pairs: int = Field(default=0, ge=0)
    options: list[FlightWindowOption] = Field(default_factory=list)


class CityStay(BaseModel):
    """One contiguous hotel stay within the selected trip dates."""

    sequence: int = Field(ge=1)
    city: str
    check_in: date
    check_out: date
    nights: int = Field(ge=1)

    @model_validator(mode="after")
    def _validate_nights(self) -> CityStay:
        actual = (self.check_out - self.check_in).days
        if actual != self.nights:
            raise ValueError(
                f"stay nights mismatch for {self.city}: expected {self.nights}, got {actual}"
            )
        return self


class TripSkeleton(BaseModel):
    """Exact selected trip interval and complete city/night allocation."""

    start_date: date
    end_date: date
    duration_days: int = Field(ge=1, le=365)
    total_nights: int = Field(ge=0)
    entry_city: str
    exit_city: str
    stays: list[CityStay] = Field(default_factory=list)
    selected_flight: FlightWindowOption | None = None
    allocation_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_calendar_and_stays(self) -> TripSkeleton:
        inclusive_days = (self.end_date - self.start_date).days + 1
        if inclusive_days != self.duration_days:
            raise ValueError(
                f"duration mismatch: {self.start_date} to {self.end_date} is "
                f"{inclusive_days} inclusive days, not {self.duration_days}"
            )
        if self.total_nights != max(0, self.duration_days - 1):
            raise ValueError("total_nights must equal duration_days - 1")
        if sum(stay.nights for stay in self.stays) != self.total_nights:
            raise ValueError("allocated stay nights must equal total_nights")
        for index, stay in enumerate(self.stays):
            if stay.sequence != index + 1:
                raise ValueError("stay sequence must be contiguous and 1-based")
            expected_check_in = (
                self.start_date if index == 0 else self.stays[index - 1].check_out
            )
            if stay.check_in != expected_check_in:
                raise ValueError("city stays must be contiguous")
        if self.stays and self.stays[-1].check_out != self.end_date:
            raise ValueError("last city stay must end on the trip end date")
        if self.selected_flight and (
            self.selected_flight.departure_date != self.start_date
            or self.selected_flight.return_date != self.end_date
        ):
            raise ValueError("selected flight dates must match the trip interval")
        return self


def allocate_city_stays(
    cities: list[str],
    *,
    start_date: date,
    duration_days: int,
    return_to_entry: bool = False,
) -> list[CityStay]:
    """Allocate nights evenly while preserving the user's city order."""
    ordered = [city.strip() for city in cities if city.strip()]
    if not ordered:
        raise ValueError("at least one destination city is required")
    total_nights = duration_days - 1
    required_segments = len(ordered) + (
        1 if return_to_entry and len(ordered) > 1 else 0
    )
    if total_nights < required_segments:
        raise ValueError(
            f"{duration_days} days provide {total_nights} nights, which cannot "
            f"cover {required_segments} city stays with at least one night each"
        )

    final_gateway_nights = 1 if return_to_entry and len(ordered) > 1 else 0
    distributable_nights = total_nights - final_gateway_nights
    base_nights, remainder = divmod(distributable_nights, len(ordered))
    cursor = start_date
    stays: list[CityStay] = []
    for index, city in enumerate(ordered):
        nights = base_nights + (1 if index < remainder else 0)
        check_out = cursor + timedelta(days=nights)
        stays.append(
            CityStay(
                sequence=index + 1,
                city=city,
                check_in=cursor,
                check_out=check_out,
                nights=nights,
            )
        )
        cursor = check_out
    if final_gateway_nights:
        check_out = cursor + timedelta(days=final_gateway_nights)
        stays.append(
            CityStay(
                sequence=len(stays) + 1,
                city=ordered[0],
                check_in=cursor,
                check_out=check_out,
                nights=final_gateway_nights,
            )
        )
    return stays


def build_trip_skeleton(
    *,
    cities: list[str],
    start_date: date,
    duration_days: int,
    selected_flight: FlightWindowOption | None = None,
    return_to_entry: bool = False,
) -> TripSkeleton:
    """Build and validate a deterministic exact-date trip skeleton."""
    end_date = start_date + timedelta(days=duration_days - 1)
    stays = allocate_city_stays(
        cities,
        start_date=start_date,
        duration_days=duration_days,
        return_to_entry=return_to_entry,
    )
    return TripSkeleton(
        start_date=start_date,
        end_date=end_date,
        duration_days=duration_days,
        total_nights=duration_days - 1,
        entry_city=cities[0],
        exit_city=stays[-1].city,
        stays=stays,
        selected_flight=selected_flight,
        allocation_notes=[
            "Nights are allocated as evenly as possible in the requested city order."
        ],
    )
