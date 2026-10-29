"""The manual inside the GUI, served by the launcher on the loopback address."""

from __future__ import annotations

import os
from urllib.parse import urljoin, urlsplit

import streamlit as st

from aerocoeff.gui.launcher import DOCS_URL_ENV

TOPICS = {
    "Home": "index.html",
    "Quickstart": "getting_started/quickstart.html",
    "Conventions": "getting_started/conventions.html",
    "Using the GUI": "guides/gui.html",
    "Coefficients and frames": "guides/coefficients_and_frames.html",
    "Moment reference and reference quantities": "guides/reference_transfer.html",
    "Control-surface loads": "guides/control_surface.html",
    "Forces and moments": "guides/loads.html",
    "Batches and validation": "guides/batches_and_validation.html",
    "API reference": "api/index.html",
}


def documentation_base_url() -> str | None:
    """The base URL from :data:`DOCS_URL_ENV`, or ``None`` if unset or not HTTP."""
    value = os.environ.get(DOCS_URL_ENV, "").strip()
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return value.rstrip("/") + "/"


def topic_url(topic: str, base_url: str) -> str:
    """The URL of one page of :data:`TOPICS`."""
    return urljoin(base_url, TOPICS[topic])


def render_documentation() -> None:
    """Show the manual, or explain how to build it when it was not found."""
    st.title("Documentation")
    base_url = documentation_base_url()
    if base_url is None:
        st.warning(
            "The HTML manual was not found. In a source checkout, build it and "
            "restart aerocoeff-gui:"
        )
        st.code("uv run --group docs sphinx-build -b html docs docs/_build/html", language="bash")
        return
    topic = st.selectbox("Page", tuple(TOPICS), key="documentation_topic") or "Home"
    url = topic_url(topic, base_url)
    st.link_button("Open in a new tab", url)
    st.iframe(url, height=900)
