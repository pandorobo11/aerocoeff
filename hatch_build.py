"""Hatch build hook that bundles the HTML manual in the wheel as ``aerocoeff/_docs``."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from importlib.metadata import distribution
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

# Distributions whose files are copied into the manual (CSS, JavaScript, fonts).
# Bootstrap and Font Awesome ship their notices in _static/scripts/*.LICENSE.txt.
BUNDLED_DISTRIBUTIONS = ("sphinx", "pydata-sphinx-theme")


def copy_licenses(target: Path) -> None:
    """Copy the license files of :data:`BUNDLED_DISTRIBUTIONS` into ``target``."""
    target.mkdir()
    for name in BUNDLED_DISTRIBUTIONS:
        installed = distribution(name)
        licenses = [
            file
            for file in installed.files or ()
            if ".dist-info" in file.parts[0] and file.name.upper().startswith(("LICENSE", "COPYING"))
        ]
        if not licenses:
            raise RuntimeError(f"no license file found for {name}")
        for file in licenses:
            shutil.copyfile(
                Path(str(installed.locate_file(file))),
                target / f"{name}-{installed.version}-{file.name}",
            )


class CustomBuildHook(BuildHookInterface):  # type: ignore[type-arg]
    """Build the Sphinx manual from a copy of the sources before the wheel is assembled."""

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        if self.target_name != "wheel" or version == "editable":
            return
        root = Path(self.root)
        sources = TemporaryDirectory(prefix="aerocoeff-docs-source-")
        output = TemporaryDirectory(prefix="aerocoeff-docs-")
        try:
            copy = Path(sources.name)
            shutil.copytree(root / "docs", copy / "docs", ignore=shutil.ignore_patterns("_build"))
            shutil.copytree(root / "src", copy / "src")
            shutil.copy2(root / "pyproject.toml", copy / "pyproject.toml")
            environment = dict(os.environ)
            environment["PYTHONPATH"] = os.pathsep.join(
                filter(None, [str(copy / "src"), environment.get("PYTHONPATH")])
            )
            command = [sys.executable, "-m", "sphinx", "-W", "--keep-going", "-q", "-b", "html"]
            subprocess.run(
                [*command, str(copy / "docs"), output.name], cwd=copy, env=environment, check=True
            )
            copy_licenses(Path(output.name) / "_licenses")
        except BaseException:
            sources.cleanup()
            output.cleanup()
            raise
        self._temporary = (sources, output)
        build_data["force_include"][output.name] = "aerocoeff/_docs"

    def finalize(self, version: str, build_data: dict[str, Any], artifact_path: str) -> None:
        for directory in getattr(self, "_temporary", ()):
            directory.cleanup()
