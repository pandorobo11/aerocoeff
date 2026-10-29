aerocoeff
=========

``aerocoeff`` is a Python library for aerodynamic force and moment
coefficients. Use it when coefficients from a wind tunnel, a CFD run, or a
panel code have to be expressed differently:

* in other axes: body, stability, wind, or the axes of a CAD model;
* about another moment reference point, such as the center of gravity;
* with another reference area or other reference lengths;
* as the normal force, hinge moment, and root bending moment of a control
  surface;
* as forces and moments in newtons and newton meters.

Every frame, sign, and angle unit is stated explicitly, so a result never
depends on a hidden convention. Dimensional loads, reference quantities, and
point coordinates use SI units. Coefficient components and angles support
NumPy arrays of cases. Reference quantities are shared scalars, and each
``ControlSurface`` describes one fixed geometry; see
:doc:`guides/batches_and_validation` for batch inputs.

If you are new to the package, read :doc:`getting_started/installation`,
:doc:`getting_started/quickstart`, and :doc:`getting_started/conventions` in
that order, then the :doc:`guides/index` for the tasks you need. The
:doc:`api/index` lists every class and method.

.. toctree::
   :maxdepth: 2
   :titlesonly:

   getting_started/index
   guides/index
   api/index
