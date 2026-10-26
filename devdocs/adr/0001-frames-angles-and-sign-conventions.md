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
frame named in their suffix, positive along each axis. Named quantities, all in
body or stability axes as in panelsolver:

| Quantity | Definition |
|---|---|
| Axial force `CA` | `-CX_body` |
| Normal force `CN` | `-CZ_body` |
| Side force `CY` | `CY_body` (equal to `CY_stability`) |
| Drag `CD` | `-CX_stability` |
| Lift `CL` | `-CZ_stability` (equal to `-CZ_wind`) |

Because `y_stability = y_body`, the side force has one definition and no sign
ambiguity. Wind-axis components remain available as `CX_wind`, `CY_wind`, and
`CZ_wind` without other names; the force component opposite the velocity is
`-CX_wind = cos(beta) CD - sin(beta) CY`, which differs from `CD` when beta is
nonzero.

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

## Review decisions

1. `CD` and `CL` are stability-axis coefficients, matching panelsolver.
2. No crosswind-force name is defined; the side force is `CY_body`.
3. Frames are selected with the F/B, R/L, D/U axis letters or a rotation matrix.

## Open decision: positions

Proposed rule. Points such as moment reference points are positions, not
coefficient components, and carry their own frame, independent of the frame of
the coefficients. Every point passed to one operation is expressed in the same
frame orientation with a shared, otherwise arbitrary origin (for example the
CAD/STL origin in `BRU`), in meters. Only differences of points are used, so
the origin never needs to be stated: a displacement is rotated into the
coefficient frame like any other vector, `dr_body = R_body<-points @ (r_to - r_from)`.

For example, six components in `FRD` can have their moment reference moved
between two points given in `BRU` STL coordinates. Points in different
coordinate systems, with different origins, are outside this record.

## Consequences

- panelsolver results map directly: its `beta_sin` attitude gives the same
  alpha and beta as this record, its STL frame is `BRU`, and its `CA`, `CY`,
  `CN`, `CD`, `CL`, `Cl`, `Cm`, `Cn`, and per-axis reference lengths match the
  definitions above.
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
and `-CZ_stability`; and the `-CX_wind` relation in the force section holds.

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
