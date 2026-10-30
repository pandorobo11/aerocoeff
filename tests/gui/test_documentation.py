from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from aerocoeff.gui import documentation
from aerocoeff.gui.launcher import DOCS_URL_ENV

DOCS = Path(__file__).resolve().parents[2] / "docs"
SCRIPT = "from aerocoeff.gui.documentation import render_documentation\nrender_documentation()\n"


def test_base_url_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(DOCS_URL_ENV, raising=False)
    assert documentation.documentation_base_url() is None
    monkeypatch.setenv(DOCS_URL_ENV, "file:///tmp/docs")
    assert documentation.documentation_base_url() is None
    monkeypatch.setenv(DOCS_URL_ENV, " http://127.0.0.1:8123 ")
    assert documentation.documentation_base_url() == "http://127.0.0.1:8123/"


def test_topics_are_pages_of_the_manual() -> None:
    for page in documentation.TOPICS.values():
        assert (DOCS / page).with_suffix(".rst").is_file(), page
    assert (
        documentation.topic_url("Control-surface loads", "http://127.0.0.1:8123/")
        == "http://127.0.0.1:8123/guides/control_surface.html"
    )


def test_page_without_a_manual(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(DOCS_URL_ENV, raising=False)
    app = AppTest.from_string(SCRIPT).run()
    assert not app.exception
    assert "not found" in app.warning[0].value


def test_page_with_a_manual(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DOCS_URL_ENV, "http://127.0.0.1:8123/")
    app = AppTest.from_string(SCRIPT).run()
    assert not app.exception
    app.selectbox(key="documentation_topic").select("API reference").run()
    assert not app.exception
    assert app.selectbox(key="documentation_topic").value == "API reference"
