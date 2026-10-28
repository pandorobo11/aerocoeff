# ADR 0003: Control-surface frame and three-component loads

- Status: Accepted
- Date: 2026-10-28

## Context

Roadmap Phase 4 re-expresses the load on a control surface, given as
six-component coefficients in the vehicle frame and vehicle reference
quantities about the vehicle moment reference point, as the surface's own
three components. ADR 0002 already provides the transformation; this record
fixes how the hinge frame is built from geometry, which three components are
returned, and their signs.

The input must be the load on the surface alone (for example panelsolver
coefficients integrated over the surface panels). Separating the surface load
from the vehicle load, and local dynamic pressure, are outside this record: the
surface coefficients use the same freestream dynamic pressure.

## Decision

### Hinge frame

The surface is described in a points frame (required, as in ADR 0002), in
meters, by:

- `hinge_start_m`, `hinge_end_m`: two points on the hinge line. The hinge axis
  points from start to end, and `hinge_start_m` is the moment reference point
  of the surface loads (normally the root end of the hinge line).
- `trailing_edge_direction`: a direction from the hinge line toward the
  trailing edge of the undeflected surface, in the points frame; its length is
  irrelevant. Together with the hinge axis it fixes the plane of the
  undeflected surface. Only its component perpendicular to the hinge axis is
  used, so a swept hinge line needs no special handling. It is rejected if its
  perpendicular part is shorter than `1e-6` times its length (nearly parallel
  to the hinge axis), as is a zero-length hinge line.

Typical inputs in `BRU` (x back, y right, z up):

| Surface | `hinge_start_m` → `hinge_end_m` | `trailing_edge_direction` |
|---|---|---|
| Right horizontal tail | root → tip (outboard, +y) | `(1, 0, 0)`: straight back |
| Same, with sweep or dihedral | root → tip along the swept or tilted hinge | `(1, 0, 0)` still works when the undeflected chord lies along the body x axis |
| Surface with incidence or twist | root → tip | trailing-edge point minus a hinge point, from CAD |
| Vertical fin | root → tip (up, +z) | `(1, 0, 0)` |

`(1, 0, 0)` in `BRU` is enough whenever the undeflected chord is parallel to the
body x axis, because dihedral and sweep only tilt the hinge axis and the
projection removes the along-hinge part. When the chord is inclined to the body
x axis (incidence), give the actual chord direction, for example a
trailing-edge point minus a hinge point.

The hinge frame is right-handed:

```text
y_h = unit(hinge_end - hinge_start)                    hinge axis
x0  = unit(t - (t . y_h) y_h),  t = trailing_edge_direction
z0  = x0 x y_h                                         undeflected normal
x_h = cos(delta) x0 - sin(delta) z0                    deflected chord
z_h = sin(delta) x0 + cos(delta) z0                    deflected normal
```

The deflection `delta` is a right-hand rotation of the surface about `y_h`, the
same sense as a positive hinge moment: positive `delta` moves the trailing
edge toward `-z0`. It is given on every call as exactly one of
`deflection_rad` and `deflection_deg`, with no default, so a forgotten
deflection is never read as zero; it broadcasts with the coefficient batch. The hinge line, and therefore `y_h` and the moment
reference point, do not move with the deflection.

Its rotation is assembled in body axes and used as a `Frame` named `"hinge"`
with kind `"custom"`. For a right horizontal tail with the hinge axis pointing
outboard and the trailing edge aft, `x_h` is aft, `y_h` is right, and `z_h` is
up.

### Three components

The surface loads are `transform(frame=hinge, reference=surface_reference,
from_point_m=vehicle_moment_reference_m, to_point_m=hinge_start_m,
points_frame=...)` (ADR 0002). From them:

| Component | Definition | Normalization |
|---|---|---|
| Normal force `CN_s` | `CZ_h`, positive along `z_h` | `q S_s` |
| Hinge moment `Ch` | `Cm_h`, right-hand rule about `y_h` | `q S_s l_hinge` |
| Root bending moment `CB` | `Cl_h`, right-hand rule about `x_h` through `hinge_start_m` | `q S_s l_bending` |

The surface reference is given with names tied to these components, not to a
particular geometric length: `area_m2` (`S_s`), `hinge_moment_length_m`
(`l_hinge`, often the surface chord), and `bending_moment_length_m`
(`l_bending`, often the surface span). Internally they fill the axis positions
of ADR 0001 in the hinge frame: x (`l_roll`) is `l_bending`, y (`l_pitch`) is
`l_hinge`, and z (`l_yaw`), used only for `Cn_h`, is
`normal_moment_length_m`, which defaults to `l_bending`.

