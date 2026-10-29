Forces and moments
==================

:meth:`~aerocoeff.AeroCoefficients.to_loads_array` returns
``Fx, Fy, Fz, Mx, My, Mz`` in N and N m along and about the axes of the
coefficient frame: ``F = q S C_F`` and ``M = q S (l C_M)`` per axis. With
``q = 0.5 rho V^2 = 1531.25 Pa`` (sea-level density 1.225 kg/m^3, 50 m/s):

>>> from aerocoeff import AeroCoefficients, ReferenceQuantities
>>> reference = ReferenceQuantities.from_span_chord(area_m2=2.0, span_m=10.0, chord_m=2.0)
>>> body = AeroCoefficients.from_axial_normal(
...     CA=0.1, CY=0.0, CN=1.0, Cl=0.0, Cm=-0.05, Cn=0.0, reference=reference
... )
>>> q_pa = 0.5 * 1.225 * 50.0**2
>>> loads = body.to_loads_array(dynamic_pressure_pa=q_pa)
>>> loads.tolist()
[-306.25, 0.0, -3062.5, 0.0, -306.25, 0.0]

:meth:`~aerocoeff.AeroCoefficients.from_loads_array` is the inverse:

>>> restored = AeroCoefficients.from_loads_array(
...     loads, dynamic_pressure_pa=q_pa, reference=reference
... )
>>> restored.force.tolist(), restored.moment.tolist()
([-0.1, 0.0, -1.0], [0.0, -0.05, 0.0])

The dynamic pressure must be positive and is given by the caller; frame changes
and moment transfers are done on the coefficients.
