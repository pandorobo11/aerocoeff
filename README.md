# aerocoeff

`aerocoeff` is a Python package for aerodynamic coefficient transformations:

- frame changes between body, stability, wind, and user-specified frames;
- moment reference transfer and reference-quantity changes, with per-axis
  reference lengths;
- control-surface normal force, hinge moment, and root bending moment;
- conversion between coefficients and forces and moments in N and N m.

Frames, signs, and angle units are always explicit. The default frame is the
body frame (x forward, y toward the right wing, z down), and NumPy is the only
runtime dependency.

## Installation

The package is not on PyPI; install it from GitHub:

```bash
uv add "aerocoeff @ git+https://github.com/pandorobo11/aerocoeff"
```

This installs the latest `main`. To pin a version published on
[GitHub Releases](https://github.com/pandorobo11/aerocoeff/releases), append its
tag, for example `...aerocoeff@v0.1.0`.

## Documentation

The manual is built with Sphinx from `docs/`:

- [Quickstart](docs/getting_started/quickstart.rst)
- [Conventions](docs/getting_started/conventions.rst): frames, angles,
  component names and signs, per-axis reference lengths, and points.
- [Guides](docs/guides/index.rst): every operation with worked examples.
- [Architecture decision records](devdocs/adr/README.md): the full definitions.

To read it as a website, with the API reference and search, build it from a
checkout and open `docs/_build/html/index.html` in a browser; no server or
network access is needed:

```bash
uv run --group docs sphinx-build -b html docs docs/_build/html
```

## Development

The package is managed with [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

```bash
python scripts/check.py --quick  # during development
python scripts/check.py          # before push or pull request
```

Contributor and agent instructions are in [AGENTS.md](AGENTS.md); the plan is
in [devdocs/roadmap.md](devdocs/roadmap.md).

## License

Licensed under the [Apache License 2.0](LICENSE).
