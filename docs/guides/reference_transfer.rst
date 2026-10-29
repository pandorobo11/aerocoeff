Moment reference and reference quantities
=========================================

Moving the moment reference point
---------------------------------

:meth:`~aerocoeff.AeroCoefficients.transfer_moment_reference` applies
``M_to = M_from + (r_from - r_to) x F`` (ADR 0002). Both points are in
``points_frame``, which has no default. Here an upward normal force ``CN = 1``
is moved to a point 0.5 m aft, given in ``BRU`` STL coordinates (x back), so
``Delta Cm = CN * 0.5 / l_pitch = +0.25``, nose up:

>>> from aerocoeff import AeroCoefficients, Frame, ReferenceQuantities
>>> reference = ReferenceQuantities.from_span_chord(area_m2=2.0, span_m=10.0, chord_m=2.0)
>>> lift = AeroCoefficients.from_components(
...     CX=0.0, CY=0.0, CZ=-1.0, Cl=0.0, Cm=0.0, Cn=0.0, reference=reference
... )
>>> bru = Frame.from_axes("BRU")
>>> moved = lift.transfer_moment_reference(
...     from_point_m=[0.0, 0.0, 0.0], to_point_m=[0.5, 0.0, 0.0], points_frame=bru
... )
>>> moved.moment.tolist()
[0.0, 0.25, 0.0]

Changing reference quantities
-----------------------------

:meth:`~aerocoeff.AeroCoefficients.with_reference` renormalizes in the same
frame and about the same point: ``C_F' = C_F S / S'`` and
``C_M' = C_M (S l) / (S' l')`` per axis.

>>> body = AeroCoefficients.from_axial_normal(
...     CA=0.1, CY=0.0, CN=1.0, Cl=0.0, Cm=-0.05, Cn=0.0, reference=reference
... )
>>> wing = ReferenceQuantities.from_span_chord(area_m2=4.0, span_m=10.0, chord_m=0.5)
>>> renormalized = body.with_reference(wing)
>>> renormalized.force.tolist(), renormalized.moment.tolist()
([-0.05, 0.0, -0.5], [0.0, -0.1, 0.0])

Combined transformation
-----------------------

:meth:`~aerocoeff.AeroCoefficients.transform` applies any combination of a
moment reference transfer, a frame change, and a reference change. The
operations are exact, so their order does not matter. Give ``from_point_m``,
``to_point_m``, and ``points_frame`` together or not at all, and give
``reference`` lengths for the axes of ``frame``.
