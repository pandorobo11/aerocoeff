Control-surface loads
=====================

:class:`~aerocoeff.ControlSurface` re-expresses the load on one surface as its
normal force ``CN_s``, hinge moment ``Ch``, and root bending moment ``CB``.

Geometry and signs
------------------

* The hinge axis ``y_h`` points from ``hinge_start_m`` to ``hinge_end_m``, and
  ``hinge_start_m`` is the moment reference point of the result.
* ``trailing_edge_direction`` points from the hinge toward the trailing edge of
  the undeflected surface. Only its part perpendicular to the hinge axis is
  used, so a swept hinge line needs nothing special.
* ``z_h = x_h x y_h``. A positive deflection is a right-hand rotation about
  ``y_h``.

The signs follow the hinge-axis direction you choose. For a right horizontal
tail with the axis pointing outboard, ``x_h`` is aft, ``y_h`` right, and ``z_h``
up: a positive deflection moves the trailing edge down, a positive normal force
is up, and a positive hinge moment tends to deflect the trailing edge down.

Example
-------

The input must be the load on the surface alone, taken about a known point.
Here the coefficients are in body axes (``FRD``): an upward force
``CZ = -0.01`` acts 0.1 m aft of the hinge and 0.5 m outboard of the root,
with its moment taken about the vehicle reference point at the origin of the
CAD model. The hinge points, trailing-edge direction, and
``moment_reference_m`` are expressed separately in ``BRU`` (x back, y right,
z up):

>>> import numpy as np
>>> from aerocoeff import AeroCoefficients, ControlSurface, Frame, ReferenceQuantities
>>> vehicle = ReferenceQuantities.from_span_chord(area_m2=2.0, span_m=10.0, chord_m=2.0)
>>> tail = ControlSurface(
...     hinge_start_m=np.array([5.0, 0.2, 0.0]),
...     hinge_end_m=np.array([5.0, 1.2, 0.0]),
...     trailing_edge_direction=np.array([1.0, 0.0, 0.0]),
...     points_frame=Frame.from_axes("BRU"),
...     area_m2=0.2,
...     hinge_moment_length_m=0.25,
...     bending_moment_length_m=1.0,
... )
>>> tail_load = AeroCoefficients.from_components(
...     CX=0.0, CY=0.0, CZ=-0.01, Cl=-0.0007, Cm=-0.0255, Cn=0.0, reference=vehicle
... )
>>> components = tail.three_components_array(
...     tail_load, moment_reference_m=np.zeros(3), deflection_deg=0.0
... )
>>> components.round(12).tolist()
[0.1, -0.04, 0.05]

These are ``CN_s = 0.01 * 2 / 0.2``, ``Ch = -0.1 * 0.01 * 2 / (0.2 * 0.25)``
(the trailing edge is pushed up), and ``CB = 0.5 * 0.01 * 2 / (0.2 * 1.0)``.

The deflection is required on every call, as ``deflection_deg`` or
``deflection_rad``, so a forgotten deflection is never read as zero.
:meth:`~aerocoeff.ControlSurface.loads` returns all six components in the hinge
frame, :meth:`~aerocoeff.ControlSurface.frame` the hinge frame, and
:attr:`~aerocoeff.ControlSurface.reference` the surface reference quantities.
