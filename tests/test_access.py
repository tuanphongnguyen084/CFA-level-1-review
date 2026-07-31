"""Access-gate decision tests.

The gate is the paywall of a paid app, so its decision logic is tested
directly instead of only through a live Google round-trip (which needs real
OAuth credentials and a human at a browser).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.access import decide  # noqa: E402

BUYERS = {"an@gmail.com", "binh@gmail.com"}


def test_anonymous_visitor_is_sent_to_login():
    assert decide(False, None, BUYERS) == "login"
    # Even a known address means nothing until Google has verified it.
    assert decide(False, "an@gmail.com", BUYERS) == "login"


def test_allowlisted_buyer_gets_in():
    assert decide(True, "an@gmail.com", BUYERS) == "allow"


def test_email_match_ignores_case_and_padding():
    assert decide(True, "  AN@Gmail.COM  ", BUYERS) == "allow"


def test_signed_in_stranger_is_denied():
    assert decide(True, "someone@else.com", BUYERS) == "deny"


def test_revoked_buyer_is_denied():
    remaining = {"binh@gmail.com"}
    assert decide(True, "an@gmail.com", remaining) == "deny"


def test_empty_allowlist_admits_nobody():
    """Fails closed: a misconfigured allowlist must not mean 'free for all'."""
    assert decide(True, "an@gmail.com", set()) == "deny"
    assert decide(True, "", set()) == "deny"


def test_missing_email_claim_is_denied():
    assert decide(True, None, BUYERS) == "deny"
    assert decide(True, "   ", BUYERS) == "deny"
