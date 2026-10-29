Using the GUI
=============

The optional GUI runs the same calculations as the Python API in a web
browser, for one case typed in or for many cases from a CSV file. It adds no
calculation of its own.

Installation and launch
-----------------------

Install the package with its ``gui`` extra, which adds Streamlit:

.. code-block:: console

   $ pip install "aerocoeff-0.1.0-py3-none-any.whl[gui]"
   $ aerocoeff-gui

``aerocoeff-gui`` opens the GUI in your browser. It listens only on this
computer (``127.0.0.1``) and sends no usage statistics. Stop it with
:kbd:`Ctrl-C` in the terminal. Options after ``aerocoeff-gui`` are passed to
``streamlit run``, for example ``aerocoeff-gui --server.port 8600``.

Pages
-----

.. list-table::
   :header-rows: 1

   * - Page
     - What it does
   * - Transform
     - Changes the frame (body, stability, wind, or axis letters), moves the
       moment reference point, and changes the reference quantities, in any
       combination and in one step. The results include ``CA, CN`` in body axes
       and ``CD, CL`` in stability axes.
   * - Control surface
     - Returns the normal force ``CN_s``, hinge moment ``Ch``, and root bending
       moment ``CB`` of one surface, and the six components in its hinge frame.
   * - Forces and moments
     - Converts coefficients to forces in N and moments in N m, or back.
   * - Documentation
     - Shows this manual.

Every page first asks for the settings shared by all cases: which coefficient
columns are given and in which frame, the reference quantities, and any points
or surface geometry. The frame of the points has no default; enter axis letters
such as ``BRU``. On the Transform page, new reference lengths divide the x-, y-,
and z-axis moments of the output frame. The conventions are those of
:doc:`../getting_started/conventions`.

Single case and CSV batch
-------------------------

Below the settings, the **Single case** tab takes the values of one case and
shows the results. Angles, deflections, and dynamic pressures start empty and
must be entered, so a forgotten value is never read as zero.

The **CSV batch** tab lists the columns the page needs and offers a template.
Upload a CSV file with a header row and one case per row:

.. code-block:: text

   case,CA,CY,CN,Cl,Cm,Cn,alpha_deg
   cruise,0.02,0,0.1,0,-0.01,0,2
   climb,0.03,0,0.5,0,-0.05,0,10

Column names are case sensitive. Columns that the page does not use, such as
``case`` above, are copied to the results. The results are shown in a table
and can be downloaded as a CSV file with the input columns followed by the
result columns; a result whose name is already an input column gets the suffix
``_out``. A file with a missing column, a value that is not a number, or a
value the calculation rejects shows an error instead of results.

The column names are:

.. list-table::
   :header-rows: 1

   * - Columns
     - Meaning
   * - ``CA, CY, CN, Cl, Cm, Cn``
     - body-axis coefficients
   * - ``CD, CY, CL, Cl, Cm, Cn``
     - stability-axis coefficients
   * - ``CX, CY, CZ, Cl, Cm, Cn``
     - frame components in the chosen input frame
   * - ``Fx_N, Fy_N, Fz_N, Mx_Nm, My_Nm, Mz_Nm``
     - forces in N and moments in N m
   * - ``alpha_deg``, ``beta_deg``
     - angle of attack and sideslip in degrees, for stability and wind axes
   * - ``deflection_deg``
     - control-surface deflection in degrees
   * - ``dynamic_pressure_pa``
     - dynamic pressure in Pa
   * - ``CN_s, Ch, CB`` and ``CX_h`` ... ``Cn_h``
     - control-surface results

Documentation
-------------

The **Documentation** page shows this manual inside the GUI, served from the
installed package. **Open in a new tab** shows the selected page in a separate
browser tab.
