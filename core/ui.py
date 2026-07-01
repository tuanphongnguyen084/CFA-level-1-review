"""Shared UI helpers: CSS, navigation, question rendering, sidebar."""
import html as _html
import json

import streamlit as st

from core import progress

_CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  :root {
    --sp-green: #1ed760;
    --sp-green-hover: #1fdf64;
    --sp-bg: #121212;
    --sp-surface: #181818;
    --sp-surface-2: #282828;
    --sp-text: #ffffff;
    --sp-text-2: #b3b3b3;
    --sp-border: #7c7c7c;
  }
  html, body, [class*="css"], [class*="st-"], .stMarkdown, .stRadio,
  .stButton button, button, input, textarea, select {
      font-family: 'Inter', -apple-system, "Segoe UI", Roboto,
                   Helvetica, Arial, sans-serif !important;
      -webkit-font-smoothing: antialiased;
  }
  /* Keep Streamlit's Material icons as glyphs — the Inter override above
     would otherwise show ligature names ("expand_more") as literal text. */
  [data-testid="stIconMaterial"] {
      font-family: 'Material Symbols Rounded' !important;
  }
  .block-container { max-width: 900px; padding-top: 2rem; }
  header[data-testid="stHeader"] { display: none !important; }
  #MainMenu { visibility: hidden; }
  footer { visibility: hidden; }

  /* Sidebar always open: force it visible regardless of collapsed state,
     and hide the collapse (<<) button entirely. */
  section[data-testid="stSidebar"] {
      transform: none !important;
      visibility: visible !important;
      margin-left: 0 !important;
      min-width: 250px !important;
      width: 250px !important;
  }
  section[data-testid="stSidebar"][aria-expanded="false"] {
      transform: none !important;
      margin-left: 0 !important;
  }
  [data-testid="stSidebarCollapseButton"],
  [data-testid="stSidebarCollapsedControl"] { display: none !important; }

  /* Typography — bold/regular binary, tight, white on dark */
  h1, h2, h3, h4 {
      color: var(--sp-text) !important;
      font-weight: 700 !important;
      letter-spacing: -0.02em;
  }
  h1 { font-size: 2rem !important; }
  [data-testid="stCaptionContainer"] { color: var(--sp-text-2) !important; }

  /* Buttons — pill (theme.buttonRadius=full), UPPERCASE, scale-on-hover */
  .stButton > button, .stDownloadButton > button {
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      font-size: 0.8rem;
      padding: 0.55rem 1.4rem;
      transition: transform .1s ease, background .2s ease,
                  color .2s ease, border-color .2s ease;
  }
  .stButton > button[kind="primary"], .stDownloadButton > button {
      background: var(--sp-green) !important;
      color: #000000 !important;
      border: none !important;
  }
  .stButton > button[kind="primary"]:hover,
  .stDownloadButton > button:hover {
      background: var(--sp-green-hover) !important;
      color: #000 !important;
      transform: scale(1.04);
  }
  .stButton > button[kind="secondary"] {
      background: transparent !important;
      color: var(--sp-text) !important;
      border: 1px solid var(--sp-border) !important;
  }
  .stButton > button[kind="secondary"]:hover {
      border-color: #ffffff !important;
      color: #fff !important;
      transform: scale(1.04);
  }

  /* List rows / column blocks — Spotify track-list hover highlight */
  [data-testid="stHorizontalBlock"] {
      border-radius: 8px;
      padding: 6px 10px;
      transition: background .2s ease;
  }
  [data-testid="stHorizontalBlock"]:hover {
      background: rgba(255, 255, 255, 0.06);
  }

  /* Question card — dark surface, heavy shadow */
  .q-card {
      background: var(--sp-surface);
      border: none;
      border-radius: 8px;
      padding: 30px 34px;
      margin: 12px auto 24px auto;
      text-align: center;
      font-size: 1.2rem;
      line-height: 1.5;
      color: var(--sp-text);
      box-shadow: rgba(0, 0, 0, 0.4) 0px 8px 24px;
  }
  .q-card .q-no {
      display: block;
      font-size: .75rem;
      letter-spacing: .16em;
      text-transform: uppercase;
      color: var(--sp-text-2);
      margin-bottom: 10px;
  }
  .stRadio > label { font-weight: 700; }
  div[role="radiogroup"] label {
      font-size: 1rem; line-height: 1.4; color: var(--sp-text);
  }
</style>
"""


def inject_css():
    st.markdown(_CSS, unsafe_allow_html=True)


def md(text):
    """Escape chars that make Streamlit mis-render text as LaTeX ($...$) —
    money amounts like $8,000 are common in CFA questions."""
    return str(text).replace("\\", "\\\\").replace("$", "\\$")


def render_question(no_text, body):
    safe = _html.escape(str(body)).replace("$", "&#36;")
    st.markdown(
        f'<div class="q-card"><span class="q-no">{no_text}</span>{safe}</div>',
        unsafe_allow_html=True,
    )


def go(view, **kwargs):
    """Switch view and stash any extra state, then rerun."""
    st.session_state.view = view
    for k, v in kwargs.items():
        st.session_state[k] = v
    st.rerun()


def sidebar(library):
    with st.sidebar:
        st.download_button(
            "Download progress",
            data=json.dumps(st.session_state.get("progress", {}),
                            ensure_ascii=False, indent=2),
            file_name="cfa_progress.json",
            mime="application/json",
            use_container_width=True,
        )

        up = st.file_uploader("Upload progress file",
                              label_visibility="collapsed")
        if up is not None:
            uid = getattr(up, "file_id", up.name)
            if st.session_state.get("_imported") != uid:
                try:
                    if not up.name.lower().endswith(".json"):
                        raise ValueError("Please upload a .json file.")
                    progress.load_from_dict(json.load(up))
                    st.session_state["_imported"] = uid
                    st.success("Progress loaded.")
                except Exception as e:  # noqa: BLE001
                    st.error(f"Invalid file: {e}")

        with st.popover("Clear all progress", use_container_width=True):
            st.write("Clear all progress in this browser?")
            if st.button("Clear", type="primary"):
                progress.reset()
                go("home")

        if library.errors:
            st.divider()
            with st.expander(f"{len(library.errors)} data issue(s)"):
                import os
                for path, msg in library.errors:
                    st.caption(f"`{os.path.basename(path)}` — {msg}")
