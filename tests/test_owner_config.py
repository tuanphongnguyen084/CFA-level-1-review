"""owner_emails / access_emails must survive the usual secrets.toml slips.

The lists are pasted by hand into Streamlit Cloud's Secrets box. TOML assigns
every key written after a ``[auth]`` header to that table, so appending
``owner_emails`` at the bottom quietly becomes ``auth.owner_emails`` and the
owner loses access to their own material. Reading both placements cannot
widen access, since an address still has to appear in the list.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import access  # noqa: E402


@pytest.fixture
def fake_secrets(monkeypatch):
    store = {}

    def _get(name, default=None):
        return store.get(name, default)

    monkeypatch.setattr(access, "_secrets_section",
                        lambda name: _get(name))
    return store


AUTH = {"client_id": "x", "redirect_uri": "https://app/oauth2callback"}


def test_top_level_owner_list(fake_secrets):
    fake_secrets["auth"] = AUTH
    fake_secrets["owner_emails"] = ["Dev@Example.com "]
    assert access._owner_emails() == {"dev@example.com"}


def test_owner_list_pasted_under_the_auth_header(fake_secrets):
    fake_secrets["auth"] = dict(AUTH, owner_emails=["dev@example.com"])
    assert access._owner_emails() == {"dev@example.com"}


def test_comma_separated_string_is_accepted(fake_secrets):
    fake_secrets["auth"] = AUTH
    fake_secrets["owner_emails"] = "a@x.com, b@x.com"
    assert access._owner_emails() == {"a@x.com", "b@x.com"}


def test_missing_owner_list_grants_nobody(fake_secrets):
    fake_secrets["auth"] = AUTH
    assert access._owner_emails() == set()


def test_access_list_also_survives_the_auth_header_slip(fake_secrets):
    fake_secrets["auth"] = dict(AUTH, access_emails=["buyer@x.com"])
    assert access._valid_emails() == {"buyer@x.com"}


def test_top_level_wins_when_both_exist(fake_secrets):
    fake_secrets["auth"] = dict(AUTH, owner_emails=["stale@x.com"])
    fake_secrets["owner_emails"] = ["current@x.com"]
    assert access._owner_emails() == {"current@x.com"}
