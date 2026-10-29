"""Sphinx configuration for aerocoeff."""

import tomllib
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path


def _project_version() -> str:
    try:
        return package_version("aerocoeff")
    except PackageNotFoundError:
        pyproject = Path(__file__).parents[1] / "pyproject.toml"
        with pyproject.open("rb") as stream:
            project = tomllib.load(stream)["project"]
        return str(project["version"])


project = "aerocoeff"
copyright = "2026, aerocoeff contributors"
release = _project_version()
version = release

extensions = [
    "numpydoc",
    "sphinx.ext.autodoc",
    "sphinx.ext.doctest",
]
autodoc_member_order = "bysource"
numpydoc_show_class_members = False
nitpicky = True
# NumPy is not cross-referenced, so that the build needs no network access.
nitpick_ignore_regex = [("py:class", r"numpy\..*")]

html_theme = "pydata_sphinx_theme"
html_title = f"aerocoeff {release}"
html_theme_options = {
    "github_url": "https://github.com/pandorobo11/aerocoeff",
}

exclude_patterns = ["_build"]
