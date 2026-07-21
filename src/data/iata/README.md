# IATA Resolution Data

The IATA resolver loads these files once when `src.tools.iata` is imported.
They keep changeable lookup facts separate from matching and ranking logic.

- `aliases.csv`: traveler-facing names and exonyms that differ from source data.
- `primary_airports.csv`: preferred airport for genuine same-city hub ties.
- `countries.csv`: generated country name to ISO alpha-2 mapping used for flags.

`../iata_codes.csv` and `countries.csv` are generated from OurAirports by
`scripts/download_iata.py`. Alias and primary-airport changes are curated and
must reference an IATA code present in the generated airport file; startup
validation fails with a clear error when a target code is invalid.
