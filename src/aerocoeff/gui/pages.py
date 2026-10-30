"""Streamlit pages for the four calculations, each with a single case and a CSV batch."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from functools import partial
from typing import Any

import numpy as np
import streamlit as st

from aerocoeff._validation import FloatArray
from aerocoeff.coefficients import ReferenceQuantities
from aerocoeff.control_surface import ControlSurface
from aerocoeff.frames import Frame
from aerocoeff.gui import cases as c

Calculation = Callable[[Mapping[str, FloatArray]], c.Columns]
Point = tuple[float, float, float]

FRAME_LABELS: dict[c.FrameChoiceKind, str] = {
    "body": "Body (FRD)",
    "stability": "Stability (alpha per case)",
    "wind": "Wind (alpha and beta per case)",
    "axes": "Axis letters, for example BRU",
}
COLUMN_SET_LABELS: dict[c.ColumnSet, str] = {
    "axial_normal": "CA, CY, CN, Cl, Cm, Cn in body axes",
    "lift_drag": "CD, CY, CL, Cl, Cm, Cn in stability axes",
    "components": "CX, CY, CZ, Cl, Cm, Cn in a chosen frame",
}
# Case values that must be entered: a missing angle or pressure is never read as zero.
REQUIRED_ENTRIES = frozenset({c.ALPHA, c.BETA, c.DEFLECTION, c.DYNAMIC_PRESSURE})
NUMBER_FORMAT = "%.6g"
SETTINGS_INCOMPLETE = "Complete the settings above to see the results."


def frame_input(label: str, key: str, kind: c.FrameChoiceKind = "body") -> c.FrameChoice:
    """A frame selector with a field for axis letters."""
    kinds = tuple(FRAME_LABELS)
    chosen = st.selectbox(
        label, kinds, index=kinds.index(kind), format_func=FRAME_LABELS.__getitem__, key=key
    )
    if chosen == "axes":
        axes = st.text_input("Axis letters (one of F/B, R/L, D/U each)", "FRD", key=f"{key}_axes")
        return c.FrameChoice("axes", axes)
    return c.FrameChoice(chosen)


def coefficient_input(key: str) -> c.CoefficientInput:
    """The coefficient columns given per case, and their frame."""
    column_sets = tuple(COLUMN_SET_LABELS)
    column_set = st.selectbox(
        "Input coefficients",
        column_sets,
        format_func=COLUMN_SET_LABELS.__getitem__,
        key=f"{key}_columns",
    )
    if column_set == "components":
        return c.CoefficientInput("components", frame_input("Input frame", f"{key}_frame"))
    return c.CoefficientInput(column_set)


def reference_input(label: str, key: str) -> ReferenceQuantities | None:
    """Reference area and the three moment reference lengths."""
    st.markdown(f"**{label}**")
    fields = ("area_m2", "length_roll_m", "length_pitch_m", "length_yaw_m")
    columns = st.columns(len(fields))
    values = [
        column.number_input(name, value=1.0, format=NUMBER_FORMAT, key=f"{key}_{name}")
        for column, name in zip(columns, fields, strict=True)
    ]
    try:
        return ReferenceQuantities(*values)
    except ValueError as error:
        st.error(str(error))
        return None


def point_input(label: str, key: str, default: Point = (0.0, 0.0, 0.0)) -> Point:
    """Three coordinates in meters, or the three components of a direction."""
    st.markdown(label)
    x, y, z = (
        column.number_input(axis, value=value, format=NUMBER_FORMAT, key=f"{key}_{axis}")
        for column, axis, value in zip(st.columns(3), "xyz", default, strict=True)
    )
    return (x, y, z)


def axes_input(label: str, key: str) -> str | None:
    """Axis letters of a points frame; there is no default, so it must be entered."""
    axes = st.text_input(label, placeholder="for example BRU", key=key).strip()
    if not axes:
        st.info("Enter the frame of the points.")
        return None
    return axes


def _calculate(calculate: Calculation, cases: Mapping[str, FloatArray]) -> c.Columns | None:
    try:
        return calculate(cases)
    except (TypeError, ValueError) as error:
        st.error(str(error))
        return None


def _number_columns(names: Sequence[str]) -> dict[str, Any]:
    return {name: st.column_config.NumberColumn(format=NUMBER_FORMAT) for name in names}


def cases_and_results(required: Sequence[str], calculate: Calculation | None, key: str) -> None:
    """Tabs for one case typed in and for a CSV batch, with their results.

    The inputs are always shown, so typed values survive while a setting above is
    incomplete; ``calculate`` is ``None`` until the settings are complete.
    """
    single, batch = st.tabs(["Single case", "CSV batch"])
    with single:
        columns = st.columns(4)
        values = {
            name: columns[index % 4].number_input(
                name,
                value=None if name in REQUIRED_ENTRIES else 0.0,
                format=NUMBER_FORMAT,
                key=f"{key}_case_{name}",
            )
            for index, name in enumerate(required)
        }
        missing = [name for name, value in values.items() if value is None]
        if calculate is None:
            st.info(SETTINGS_INCOMPLETE)
        if missing:
            st.info(f"Enter {', '.join(missing)}.")
        if calculate is not None and not missing:
            entered = {name: float(value) for name, value in values.items() if value is not None}
            results = _calculate(calculate, c.single_case(entered))
            if results is not None:
                st.dataframe(
                    {"Quantity": list(results), "Value": [float(v[0]) for v in results.values()]},
                    column_config=_number_columns(["Value"]),
                    hide_index=True,
                )
    with batch:
        st.markdown(
            "Upload a CSV file with a header row and the columns "
            + ", ".join(f"`{name}`" for name in required)
            + ". Other columns are copied to the results."
        )
        st.download_button(
            "Download a template",
            c.cases_csv_template(required),
            file_name=f"{key}_template.csv",
            mime="text/csv",
            key=f"{key}_template",
        )
        uploaded = st.file_uploader("CSV file", type="csv", key=f"{key}_upload")
        if uploaded is None:
            return
        if calculate is None:
            st.info(SETTINGS_INCOMPLETE)
            return
        try:
            table = c.read_cases_csv(uploaded.getvalue(), required)
        except ValueError as error:
            st.error(str(error))
            return
        results = _calculate(calculate, table.values)
        if results is None:
            return
        st.dataframe(results, column_config=_number_columns(list(results)))
        st.download_button(
            "Download the results",
            c.write_results_csv(table, results),
            file_name=f"{key}_results.csv",
            mime="text/csv",
            key=f"{key}_results",
        )


def render_transform() -> None:
    """Change the frame, the moment reference point, and the reference quantities."""
    st.title("Transform")
    st.caption(
        "Change the frame, the moment reference point, and the reference quantities in "
        "one step. Each change is optional, and their order does not matter."
    )
    source = coefficient_input("transform")
    reference = reference_input("Reference quantities of the input", "transform_reference")

    target = None
    if st.checkbox("Change the frame", value=True, key="transform_change_frame"):
        target = frame_input("Output frame", "transform_output", "stability")

    transfer = None
    points_missing = False
    if st.checkbox("Move the moment reference point", key="transform_move"):
        axes = axes_input("Frame of the points (axis letters)", "transform_points_axes")
        from_point = point_input("From point (m)", "transform_from")
        to_point = point_input("To point (m)", "transform_to")
        if axes is None:
            points_missing = True
        else:
            transfer = c.PointTransfer(from_point, to_point, axes)

    new_reference = None
    renormalize = st.checkbox("Change the reference quantities", key="transform_renormalize")
    if renormalize:
        st.caption(
            "The new lengths divide the x-, y-, and z-axis moments of the output frame. "
            "In a frame that permutes the axes, such as RDF, they are not roll, pitch, "
            "and yaw lengths."
        )
        new_reference = reference_input("New reference quantities", "transform_new_reference")
    calculate: Calculation | None = None
    if reference is not None and not points_missing and not (renormalize and new_reference is None):
        calculate = partial(
            c.transform_cases,
            source,
            reference=reference,
            target=target,
            transfer=transfer,
            new_reference=new_reference,
        )
    cases_and_results(c.transform_columns(source, target), calculate, "transform")


def render_control_surface() -> None:
    """Normal force, hinge moment, and root bending moment of one control surface."""
    st.title("Control-surface loads")
    st.caption(
        "The input is the load on the surface alone. The hinge axis points from the "
        "start to the end, and a positive deflection is a right-hand rotation about it."
    )
    source = coefficient_input("surface")
    reference = reference_input("Vehicle reference quantities", "surface_vehicle_reference")
    axes = axes_input("Frame of the points and the direction (axis letters)", "surface_axes")
    moment_reference = point_input(
        "Moment reference point of the input coefficients (m)", "surface_moment_reference"
    )
    hinge_start = point_input("Hinge start (m)", "surface_hinge_start")
    hinge_end = point_input("Hinge end (m)", "surface_hinge_end", (0.0, 1.0, 0.0))
    trailing_edge = point_input(
        "Direction from the hinge toward the trailing edge",
        "surface_trailing_edge",
        (1.0, 0.0, 0.0),
    )
    st.markdown("**Surface reference**")
    lengths = st.columns(4)
    area = lengths[0].number_input("area_m2", value=1.0, format=NUMBER_FORMAT, key="surface_area")
    hinge_length = lengths[1].number_input(
        "hinge_moment_length_m", value=1.0, format=NUMBER_FORMAT, key="surface_hinge_length"
    )
    bending_length = lengths[2].number_input(
        "bending_moment_length_m", value=1.0, format=NUMBER_FORMAT, key="surface_bending_length"
    )
    normal_length = lengths[3].number_input(
        "normal_moment_length_m (empty: bending length)",
        value=None,
        format=NUMBER_FORMAT,
        key="surface_normal_length",
    )
    calculate: Calculation | None = None
    if axes is not None:
        try:
            surface = ControlSurface(
                hinge_start_m=np.array(hinge_start),
                hinge_end_m=np.array(hinge_end),
                trailing_edge_direction=np.array(trailing_edge),
                points_frame=Frame.from_axes(axes),
                area_m2=area,
                hinge_moment_length_m=hinge_length,
                bending_moment_length_m=bending_length,
                normal_moment_length_m=normal_length,
            )
        except (TypeError, ValueError) as error:
            st.error(str(error))
        else:
            if reference is not None:
                calculate = partial(
                    c.surface_components,
                    source,
                    reference=reference,
                    surface=surface,
                    moment_reference_m=moment_reference,
                )
    cases_and_results(c.surface_columns(source), calculate, "surface")


def render_loads() -> None:
    """Convert between coefficients and forces and moments in newtons."""
    st.title("Forces and moments")
    st.caption("F = q S C_F and M = q S (l C_M) per axis, in the frame of the input.")
    to_loads = (
        st.radio(
            "Direction",
            ("Coefficients to forces and moments", "Forces and moments to coefficients"),
            horizontal=True,
            key="loads_direction",
        )
        == "Coefficients to forces and moments"
    )
    reference = reference_input("Reference quantities", "loads_reference")
    calculate: Calculation | None = None
    if to_loads:
        source = coefficient_input("loads")
        if reference is not None:
            calculate = partial(c.coefficients_to_loads, source, reference=reference)
        cases_and_results(c.loads_columns(source), calculate, "loads_to")
    else:
        frame = frame_input("Frame of the forces and moments", "loads_frame")
        if reference is not None:
            calculate = partial(c.loads_to_coefficients, frame, reference=reference)
        cases_and_results(c.coefficient_from_loads_columns(frame), calculate, "loads_from")
