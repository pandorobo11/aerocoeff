"""Console entry point ``aerocoeff-gui``: serve the manual and run the Streamlit app."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import threading
from collections.abc import Sequence
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path

DOCS_URL_ENV = "AEROCOEFF_DOCS_URL"
"""Base URL of the served HTML manual, passed to the app."""
DOCS_DIR_ENV = "AEROCOEFF_DOCS_DIR"
"""Directory of a built HTML manual to serve instead of the bundled one."""
LOOPBACK_ADDRESS = "127.0.0.1"
APP_PATH = Path(__file__).with_name("app.py")
# src/aerocoeff/gui/launcher.py -> repository root, for a source checkout.
CHECKOUT_DOCS = Path(__file__).resolve().parents[3] / "docs" / "_build" / "html"


class _QuietHandler(SimpleHTTPRequestHandler):
    """Serve the manual without writing a log line per request."""

    def log_message(self, format: str, *args: object) -> None:
        pass


def _has_index(directory: Path) -> bool:
    return (directory / "index.html").is_file()


def documentation_directory() -> Path | None:
    """The configured, source-checkout, or bundled HTML manual, in that order."""
    configured = os.environ.get(DOCS_DIR_ENV)
    if configured and _has_index(Path(configured).expanduser()):
        return Path(configured).expanduser().resolve()
    if _has_index(CHECKOUT_DOCS):
        return CHECKOUT_DOCS
    bundled = Path(str(resources.files("aerocoeff").joinpath("_docs")))
    if _has_index(bundled):
        return bundled
    return None


def start_documentation_server(directory: Path) -> tuple[ThreadingHTTPServer, threading.Thread]:
    """Serve ``directory`` on a free loopback port in a daemon thread."""
    server = ThreadingHTTPServer(
        (LOOPBACK_ADDRESS, 0), partial(_QuietHandler, directory=str(directory))
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def streamlit_command(arguments: Sequence[str]) -> list[str]:
    """Run the app on the loopback address without usage statistics or the deploy
    button; extra arguments are passed to ``streamlit run``."""
    return [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(APP_PATH),
        f"--server.address={LOOPBACK_ADDRESS}",
        "--browser.gatherUsageStats=false",
        "--client.toolbarMode=minimal",
        *arguments,
    ]


def main(argv: Sequence[str] | None = None) -> int:
    """Start the manual server and the Streamlit app; return the app's exit code."""
    if importlib.util.find_spec("streamlit") is None:
        print(
            "The GUI needs the 'gui' extra; reinstall aerocoeff with it, for example "
            "pip install 'aerocoeff-<version>-py3-none-any.whl[gui]'.",
            file=sys.stderr,
        )
        return 1
    environment = dict(os.environ)
    server: ThreadingHTTPServer | None = None
    thread: threading.Thread | None = None
    directory = documentation_directory()
    if directory is not None:
        server, thread = start_documentation_server(directory)
        environment[DOCS_URL_ENV] = f"http://{LOOPBACK_ADDRESS}:{server.server_address[1]}/"
    command = streamlit_command(sys.argv[1:] if argv is None else argv)
    try:
        return subprocess.run(command, check=False, env=environment).returncode
    except KeyboardInterrupt:
        return 130
    finally:
        if server is not None and thread is not None:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2.0)


def run() -> None:
    """Console-script wrapper around :func:`main`."""
    raise SystemExit(main())
