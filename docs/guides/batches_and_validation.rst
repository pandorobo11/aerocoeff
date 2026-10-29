Batches and validation
======================

Batches
-------

Every component may be an array. Coefficient vectors have shape ``(..., 3)``,
frames built from angle arrays have a matching batch shape, and points and the
dynamic pressure broadcast with the coefficients. An alpha sweep, with lift
and drag as in :doc:`coefficients_and_frames`:

>>> import numpy as np
>>> from aerocoeff import AeroCoefficients, Frame, ReferenceQuantities
>>> reference = ReferenceQuantities.from_span_chord(area_m2=2.0, span_m=10.0, chord_m=2.0)
>>> table = np.array([[0.02, 0.0, 0.1, 0.0, -0.01, 0.0], [0.03, 0.0, 0.5, 0.0, -0.05, 0.0]])
>>> sweep = AeroCoefficients.from_axial_normal_array(table, reference=reference)
>>> lift_drag = sweep.to_frame(Frame.stability(alpha_deg=[2.0, 10.0])).to_lift_drag_array()
>>> lift_drag.round(6).tolist()
[[0.023478, 0.0, 0.099241, 0.0, -0.01, 0.0], [0.116368, 0.0, 0.487194, 0.0, -0.05, 0.0]]

Validation
----------

Inputs are checked once, at a shared boundary. NaN, infinity, booleans used as
numbers, complex and date values, wrong shapes, and zero or negative reference
quantities or dynamic pressures raise :class:`ValueError` or
:class:`TypeError` instead of propagating:

>>> ReferenceQuantities.from_span_chord(area_m2=0.0, span_m=10.0, chord_m=2.0)
Traceback (most recent call last):
...
ValueError: area_m2 must be positive, got 0.0
