"""
Access gate: Google sign-in + an email allowlist.

Why sign-in rather than a shared secret: an earlier version simply asked the
visitor to type an approved email, which is just a password — a buyer could
hand a friend the link and their email and the friend was in. Here the email
comes from Google's verified identity token, so it cannot be passed on
without also handing over the Google account itself.

Two independent switches, both read from secrets:

* ``[auth]`` (client_id/client_secret/redirect_uri/cookie_secret/
  server_metadata_url) — without it ``st.login()`` cannot work at all, so the
  gate turns itself off entirely. That keeps local development and the
  headless tests running exactly as before.
* ``access_emails`` — the list of buyers. Compared case-insensitively.

With ``[auth]`` present the gate fails CLOSED: an empty or missing
``access_emails`` admits nobody, because for a paid app "misconfigured"
must never mean "free for everyone". The message on that screen says what
to fix.
"""
import streamlit as st


def _secrets_section(name):
    try:
        return st.secrets.get(name, None)
    except Exception:  # noqa: BLE001 — no secrets file at all locally
        return None


def _auth_configured():
    """True when [auth] carries the keys st.login() actually needs."""
    auth = _secrets_section("auth")
    if not auth:
        return False
    try:
        return bool(auth.get("client_id")) and bool(auth.get("redirect_uri"))
    except Exception:  # noqa: BLE001
        return False


def _valid_emails():
    emails = _secrets_section("access_emails") or []
    if isinstance(emails, str):
        emails = [emails]
    return {str(e).strip().lower() for e in emails if str(e).strip()}


def decide(logged_in, email, valid_emails):
    """Pure access decision: "login" | "deny" | "allow".

    Kept free of Streamlit calls so the security boundary is directly
    unit-testable (see tests/test_access.py) rather than only reachable
    through a real Google round-trip.
    """
    if not logged_in:
        return "login"
    addr = (email or "").strip().lower()
    if addr and addr in valid_emails:
        return "allow"
    return "deny"


def _shell(title, body_html=None):
    st.markdown(
        f"<h2 style='text-align:center;margin-top:12vh;'>{title}</h2>"
        + (body_html or ""),
        unsafe_allow_html=True,
    )


def require_access():
    """Stop the script until a signed-in, allowlisted user is present.
    No-op unless [auth] is configured in secrets."""
    if not _auth_configured():
        return

    # st.user is always present; is_logged_in is False until OIDC completes.
    try:
        logged_in = bool(st.user.is_logged_in)
    except Exception:  # noqa: BLE001 — older/unsupported runtime
        return

    email = (getattr(st.user, "email", "") or "")
    verdict = decide(logged_in, email, _valid_emails())

    if verdict == "allow":
        return

    if verdict == "login":
        _shell(
            "🔒 CFA Quiz",
            "<p style='text-align:center;color:#b3b3b3;'>"
            "Đăng nhập bằng email đã đăng ký để tiếp tục.</p>",
        )
        _, col, _ = st.columns([1, 2, 1])
        with col:
            st.button("Đăng nhập với Google", on_click=st.login,
                      use_container_width=True, type="primary")
        st.stop()

    email = email.strip().lower()

    _shell(
        "Chưa có quyền truy cập",
        "<p style='text-align:center;color:#b3b3b3;'>"
        f"Tài khoản <b>{email or 'này'}</b> chưa được cấp quyền. "
        "Vui lòng liên hệ để được thêm vào danh sách.</p>",
    )
    _, col, _ = st.columns([1, 2, 1])
    with col:
        # Lets someone who signed in with the wrong Google account retry.
        st.button("Đăng xuất / đổi tài khoản", on_click=st.logout,
                  use_container_width=True)
    st.stop()


def sidebar_account():
    """Small 'signed in as ... / log out' block. Safe to call when the gate
    is switched off — it renders nothing."""
    if not _auth_configured():
        return
    try:
        if not st.user.is_logged_in:
            return
        email = (getattr(st.user, "email", "") or "")
    except Exception:  # noqa: BLE001
        return
    with st.sidebar:
        st.caption(f"Đăng nhập: {email}")
        st.button("Đăng xuất", on_click=st.logout, use_container_width=True)
