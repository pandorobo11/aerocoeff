"""Streamlit entry point of the GUI, started by ``aerocoeff-gui``."""

import streamlit as st

from aerocoeff.gui.documentation import render_documentation
from aerocoeff.gui.pages import (
    render_control_surface,
    render_loads,
    render_transform,
)

st.set_page_config(page_title="aerocoeff", layout="wide")
st.navigation(
    {
        "Calculations": [
            st.Page(render_transform, title="Transform", default=True),
            st.Page(render_control_surface, title="Control surface", url_path="control-surface"),
            st.Page(render_loads, title="Forces and moments", url_path="forces-and-moments"),
        ],
        "Help": [st.Page(render_documentation, title="Documentation", url_path="documentation")],
    }
).run()
