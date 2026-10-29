Quickstart
==========

This example builds body-axis coefficients, such as the ``CA, CY, CN, Cl, Cm,
Cn`` output of panelsolver, and reads lift and drag in stability axes.

Reference quantities hold the reference area and one moment reference length
per axis. ``from_span_chord`` uses the span for roll and yaw and the chord for
pitch:

>>> from aerocoeff import AeroCoefficients, Frame, ReferenceQuantities
>>> reference = ReferenceQuantities.from_span_chord(area_m2=2.0, span_m=10.0, chord_m=2.0)
>>> reference.moment_lengths_m.tolist()
[10.0, 2.0, 10.0]

Body-axis coefficients from axial and normal force (``CX = -CA``,
``CZ = -CN``):

>>> body = AeroCoefficients.from_axial_normal(
...     CA=0.1, CY=0.0, CN=1.0, Cl=0.0, Cm=-0.05, Cn=0.0, reference=reference
... )
>>> body.force.tolist(), body.moment.tolist()
([-0.1, 0.0, -1.0], [0.0, -0.05, 0.0])

Lift and drag at alpha = 30 deg. They follow Anderson, *Fundamentals of
Aerodynamics*, Sec. 1.5: ``CD = CN sin(alpha) + CA cos(alpha)`` and
``CL = CN cos(alpha) - CA sin(alpha)``:

>>> stability = body.to_frame(Frame.stability(alpha_deg=30.0))
>>> round(float(stability.CD), 6), round(float(stability.CL), 6)
(0.586603, 0.816025)

Where to go next
----------------

* :doc:`conventions` defines the frames, angles, component signs, per-axis
  reference lengths, and points used everywhere.
* :doc:`../guides/coefficients_and_frames` lists every constructor and frame.
* :doc:`../api/index` lists the complete public API.
