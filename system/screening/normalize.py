"""[Workstream B] Dates, countries and name parts.

STUB from kickoff: B replaces these with the real versions (task B1).
"""
from typing import Optional

from .models import PartialDate


def parse_date(s) -> Optional[PartialDate]:
    """Parse ISO, DD/MM/YYYY (day-first), '17 June 1976', 'June 17, 1976', '1976', '1976-06'."""
    return None


def to_country(s) -> Optional[str]:
    """Map a country name, ISO2 code or demonym to one canonical country name."""
    return None


def name_parts(s, is_company: bool = False) -> list:
    """Normalised, distinct name parts (no initials, placeholders or legal forms)."""
    return []
