# Roadmap

## Agreed decisions (2026-10-26)

- The default frame is the NED-style body frame (x forward, y right wing,
  z down). Other frames can be selected explicitly.
- NumPy is allowed as a runtime dependency, and array inputs are supported.
- Conversion to control-surface three-component loads is in scope: re-express
  coefficients given in the whole-vehicle reference quantities and basis in a
  control surface's reference quantities and basis (hinge-line frame). It is
  the general six-component reference-quantity and basis transformation with
  a convenience wrapper on top.

## Phases

### Phase 0: development infrastructure

- pytest and pytest-cov in the dev group, `py.typed`, GitHub Actions CI.
- `scripts/check.py` local gate, `AGENTS.md` repository instructions.

### Phase 1: data types and conventions

- ADR 0001: body, stability, and wind frames; positive alpha and beta; force
  and moment component names and signs; how alternative frames are specified.
- Coefficient types for forces and moments with explicit frame tags
  (`AeroCoefficients`, `ReferenceQuantities`).
- Frames from axis letters or rotation matrices (`Frame`).
- The shared validation boundary.
- Add the NumPy runtime dependency.

### Phase 2: frame transformations

- Angle inputs with explicit units (`alpha_rad`/`alpha_deg`).
- Body, stability, and wind frame transformations built from alpha and beta.
- Named quantities: `CA`, `CN`, `CD`, `CL`.
- Transformations to and from user-specified frames.
- Round-trip and reference-value tests.

### Phase 3: reference quantity and basis transformation

- Moment coefficient correction when the moment reference center moves.
- Re-normalization between reference areas and reference lengths
  (longitudinal chord, lateral-directional span).
- Rotation of the six components into an arbitrary basis.
- Combined general transformation: reference quantities and basis together.

### Phase 4: control-surface wrapper

- Build the target basis from a hinge line and the surface orientation, and the
  target reference quantities from the surface area and chord.
- Return the control surface's three components (component set and signs to be
  fixed by ADR) through the Phase 3 transformation, without new physics.

### Phase 5: dimensional and nondimensional conversion

- Forces and moments to and from coefficients via dynamic pressure, reference
  area, and reference lengths.

### Phase 6: documentation

- User documentation and examples.
- Releases are GitHub Releases with the wheel and sdist attached; see
  [Release](development/release.md). PyPI release is out of scope.
