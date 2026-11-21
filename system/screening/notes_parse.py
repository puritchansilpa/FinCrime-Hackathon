"""[Workstream A] Extract facts from support/onboarding notes.

STUB from kickoff: the real parsers come in task A5.
"""
from typing import Optional


def parse_kyc_note(text: str) -> Optional[dict]:
    """Keys: name, dob, doc_country, provider, checked_at, result. None if not a kyc sentence."""
    return None


def parse_residence_note(text: str) -> list:
    """Countries the customer lived or worked in, e.g. 'worked and lived in Pakistan from 2013 to 2015'."""
    return []
