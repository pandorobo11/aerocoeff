import importlib.resources
import importlib.util
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from aerocoeff.gui import launcher


def _site(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "index.html").write_text("<p>manual</p>", encoding="utf-8")
    return directory


@pytest.fixture
def no_manual(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.delenv(launcher.DOCS_DIR_ENV, raising=False)
    monkeypatch.setattr(launcher, "CHECKOUT_DOCS", tmp_path / "checkout")
    monkeypatch.setattr(importlib.resources, "files", lambda package: tmp_path / "package")
    return tmp_path


def test_documentation_directory_order(no_manual: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert launcher.documentation_directory() is None
    bundled = _site(no_manual / "package" / "_docs")
    assert launcher.documentation_directory() == bundled
    checkout = _site(no_manual / "checkout")
    assert launcher.documentation_directory() == checkout
    monkeypatch.setenv(launcher.DOCS_DIR_ENV, str(no_manual / "missing"))
    assert launcher.documentation_directory() == checkout
    configured = _site(no_manual / "configured")
    monkeypatch.setenv(launcher.DOCS_DIR_ENV, str(configured))
    assert launcher.documentation_directory() == configured.resolve()


def test_documentation_server_serves_on_loopback(tmp_path: Path) -> None:
    server, thread = launcher.start_documentation_server(_site(tmp_path))
    try:
        host, port = server.server_address[:2]
        assert host == launcher.LOOPBACK_ADDRESS
        with urllib.request.urlopen(f"http://{host}:{port}/index.html") as response:
            assert response.read() == b"<p>manual</p>"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)


def test_streamlit_command_binds_loopback_without_usage_statistics() -> None:
    command = launcher.streamlit_command(["--server.port=8600"])
    assert command[:5] == [sys.executable, "-m", "streamlit", "run", str(launcher.APP_PATH)]
    assert command[5:] == [
        "--server.address=127.0.0.1",
        "--browser.gatherUsageStats=false",
        "--client.toolbarMode=minimal",
        "--server.port=8600",
    ]
    assert launcher.APP_PATH.is_file()


def test_main_reports_a_missing_gui_extra(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    assert launcher.main([]) == 1
    assert "'gui' extra" in capsys.readouterr().err


def test_main_serves_the_manual_to_the_app(
    no_manual: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _site(no_manual / "checkout")
    calls: list[dict[str, Any]] = []

    def run(command: list[str], *, check: bool, env: dict[str, str]) -> Any:
        url = env[launcher.DOCS_URL_ENV]
        with urllib.request.urlopen(url + "index.html") as response:
            calls.append({"command": command, "page": response.read()})
        return subprocess.CompletedProcess(command, 3)

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(sys, "argv", ["aerocoeff-gui", "--server.port=8600"])
    assert launcher.main() == 3
    assert calls[0]["command"][-1] == "--server.port=8600"
    assert calls[0]["page"] == b"<p>manual</p>"


def test_main_without_a_manual_and_with_an_interrupt(
    no_manual: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def run(command: list[str], *, check: bool, env: dict[str, str]) -> Any:
        assert launcher.DOCS_URL_ENV not in env
        raise KeyboardInterrupt

    monkeypatch.delenv(launcher.DOCS_URL_ENV, raising=False)
    monkeypatch.setattr(subprocess, "run", run)
    assert launcher.main([]) == 130


def test_run_exits_with_the_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(launcher, "main", lambda: 7)
    with pytest.raises(SystemExit) as raised:
        launcher.run()
    assert raised.value.code == 7
