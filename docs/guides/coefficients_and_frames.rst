Coefficients and frames
=======================

Reference quantities
--------------------

>>> from aerocoeff import AeroCoefficients, Frame, ReferenceQuantities
>>> reference = ReferenceQuantities.from_span_chord(area_m2=2.0, span_m=10.0, chord_m=2.0)
>>> reference.moment_lengths_m.tolist()
[10.0, 2.0, 10.0]

``from_span_chord`` uses the span for roll and yaw and the chord for pitch. Give
the four values directly when they differ:
``ReferenceQuantities(area_m2=..., length_roll_m=..., length_pitch_m=..., length_yaw_m=...)``.
All of them must be positive.

Building coefficients
---------------------

Body-axis results, such as the ``CA, CY, CN, Cl, Cm, Cn`` output of a panel or
CFD code:

>>> body = AeroCoefficients.from_axial_normal(
...     CA=0.1, CY=0.0, CN=1.0, Cl=0.0, Cm=-0.05, Cn=0.0, reference=reference
... )
>>> body.force.tolist(), body.moment.tolist()
([-0.1, 0.0, -1.0], [0.0, -0.05, 0.0])

The other constructors are:

.. list-table::
   :header-rows: 1

   * - Constructor
     - Input
     - Frame
   * - ``from_components(CX=..., ..., Cn=..., reference=..., frame=None)``
     - frame components
     - ``frame``, default body
   * - ``from_components_array(array, reference=..., frame=None)``
     - ``(..., 6)``: ``CX, CY, CZ, Cl, Cm, Cn``
     - ``frame``, default body
   * - ``from_axial_normal(...)``, ``from_axial_normal_array(...)``
     - ``CA, CY, CN, Cl, Cm, Cn``
     - body
   * - ``from_lift_drag(..., alpha_deg=...)``, ``from_lift_drag_array(...)``
     - ``CD, CY, CL, Cl, Cm, Cn``
     - stability
   * - ``from_longitudinal_axial_normal(...)`` and ``_array``
     - ``CA, CN, Cm``
     - body
   * - ``from_longitudinal_lift_drag(..., alpha_deg=...)`` and ``_array``
     - ``CD, CL, Cm``
     - stability
   * - ``from_loads_array(array, dynamic_pressure_pa=..., reference=..., frame=None)``
     - ``(..., 6)``: ``Fx, Fy, Fz, Mx, My, Mz`` in N and N m
     - ``frame``, default body

Each ``from_..._array`` constructor has a matching ``to_..._array`` method that
returns a new array. The longitudinal outputs raise instead of silently
dropping a nonzero ``CY``, ``Cl``, or ``Cn``.

Changing frames
---------------

:meth:`~aerocoeff.AeroCoefficients.to_frame` rotates the six components into
another frame about the same moment reference point. Lift and drag follow from
axial and normal force at alpha = 30 deg (Anderson, *Fundamentals of
Aerodynamics*, Sec. 1.5: ``CD = CN sin(alpha) + CA cos(alpha)``,
``CL = CN cos(alpha) - CA sin(alpha)``). Named quantities are only available in
the frame that defines them:

>>> stability = body.to_frame(Frame.stability(alpha_deg=30.0))
>>> round(float(stability.CD), 6), round(float(stability.CL), 6)
(0.586603, 0.816025)
>>> body.CD
Traceback (most recent call last):
...
ValueError: CD is defined in stability axes, but these coefficients are in the 'FRD' frame; convert them with to_frame() first

Moments are rotated as the length-scaled vector
``(Cl l_roll, Cm l_pitch, Cn l_yaw)`` and renormalized, because the lengths
differ between axes. A pitching moment ``Cm = 0.1`` with ``l_pitch = 2`` and
``l_roll = 10`` seen in wind axes at beta = 10 deg has
``Cl_wind = 0.1 * 2 * sin(10 deg) / 10``, not ``0.1 * sin(10 deg)``:

>>> pitching = AeroCoefficients.from_components(
...     CX=0.0, CY=0.0, CZ=0.0, Cl=0.0, Cm=0.1, Cn=0.0, reference=reference
... )
>>> wind = pitching.to_frame(Frame.wind(alpha_deg=0.0, beta_deg=10.0))
>>> round(float(wind.Cl), 6)
0.003473

The reference lengths stay with the axis positions. In a frame that permutes
the axes, such as ``"RDF"``, the x-axis moment is still divided by ``l_roll``,
so choose reference lengths for that frame's own axes with
:meth:`~aerocoeff.AeroCoefficients.with_reference`.
