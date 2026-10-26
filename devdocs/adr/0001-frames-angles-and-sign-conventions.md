# ADR 0001: Frames, aerodynamic angles, and sign conventions

- Status: Proposed
- Date: 2026-10-26

## Context

Every later transformation (frame rotation, moment reference transfer,
reference-quantity changes, the control-surface wrapper) depends on one set of
axis, angle, and sign definitions. Published conventions differ in drag
(stability versus wind axes), side-force sign, and frame handedness, and the
sibling project panelsolver already exports body-axis and stability-axis
coefficients. This record fixes the conventions before any numerical code is
written.

## Decision

### Frames

All frames are right-handed and share the moment reference point as origin.
Frames describe axis orientation only; moving the reference point is a
separate operation.

| Frame | Axes |
|---|---|
| Body (default) | x forward, y toward the right wing, z down (FRD) |
| Stability | body rotated about y_body by alpha; y_stability = y_body |
| Wind | stability rotated about z_stability by beta; x_wind along the vehicle velocity relative to the air; z_wind = z_stability |

Other frames are selected explicitly in one of two ways:

1. **Axis letters**: three letters naming the body direction of the frame's x,
   y, and z axes, one from each pair F/B (forward/back), R/L (right/left wing),
   D/U (down/up), in any order. `FRD` is the body frame. The panelsolver STL
   frame is `BRU`.
2. **Rotation matrix**: a 3x3 matrix `R` with `v_frame = R @ v_body`.

Left-handed frames are rejected, because moments are pseudovectors and would
change sign. A matrix is accepted only if it is orthonormal with determinant +1
within a documented absolute tolerance; it is never re-orthonormalized
silently.

### Aerodynamic angles

With the vehicle velocity relative to the air in body axes
`V_body = (u, v, w)` and `V = |V_body|`:

```text
alpha = atan2(w, u)        in (-pi, pi]
beta  = asin(v / V)        in [-pi/2, pi/2]
V_body = V (cos(alpha) cos(beta), sin(beta), sin(alpha) cos(beta))
```

Positive alpha is nose up relative to the flow; positive beta is relative wind
from the right. The freestream (air relative to the vehicle) is `-V_body`.

Direction cosine matrices, with `c = cos`, `s = sin`:

```text
C_stability<-body = [[ c(a), 0, s(a)],
                     [    0, 1,    0],
                     [-s(a), 0, c(a)]]

C_wind<-stability = [[ c(b), s(b), 0],
                     [-s(b), c(b), 0],
                     [    0,    0, 1]]

C_wind<-body = [[ c(a)c(b),  s(b),  s(a)c(b)],
                [-c(a)s(b),  c(b), -s(a)s(b)],
                [    -s(a),     0,      c(a)]]
```

Transformation functions accept any finite alpha and beta. Deriving angles from
a velocity vector, including the singular case u = w = 0, is outside this
record.

Public names carry the angle unit: `alpha_rad`, `alpha_deg`, `beta_rad`,
`beta_deg`.

### Force coefficients

`(CX, CY, CZ)` are the aerodynamic force components along the axes of the
frame named in their suffix, positive along each axis. Named body-axis and
wind-axis quantities:

| Quantity | Definition |
|---|---|
| Axial force `CA` | `-CX_body` |
| Normal force `CN` | `-CZ_body` |
| Body side force `CY` | `CY_body` |
| Drag `CD` | `-CX_wind` |
| Lift `CL` | `-CZ_wind` (equal to `-CZ_stability`) |
| Wind-axis side force | `CY_wind`, positive along +y_wind |

Some texts define a crosswind force with the opposite sign of `CY_wind`; it is
not provided under another name.

### Moment coefficients

`(Cl, Cm, Cn)` are the roll, pitch, and yaw moment components about the x, y,
and z axes of the named frame, positive by the right-hand rule: in the body
frame, right wing down, nose up, and nose right.

Each axis has its own reference length, as in panelsolver:
`Cl = L / (q S l_roll)`, `Cm = M / (q S l_pitch)`, `Cn = N / (q S l_yaw)`.
Conventionally `l_roll = l_yaw = b` and `l_pitch = c`.

Moment coefficients are rotated as the length-scaled vector
`(Cl l_roll, Cm l_pitch, Cn l_yaw)` and renormalized afterwards. Rotating the
coefficient triple directly is wrong whenever the reference lengths differ:
with `l_roll = 10`, `l_pitch = 2`, `Cm_body = 0.1`, and beta = 10 deg, the
correct `Cl_wind` is 0.00347, while rotating the raw triple gives 0.01736.

## Open decisions

1. **Drag axis.** This record defines `CD` in wind axes (`-CX_wind`). panelsolver
   reports `CD` in stability axes (`-CX_stability`); the two differ when beta is
   nonzero: `CD_wind = cos(beta) CD_stability - sin(beta) CY_body`. Options:
   keep wind-axis `CD` and also offer `CD_stability`, or follow panelsolver.
2. **Side force in wind axes.** Keep `CY_wind` only, or also offer the crosswind
   force with the opposite sign.
3. **Axis-letter notation.** Confirm the F/B, R/L, D/U letters for selecting
   frames.

## Consequences

- panelsolver results map directly: its `beta_sin` attitude gives the same
  alpha and beta as this record, its STL frame is `BRU`, and its `CA`, `CY`,
  `CN`, `Cl`, `Cm`, `Cn`, and per-axis reference lengths match the body-axis
  definitions above. Its `CL` equals `CL` here; its `CD` is `CD_stability`.
- The control-surface wrapper builds its basis as a rotation matrix relative to
  the body frame and reuses these rules.
- Any later change to a sign, axis, or angle definition requires a superseding
  ADR.

## Verification

Before acceptance, a numerical check over 1000 random (alpha, beta) pairs
confirmed: the closed-form `C_wind<-body` equals the product of the two
rotations; it maps `V_body` to `+x_wind`; alpha and beta are recovered from
`V_body`; panelsolver's `beta_sin` freestream, mapped from `BRU` to body axes,
equals `-V_body`; panelsolver's `CD` and `CL` formulas equal `-CX_stability`
and `-CZ_stability`; and the `CD_wind` relation in open decision 1 holds.

## References

- B. L. Stevens, F. L. Lewis, and E. N. Johnson, *Aircraft Control and
  Simulation*, 3rd ed., Wiley, 2016: body, stability, and wind frames; alpha and
  beta definitions.
- B. Etkin and L. D. Reid, *Dynamics of Flight: Stability and Control*, 3rd
  ed., Wiley, 1996: axis systems and moment sign conventions.
- ANSI/AIAA R-004-1992, *Recommended Practice: Atmospheric and Space Flight
  Vehicle Coordinate Systems*.
- panelsolver documentation: *Coordinate and attitude conventions* and *Load
  and coefficient conventions*.
