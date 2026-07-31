"""
Optional passkey gate for the whole app.

Design: off by default (local dev / AppTest never need a key). The gate only
activates once at least one key exists in ``st.secrets["access_keys"]`` —
that's the single switch for "this deployment is being sold" vs. "this is my
own free instance". Unlock state persists in the browser (localStorage, same
component/pattern as core/progress.py) so a returning buyer doesn't have to
retype their key every visit; only a boolean flag is stored client-side, never
the key itself.

Keys are a flat list, one per buyer, so a leaked/refunded key can be revoked
by deleting just that line from the Secrets UI on Streamlit Cloud — no
shared password, no accounts, no backend.
"""
import streamlit as st

_KEY = "cfa_access_v1"


def _valid_keys():
    try:
        keys = st.secrets.get("access_keys", [])
    except Exception:  # noqa: BLE001 — no secrets.toml at all locally
        keys = []
    if isinstance(keys, str):
        keys = [keys]
    return {str(k).strip() for k in keys if str(k).strip()}


def _local_storage():
    if "_access_ls" in st.session_state:
        return st.session_state["_access_ls"]
    ls = None
    try:
        from streamlit_local_storage import LocalStorage
        ls = LocalStorage()
    except Exception:  # noqa: BLE001 — component optional
        ls = None
    st.session_state["_access_ls"] = ls
    return ls


def require_access():
    """Block the rest of the script (st.stop()) until a valid key is entered.
    No-op if no keys are configured in secrets."""
    valid = _valid_keys()
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
        "Nhập mã truy cập để tiếp tục</p>",
        unsafe_allow_html=True,
    )
    _, col, _ = st.columns([1, 2, 1])
    with col:
        with st.form("access_form"):
            key_input = st.text_input(
                "Mã truy cập", type="password",
                label_visibility="collapsed", placeholder="Mã truy cập...",
            )
            submitted = st.form_submit_button(
                "Mở khóa", use_container_width=True, type="primary",
            )
        if submitted:
            if key_input.strip() in valid:
                st.session_state["_unlocked"] = True
                if ls is not None:
                    try:
                        ls.setItem(_KEY, "1", key="cfa_access_writer")
                    except Exception:  # noqa: BLE001
                        pass
                st.rerun()
            else:
                st.error("Mã truy cập không đúng.")
    st.stop()
