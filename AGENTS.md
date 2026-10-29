# Repository instructions

## Purpose and priorities

`aerocoeff` transforms aerodynamic coefficients between reference frames,
moment reference points, and dimensional/nondimensional forms. Apply these
priorities in order:

1. numerical correctness;
2. public API compatibility;
3. maintainability;
4. performance;
5. reduced code volume.

Never change numerical behavior or a public contract merely to remove duplicate
code.

## Read before editing

1. `devdocs/README.md`;
2. `devdocs/roadmap.md` for the current phase and agreed scope;
3. relevant ADRs in `devdocs/adr/`;
4. the current issue or task.

## Numerical rules

- Use SI internally.
- Make degree versus radian explicit in names or types, such as `alpha_rad`
  and `alpha_deg`.
- The default frame is the NED-style body frame: x forward, y toward the right
  wing, z down. Other frames must be selected explicitly; never infer a frame
  from data.
- Make coordinate frames explicit in names with suffixes such as `_body`,
  `_stability`, and `_wind`.
- Store 3-vectors as NumPy arrays of shape `(..., 3)` and validate shapes where
  broadcasting is used.
- Reject NaN, infinity, booleans used as numbers, invalid shapes, and zero or
  negative reference quantities at a shared validation boundary.
- Do not change signs, axes, angle definitions, or normalization conventions
  without an accepted ADR.
- Never mix a numerical-formula change with a structural refactoring.

## Tests and reference values

- Every transformation needs a round-trip test (forward then inverse) and at
  least one hand-checkable reference value.
- Cite the source (textbook, standard, or derivation) of every reference value
  in the test.
- Do not update expected values to make tests pass. Document the intended
  change, its evidence, and the tolerance instead.

## Dependencies

NumPy is the only intended runtime dependency. Explain every new production
dependency in the pull request.

## Change discipline

- Keep one issue to one independently reviewable change.
- Edit only the files needed for the task.
- Do not include unrelated cleanup, renaming, or formatting.
- Do not push directly to `main`, rewrite history, or merge on behalf of the user
  unless explicitly requested.
- If code, tests, literature, and ADRs disagree about a sign or convention, stop
  and report the conflict instead of choosing one silently.

## Verification

```bash
python scripts/check.py --quick  # during development
python scripts/check.py          # before push or pull request
```

Each mode begins with `uv sync --locked --group docs` and stops at the first
failure. Quick runs Ruff format and lint, mypy (strict) over `src`, `tests`, and
`scripts`, pytest, and the Sphinx doctest build of `docs/`. The default standard
mode runs pytest with coverage, the Sphinx HTML and doctest builds, and the
distribution build instead of the plain pytest step. Sphinx treats warnings as
errors.

## Completion report

Report changed files, implemented behavior, design choices, checks and results,
numeric differences, compatibility impact, remaining risks, and follow-up work.

## Review priorities

Review formulas, units, signs, coordinate frames, angle definitions,
shapes/broadcasting, input validation, and missing reference or round-trip
coverage before style concerns.
