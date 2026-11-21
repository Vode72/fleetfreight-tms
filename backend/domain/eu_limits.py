"""EU maximum weight and length of a semi-trailer combination in international traffic (D89).

Council Directive 96/53/EC, Annex I, as amended: an articulated vehicle (tractor and
semi-trailer) with five or six axles may weigh 40 tonnes and be 16.50 m long in international
traffic. The value is recorded once here, not per country; national limits are in
``country_rules`` and Plan Check uses the strictest value along the route.

Source: Commission impact assessment SWD(2023) 445 final, which states the limits in force
("16.50 m and 40 tonnes for articulated vehicles with 5 or 6 axles"), checked 2026-11-21.
D89 excludes the report's country table as a source; this is its statement of the EU law.
The directive is being revised (COM(2023) 445); new values are a new decision, not an edit.
"""

from typing import Final

EU_SOURCE_URL: Final = "https://data.consilium.europa.eu/doc/document/ST-11722-2023-ADD-2/en/pdf"
EU_CHECKED_ON: Final = "2026-11-21"

# Articulated vehicle (tractor and semi-trailer) with five or six axles, international traffic.
EU_SEMI_TRAILER_MAX_GROSS_WEIGHT_KG: Final = 40_000
EU_SEMI_TRAILER_MAX_LENGTH_MM: Final = 16_500


def strictest(*limits: int | None) -> int | None:
    """The lowest recorded limit; None when none is recorded (NULL = not recorded)."""
    recorded = [x for x in limits if x is not None]
    return min(recorded) if recorded else None
