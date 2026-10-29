Conventions
===========

These conventions apply to every function in the package. Read this page
before relying on a sign or a frame.

Frames
------

All frames are right-handed and share the moment reference point as origin.

.. list-table::
   :header-rows: 1

   * - Frame
     - Axes
     - Built with
   * - Body (default)
     - x forward, y toward the right wing, z down (FRD)
     - ``Frame.body()``
   * - Stability
     - body rotated about y_body by alpha
     - ``Frame.stability(alpha_deg=...)``
   * - Wind
     - stability rotated about z_stability by beta
     - ``Frame.wind(alpha_deg=..., beta_deg=...)``
   * - Axis letters
     - one of F/B, R/L, D/U per axis, for example ``"BRU"``: x back, y right, z up,
       as in many CAD models
     - ``Frame.from_axes("BRU")``
   * - Rotation matrix
     - ``v_frame = R @ v_body``
     - ``Frame.from_matrix(R)``

A frame is never inferred from data: every function that takes a frame other
than the body default asks for it explicitly. Left-handed frames and
non-orthonormal matrices are rejected.

Positive alpha is nose up relative to the flow, and positive beta is relative
wind from the right. Every angle argument carries its unit, ``alpha_rad`` or
``alpha_deg``; give exactly one of each pair.

Coefficients
------------

:class:`~aerocoeff.AeroCoefficients` holds ``force = (CX, CY, CZ)`` and
``moment = (Cl, Cm, Cn)`` along and about the axes of its ``frame``, each
with shape ``(..., 3)``, together with its reference quantities. Forces are
positive along each axis, and moments are positive by the right-hand rule: in
body axes, right wing down, nose up, and nose right.

.. list-table::
   :header-rows: 1

   * - Quantity
     - Definition
     - Available in
   * - Axial force ``CA``
     - ``-CX_body``
     - body frame
   * - Normal force ``CN``
     - ``-CZ_body``
     - body frame
   * - Drag ``CD``
     - ``-CX_stability``
     - stability frame
   * - Lift ``CL``
     - ``-CZ_stability``
     - stability frame
   * - ``CX``, ``CY``, ``CZ``, ``Cl``, ``Cm``, ``Cn``
     - frame components
     - every frame

Each moment axis has its own reference length:
``Cl = L / (q S l_roll)``, ``Cm = M / (q S l_pitch)``, ``Cn = N / (q S l_yaw)``.
The lengths belong to the x, y, and z axis positions of whatever frame the
coefficients are in.

Points
------

Points, such as moment reference points and hinge lines, are in meters in their
own ``points_frame``, which is always given explicitly. Only
differences of points are used, so the origin (for example the CAD or STL
origin) never needs to be stated. Points are often in ``BRU``, where x points
back and z up.

Control surfaces
----------------

A control surface has its own frame, built from its hinge line, and its own
three components; see :doc:`../guides/control_surface`.
