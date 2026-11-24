"""Portfolio Project Generator — four-screen Streamlit app."""

import streamlit as st

st.set_page_config(
    page_title="Portfolio Project Generator",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)

pages = [
    st.Page("ui/page_role.py", title="Role and profile", default=True),
    st.Page("ui/page_ideas.py", title="Method and ideas"),
    st.Page("ui/page_brief.py", title="Brief and review"),
    st.Page("ui/page_export.py", title="Export"),
]
st.navigation(pages, position="hidden").run()
