"""Tests for the CSV-backed IATA repository."""

from pathlib import Path

import pytest

from src.tools.iata_repository import IataRepository


def _write_csv(path: Path, contents: str) -> Path:
    path.write_text(contents, encoding="utf-8")
    return path


def _load_repository(tmp_path: Path, *, alias_code: str = "AAA") -> IataRepository:
    airports = _write_csv(
        tmp_path / "airports.csv",
        "id,airport_name,city_name,country,iata_code,icao_code,latitude,longitude,type,scheduled_service,source\n"
        "1,Alpha Regional,Springfield,Exampleland,AAA,,,,medium_airport,no,test\n"
        "2,Alpha International,Springfield,Exampleland,AAB,,,,large_airport,yes,test\n",
    )
    aliases = _write_csv(
        tmp_path / "aliases.csv",
        f"alias,iata_code\nlocal springfield,{alias_code}\n",
    )
    primary_airports = _write_csv(
        tmp_path / "primary_airports.csv",
        "city_name,iata_code\nspringfield,AAB\n",
    )
    countries = _write_csv(
        tmp_path / "countries.csv",
        "country_name,iso_code\nExampleland,EX\n",
    )
    return IataRepository.from_csv_files(
        airports_path=airports,
        aliases_path=aliases,
        primary_airports_path=primary_airports,
        countries_path=countries,
    )


def test_repository_loads_csv_policy_and_resolves_names(tmp_path: Path):
    repository = _load_repository(tmp_path)

    assert repository.resolve_code("Springfield") == "AAB"
    assert repository.resolve_code("local springfield") == "AAA"
    assert repository.resolve_code("Alpha International") == "AAB"
    assert repository.country_iso_for_code("AAB") == "EX"


def test_repository_rejects_alias_to_unknown_airport(tmp_path: Path):
    with pytest.raises(ValueError, match="unknown IATA code 'ZZZ'"):
        _load_repository(tmp_path, alias_code="ZZZ")
