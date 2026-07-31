"""
Optional email-allowlist gate for the whole app.

Design: off by default (local dev / AppTest never need this). The gate only
activates once at least one address exists in ``st.secrets["access_emails"]``
— that's the single switch for "this deployment is being sold" vs. "this is
my own free instance". Using the buyer's own email (rather than an opaque
key string) doubles as the record of who paid, and makes casual sharing feel
more like handing out your own login than passing around a cheat code.

Unlock state persists in the browser (localStorage, same component/pattern
as core/progress.py) so a returning buyer doesn't have to retype their email
every visit; only a boolean flag is stored client-side, never the email.

Emails are a flat list, one per buyer, so a refunded/leaked address can be
revoked by deleting just that line from the Secrets UI on Streamlit Cloud —
no accounts, no backend. Comparison is case-insensitive.

Note: this still doesn't bind a login to one device -- a buyer can retype
their own email on a second browser and it will work there too. That's an
accepted, low-effort tradeoff; real device-binding needs an external
datastore since st.secrets is read-only from the running app.
"""
import os
import time

import streamlit as st

_KEY = "cfa_access_v1"
# Reruns allowed while waiting for the browser to hand back its saved email.
_MAX_HYDRATE_TRIES = 4

# Same escape hatch core/progress.py uses: with no real frontend the storage
# component blocks waiting for a round-trip that never comes, so headless
# checks (AppTest) must skip it entirely.
_DISABLED = bool(os.environ.get("CFA_DISABLE_LOCALSTORAGE"))


def _valid_emails():
    try:
        emails = st.secrets.get("access_emails", [])
    except Exception:  # noqa: BLE001 — no secrets.toml at all locally
        emails = []
    if isinstance(emails, str):
        emails = [emails]
    return {str(e).strip().lower() for e in emails if str(e).strip()}


def _component():
    """The raw storage component function, or None.

    Same reasoning as core/progress.py: the library's ``LocalStorage`` class
    must be avoided because its constructor spins in a blocking
    ``while ... time.sleep(0.1)`` loop waiting on the browser, which hung the
    whole app under Streamlit 1.60. Calling the component directly returns a
    default until the browser answers, so nothing can block.
    """
    if _DISABLED:
        return None
    try:
        from streamlit_local_storage import _st_local_storage
        return _st_local_storage
    except Exception:  # noqa: BLE001 — component optional
        return None


def _saved_email(comp):
    """The email this browser last unlocked with (None if none/not yet)."""
    try:
        got = comp(method="getAll", key="cfa_access_read", default={})
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(got, dict):
        return None
    val = got.get(_KEY)
    return str(val).strip().lower() if val else None


def require_access():
    """Block the rest of the script (st.stop()) until a known email is
    entered. No-op if no emails are configured in secrets."""
    valid = _valid_emails()
    if not valid:
        return
    if st.session_state.get("_unlocked"):
        return

    comp = _component()

    # A custom component returns its default on the first script run and only
    # delivers the real browser payload on a later run. Reading once would
    # therefore always look like "nothing saved" and force every returning
    # buyer to retype their email, so retry across a few reruns (bounded, so
    # a genuinely-empty store still falls through to the form).
    if comp is not None and not st.session_state.get("_access_hydrated"):
        raw = _saved_email(comp)
        # What's stored is the email itself, re-checked against the current
        # allowlist on every visit. Storing a bare "unlocked" flag instead
        # would make revocation useless: deleting someone from secrets
        # wouldn't lock out the browser that had already unlocked.
        if raw and str(raw).strip().lower() in valid:
            st.session_state["_unlocked"] = True
            return
        if raw:
            # Known browser, but that email no longer has access.
            st.session_state["_revoked"] = True
        tries = st.session_state.get("_access_tries", 0)
        if tries < _MAX_HYDRATE_TRIES:
            st.session_state["_access_tries"] = tries + 1
            time.sleep(0.3)
            st.rerun()
        st.session_state["_access_hydrated"] = True

    # The gate lives in a placeholder so a successful unlock can wipe it and
    # let the app render in this same run. Doing it that way (instead of
    # st.rerun()) is what makes the "remember me" write actually land: a
    # rerun aborts the script before the writer component's JS has a chance
    # to execute in the browser, so the flag was never saved and every
    # refresh asked for the email again (verified by reading
    # window.localStorage from a real browser).
    gate = st.empty()
    with gate.container():
        st.markdown(
            "<h2 style='text-align:center;margin-top:12vh;'>🔒 CFA Quiz</h2>"
            "<p style='text-align:center;color:#b3b3b3;'>"
            "Nhập email đã đăng ký để tiếp tục</p>",
            unsafe_allow_html=True,
        )
        _, col, _ = st.columns([1, 2, 1])
        with col:
            if st.session_state.get("_revoked"):
                st.warning("Quyền truy cập của email này đã hết hiệu lực.")
            with st.form("access_form"):
                email_input = st.text_input(
                    "Email", label_visibility="collapsed",
                    placeholder="you@email.com",
                )
                submitted = st.form_submit_button(
                    "Mở khóa", use_container_width=True, type="primary",
                )
            if submitted and email_input.strip().lower() not in valid:
                st.error("Email này chưa được cấp quyền truy cập.")

    email_clean = email_input.strip().lower()
    if submitted and email_clean in valid:
        st.session_state["_unlocked"] = True
        st.session_state.pop("_revoked", None)
        gate.empty()
        if comp is not None:
            try:
                # Mounted outside the emptied container so it survives, and
                # given a moment to actually run before the app draws over it.
                comp(method="setItem", itemKey=_KEY, itemValue=email_clean,
                     key="cfa_access_writer")
                time.sleep(0.8)
            except Exception:  # noqa: BLE001
                pass
        return

    st.stop()
