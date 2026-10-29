API reference
=============

Import the classes and ``FrameKind`` from the top-level package, for example
``from aerocoeff import AeroCoefficients``. The tolerance constants listed
below are available from their indicated submodules, for example
``from aerocoeff.coefficients import LATERAL_ATOL``.

.. currentmodule:: aerocoeff

Coefficients
------------

.. autoclass:: AeroCoefficients
   :members:

.. autoclass:: ReferenceQuantities
   :members:

.. autodata:: aerocoeff.coefficients.LATERAL_ATOL

Frames
------

.. autoclass:: Frame
   :members:

.. autodata:: FrameKind

.. autodata:: aerocoeff.frames.ROTATION_ATOL

Control surfaces
----------------

.. autoclass:: ControlSurface
   :members:

.. autodata:: aerocoeff.control_surface.TRAILING_EDGE_RTOL
