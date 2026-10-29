Quickstart
==========

This example takes coefficients in body axes, as most panel and CFD codes
report them, and computes lift and drag at an angle of attack of 30 degrees.

Every set of coefficients carries its reference quantities: the reference area
and one moment reference length per axis. ``from_span_chord`` uses the span for
the roll and yaw moments and the chord for the pitching moment:

>>> from aerocoeff import AeroCoefficients, Frame, ReferenceQuantities
>>> reference = ReferenceQuantities.from_span_chord(area_m2=2.0, span_m=10.0, chord_m=2.0)
>>> reference.moment_lengths_m.tolist()
[10.0, 2.0, 10.0]

Body-axis coefficients from the axial force ``CA``, side force ``CY``, normal
force ``CN``, and the moments ``Cl``, ``Cm``, ``Cn``. Internally they are stored
as components along the body axes, so ``CX = -CA`` and ``CZ = -CN``:

>>> body = AeroCoefficients.from_axial_normal(
...     CA=0.1, CY=0.0, CN=1.0, Cl=0.0, Cm=-0.05, Cn=0.0, reference=reference
... )
>>> body.force.tolist(), body.moment.tolist()
([-0.1, 0.0, -1.0], [0.0, -0.05, 0.0])

Lift and drag are defined in stability axes, so convert the coefficients to
the stability frame at alpha = 30 deg. The result agrees with the textbook
relations ``CD = CN sin(alpha) + CA cos(alpha)`` and
``CL = CN cos(alpha) - CA sin(alpha)`` (Anderson, *Fundamentals of
Aerodynamics*, Sec. 1.5):

>>> stability = body.to_frame(Frame.stability(alpha_deg=30.0))
>>> round(float(stability.CD), 6), round(float(stability.CL), 6)
(0.586603, 0.816025)

Where to go next
----------------

* :doc:`conventions` defines the axes, angles, signs, and reference lengths
  used everywhere. Read it before relying on a sign.
* :doc:`../guides/coefficients_and_frames` lists every way to build
  coefficients and every frame.
* :doc:`../api/index` lists the complete public API.