With the right horizontal tail above, these match the usual convention
(NACA): a positive deflection moves the trailing edge down, a positive normal
force is up, a positive hinge moment tends to deflect the trailing edge down,
and a positive bending moment comes from a positive normal force outboard of
the root. `Ch` does not depend on the deflection, because `y_h` does not;
`CN_s` and `CB` are taken in the deflected axes. The sign of every component
follows the hinge-axis direction chosen by the user: reversing the two hinge
points reverses `y_h` and `z_h`, and therefore `CN_s` and `Ch`. On a left
surface, a hinge axis pointing outboard gives `z_h` down; a hinge axis pointing
to the right on both sides gives the same signs on both sides.

The full six components in the hinge frame remain available; the chordwise
force `CX_h` and the moment about the normal `Cn_h` have no names here.

### Interface

All arguments are keyword-only. Geometry is a single surface: points and
direction have shape `(3,)`, and `points_frame` has no batch.

```python
surface = ControlSurface(
    hinge_start_m=..., hinge_end_m=..., trailing_edge_direction=...,
    points_frame=Frame.from_axes("BRU"),
    area_m2=..., hinge_moment_length_m=..., bending_moment_length_m=...,
)
surface.reference                               # ReferenceQuantities in hinge axis positions
surface.frame(deflection_deg=...)               # the hinge Frame
surface.loads(coefficients, moment_reference_m=..., deflection_deg=...)  # AeroCoefficients
surface.three_components_array(coefficients, moment_reference_m=..., deflection_deg=...)
                                                # (..., 3): CN_s, Ch, CB
```

`moment_reference_m` is the vehicle moment reference point of the input
coefficients, in the surface's points frame. Geometry and reference belong to
the surface; the deflection belongs to each call, because it changes from case
to case.

## Review decisions

1. The three components are the normal force, the hinge moment, and the root
   bending moment.
2. Signs follow the hinge-axis direction chosen by the user.
3. The deflection is a required angle parameter of each call.
4. Surface reference lengths are named after the components, not after span
   and chord.
5. `normal_moment_length_m` defaults to `bending_moment_length_m`: `Cn_h` is
   the in-plane root bending moment (chordwise force times spanwise distance),
   the same kind of quantity as `CB`.

## Alternatives considered

- **Components `CN_s`, `CC_s` (chordwise force), `Ch`.** Common for
  two-dimensional sections, but the root bending moment is usually needed for
  structural sizing of a three-dimensional surface.
- **Fixed hinge-moment sign independent of the axis direction** (for example
  always trailing edge down). Not defined for vertical or canted surfaces
  without another reference direction; the axis direction makes the choice
  explicit instead.
- **Deflection only through a deflected trailing-edge direction.** Simpler,
  but every case would need its own geometry; rejected in review.
- **`ReferenceQuantities.from_span_chord` for the surface.** The hinge-moment
  and bending-moment lengths are not always the chord and span; rejected in
  review in favor of component-named lengths.
- **Surface normal as input instead of the trailing-edge direction.** The normal
  must then be exactly perpendicular to the hinge line, which CAD values rarely
  are; the trailing-edge direction can be projected without changing meaning.

## Consequences

- No new physics: the wrapper only builds a frame and a reference and calls the
  ADR 0002 transformation.
- Coefficients from several surfaces in one array can share a vehicle
  reference point but each needs its own `ControlSurface`.

## Verification

Before acceptance, a prototype checked a right horizontal tail with the hinge
from `(-5, 0.2, 0)` to `(-5, 1.2, 0)` m (body), the trailing edge aft, vehicle
reference `S = 2`, `l = (10, 2, 10)`, surface `S_s = 0.2`, `c_s = 0.25`,
`b_s = 1.0`, and an upward force `CZ = -0.01` acting 0.1 m aft of the hinge and
0.5 m outboard of the root:

| Component | Hand calculation | Prototype |
|---|---|---|
| `CN_s` | `0.01 * 2 / 0.2 = 0.1` | 0.1 |
| `Ch` | `-0.1 * 0.01 * 2 / (0.2 * 0.25) = -0.04` (trailing edge pushed up) | -0.04 |
| `CB` | `0.5 * 0.01 * 2 / (0.2 * 1.0) = 0.05` | 0.05 |

The same geometry given in `BRU` gave identical results; a swept hinge line
gave an orthonormal frame with `x_h` perpendicular to the hinge; a 10 deg
dihedral tilted `z_h` inboard by 10 deg; a trailing-edge point minus a hinge
point gave the same frame as the aft direction; `delta = +10 deg` moved the
trailing edge down; a left tail with an outboard axis gave `z_h` down; a
vertical fin with the axis up and the trailing edge aft gave `z_h` to the
left.

## References

- ADR 0001 and ADR 0002.
- The signs are defined by this record (right-hand rule about the user-chosen
  hinge axis) and do not depend on an external source. The statement that they
  match the common convention (positive deflection and positive hinge moment
  with the trailing edge down) is informational; NACA reports define flap and
  aileron deflection as positive with the trailing edge down, but a primary
  source stating the hinge-moment sign in those words has not yet been cited.
