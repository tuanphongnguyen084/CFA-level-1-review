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
import streamlit as st

_KEY = "cfa_access_v1"


def _valid_emails():
    try:
        emails = st.secrets.get("access_emails", [])
    except Exception:  # noqa: BLE001 — no secrets.toml at all locally
        emails = []
    if isinstance(emails, str):
        emails = [emails]
    return {str(e).strip().lower() for e in emails if str(e).strip()}


def _local_storage():
    if "_access_ls" in st.session_state:
        return st.session_state["_access_ls"]
    ls = None
    try:
        from streamlit_local_storage import LocalStorage
        # Explicit key: the library defaults every instance to the same
        # internal session_state key ("storage_init"), which this gate
        # would then share with core/progress.py's own instance. Verified
        # in a real browser that sharing it does NOT break anything today,
        # so this is defensive hygiene against future confusion, not a
        # bug fix.
        ls = LocalStorage(key="cfa_access_storage")
    except Exception:  # noqa: BLE001 — component optional
        ls = None
    st.session_state["_access_ls"] = ls
    return ls


def require_access():
    """Block the rest of the script (st.stop()) until a known email is
    entered. No-op if no emails are configured in secrets."""
    valid = _valid_emails()
    if not valid:
        return
    if st.session_state.get("_unlocked"):
        return

    ls = _local_storage()

    if not st.session_state.get("_access_hydrated"):
        st.session_state["_access_hydrated"] = True
        if ls is not None:
            try:
                raw = ls.getItem(_KEY)
            except Exception:  # noqa: BLE001
                raw = None
            if raw:
                st.session_state["_unlocked"] = True
                return

    st.markdown(
        "<h2 style='text-align:center;margin-top:12vh;'>🔒 CFA Quiz</h2>"
        "<p style='text-align:center;color:#b3b3b3;'>"
        "Nhập email đã đăng ký để tiếp tục</p>",
        unsafe_allow_html=True,
    )
    _, col, _ = st.columns([1, 2, 1])
    with col:
        with st.form("access_form"):
            email_input = st.text_input(
                "Email", label_visibility="collapsed",
                placeholder="you@email.com",
            )
            submitted = st.form_submit_button(
                "Mở khóa", use_container_width=True, type="primary",
            )
        if submitted:
            if email_input.strip().lower() in valid:
                st.session_state["_unlocked"] = True
                if ls is not None:
                    try:
                        ls.setItem(_KEY, "1", key="cfa_access_writer")
                    except Exception:  # noqa: BLE001
                        pass
                st.rerun()
            else:
                st.error("Email này chưa được cấp quyền truy cập.")
    st.stop()
