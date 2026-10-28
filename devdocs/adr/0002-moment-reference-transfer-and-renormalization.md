# ADR 0002: Moment reference transfer and reference-quantity change

- Status: Accepted
- Date: 2026-10-28

## Context

Roadmap Phase 3 moves the moment reference point, replaces the reference area
and lengths, and combines both with the frame rotation of ADR 0001. The
control-surface wrapper (Phase 4) is this combination with a hinge-line frame,
a hinge point, and the surface's area and chord. The formulas are standard,
but the sign of the transfer term, the direction of the displacement, the frame
of the points, and the interaction with per-axis reference lengths must be
fixed before implementation.

## Decision

### Physical quantities

All three operations act on the coefficients scaled back to forces and moments
per unit dynamic pressure, which are independent of the reference quantities:

```text
F / q = S C_F                      (m^2),  C_F = (CX, CY, CZ)
M / q = S (l * C_M)                (m^3),  C_M = (Cl, Cm, Cn)
l = (l_roll, l_pitch, l_yaw),  * is element-wise
```

Each operation converts to these quantities, applies an exact physical
relation, and normalizes again. No approximation is made, so the operations
commute and chain exactly up to rounding.

### Moment reference transfer

For a force `F` and a moment `M_P` about point `P`, the moment about point `Q`
is

```text
M_Q = M_P + (r_P - r_Q) x F
```

In coefficients, with `d = r_P - r_Q` in meters in the coefficient frame:

```text
C_F unchanged
C_M,Q = (l * C_M,P + d x C_F) / l
```

The cross product uses the right-handed coefficient frame, so the result is
valid in any frame of ADR 0001. The force is unchanged, and the reference
quantities are unchanged.

Points follow ADR 0001: both points are given in one points frame, with a
shared arbitrary origin, in meters. The displacement is rotated into the
coefficient frame before use:

```text
d = R_coef<-body R_points<-body^T (r_P - r_Q)
```

The points frame is always given explicitly and has no default: points often
come from CAD or STL coordinates in `BRU`, and a body-frame default would
silently flip the x and z components of a forgotten `BRU` displacement. Points
have shape `(..., 3)` and broadcast with the coefficient batch.

Sign check (body frame, `l_pitch = 2 m`): a normal force `CN = 1` (`CZ = -1`)
acting at `P`, with `Q` 0.5 m aft of `P`, gives `d = (0.5, 0, 0)` and
`Delta Cm = (d_z CX - d_x CZ) / l_pitch = +0.25`: the force ahead of the new
point pitches the nose up. This is the familiar
`Cm_Q = Cm_P + CN (x_P - x_Q) / l_pitch` with x forward. The same points given
in `BRU` as `(0, 0, 0)` and `(0.5, 0, 0)` give the same result, because
`x_body = -x_BRU`.

### Reference-quantity change

From reference `(S, l)` to `(S', l')`, in the same frame and about the same
point:

```text
C_F' = C_F S / S'
C_M' = C_M * (S l) / (S' l')
```

Each length belongs to an axis position, as in ADR 0001: the x-axis moment is
renormalized from `l_roll` to `l_roll'`, and so on.

### Combined transformation

The general transformation takes a target frame, a target reference, and a
moment reference transfer, in any combination. It is defined as the
composition of the three operations above in physical quantities; because they
are exact, the order is irrelevant: transfer, then rotate, then renormalize
gives the same result as renormalize, then rotate, then transfer with the
rotated displacement.

Target reference lengths belong to the axis positions of the target frame. This
is what the control-surface wrapper needs: in a hinge-line frame the hinge
moment is divided by the length assigned to the hinge axis.

### Interface

- `AeroCoefficients` does not store its moment reference point. The transfer
  takes both points, `from_point_m` and `to_point_m`, plus `points_frame`.
- `with_reference(reference)` replaces the reference quantities.
- `transfer_moment_reference(*, from_point_m, to_point_m, points_frame)` moves
  the moment reference point; `points_frame` is required.
- `to_frame(frame)` rotates the basis (ADR 0001).
- `transform(*, frame=None, reference=None, from_point_m=None, to_point_m=None,
  points_frame=None)` applies any combination; the two points and
  `points_frame` are given together or not at all.

## Alternatives considered

- **Store the reference point in `AeroCoefficients`.** This prevents passing
  the wrong source point, but every entry point would need a point, a frame,
  and an origin, including for coefficients that are never moved, and a stored
  point could not be checked to share an origin with a point given later.
  Passing both points to one call keeps the ADR 0001 rule that points are used
  only in pairs. Rejected for now; an optional stored point can be added later
  without breaking the interface, whereas removing one could not.
- **Rotate or renormalize the coefficient triples directly.** Wrong whenever
  the reference lengths differ (ADR 0001 example); rejected.
- **A body-frame default for `points_frame`.** Consistent with the default
  coefficient frame, but most points are given in `BRU`, where a forgotten
  frame would flip signs without an error; rejected.
- **Points in units of reference length (for example `x/c`).** Ambiguous with
  per-axis lengths; points stay in meters.

## Review decisions

1. Coefficients do not store their moment reference point; the transfer takes
   both points.
2. `points_frame` is required, with no default, because points are usually in
   `BRU`.
3. The interface is `with_reference`, `transfer_moment_reference`, `to_frame`,
   and the combined `transform`.

## Consequences

- Phase 3 adds no new convention: signs and frames come from ADR 0001.
- The control-surface wrapper is the combined transformation with a hinge
  frame, a hinge point, and the surface reference; its component set and signs
  remain for a later ADR.
- Lateral moments appear whenever the displacement has a lateral component or
  the frame leaves the longitudinal plane; the longitudinal outputs of Phase 2
  then raise instead of dropping them.

## Verification

Before acceptance, a numerical check over 1000 random cases (coefficients,
areas, per-axis lengths, points, and rotations) confirmed that the combined
transformation equals the dimensional calculation with `q = 1234.5 Pa` to
`1e-12`, that both operation orders agree, and that transferring from `P` to `Q`
and back restores the moments. Hand values:

| Case | Result |
|---|---|
| `CZ = -1`, `l_pitch = 2`, `Q` 0.5 m aft of `P` | `Delta Cm = +0.25` |
| Same points in `BRU` | `Delta Cm = +0.25` |
| `CZ = -1`, `l_roll = 10`, `Q` 1 m right of `P` | `Delta Cl = +0.1` (right wing down) |
| `S: 2 -> 4`, `l_pitch: 2 -> 0.5`, `CX = 1`, `Cm = 1` | `CX' = 0.5`, `Cm' = 2` |

## References

- J. D. Anderson, *Fundamentals of Aerodynamics*, 6th ed., McGraw-Hill, 2017,
  Sec. 1.6: transfer of the moment between reference points.
- B. Etkin and L. D. Reid, *Dynamics of Flight: Stability and Control*, 3rd
  ed., Wiley, 1996: moment about the center of gravity from aerodynamic-center
  data.
- ADR 0001: frames, signs, per-axis reference lengths, and points.
