import numpy as np
import pytest

from aerocoeff import AeroCoefficients, ControlSurface, Frame, ReferenceQuantities
from aerocoeff.gui import cases as c

REFERENCE = ReferenceQuantities(
    area_m2=2.0, length_roll_m=10.0, length_pitch_m=2.0, length_yaw_m=10.0
)
BODY_COMPONENTS = c.CoefficientInput("components")
AXIAL_NORMAL = c.CoefficientInput("axial_normal")
LIFT_DRAG = c.CoefficientInput("lift_drag")


def _cases(**columns: list[float]) -> dict[str, np.ndarray]:
    return {name: np.array(values, dtype=np.float64) for name, values in columns.items()}


def _body(**values: float) -> dict[str, np.ndarray]:
    components = dict.fromkeys(("CX", "CY", "CZ", "Cl", "Cm", "Cn"), 0.0) | values
    return c.single_case(components)


# Input choices


def test_frame_choices_need_their_angle_columns() -> None:
    assert c.FrameChoice("body").angle_columns == ()
    assert c.FrameChoice("stability").angle_columns == ("alpha_deg",)
    assert c.FrameChoice("wind").angle_columns == ("alpha_deg", "beta_deg")
    assert c.FrameChoice("axes", "BRU").angle_columns == ()


def test_frame_choices_build_the_api_frames() -> None:
    cases = _cases(alpha_deg=[5.0], beta_deg=[2.0])
    np.testing.assert_array_equal(c.FrameChoice("body").build(cases).rotation_from_body, np.eye(3))
    np.testing.assert_array_equal(
        c.FrameChoice("stability").build(cases).rotation_from_body,
        Frame.stability(alpha_deg=[5.0]).rotation_from_body,
    )
    np.testing.assert_array_equal(
        c.FrameChoice("wind").build(cases).rotation_from_body,
        Frame.wind(alpha_deg=[5.0], beta_deg=[2.0]).rotation_from_body,
    )
    assert c.FrameChoice("axes", "BRU").build(cases).name == "BRU"


def test_coefficient_inputs_name_their_columns_and_frames() -> None:
    assert AXIAL_NORMAL.required_columns == ("CA", "CY", "CN", "Cl", "Cm", "Cn")
    assert AXIAL_NORMAL.frame_choice == c.FrameChoice("body")
    assert LIFT_DRAG.required_columns == ("CD", "CY", "CL", "Cl", "Cm", "Cn", "alpha_deg")
    wind = c.CoefficientInput("components", c.FrameChoice("wind"))
    assert wind.required_columns == ("CX", "CY", "CZ", "Cl", "Cm", "Cn", "alpha_deg", "beta_deg")
    assert wind.frame_choice == c.FrameChoice("wind")


def test_coefficient_inputs_build_the_api_coefficients() -> None:
    cases = _cases(
        CA=[0.1], CD=[0.2], CX=[-0.1], CY=[0.0], CN=[1.0], CL=[0.9], CZ=[-1.0],
        Cl=[0.0], Cm=[-0.05], Cn=[0.0], alpha_deg=[4.0],
    )  # fmt: skip
    axial = AXIAL_NORMAL.build(cases, REFERENCE)
    np.testing.assert_array_equal(axial.force, [[-0.1, 0.0, -1.0]])
    assert axial.frame.kind == "body"
    lift = LIFT_DRAG.build(cases, REFERENCE)
    np.testing.assert_array_equal(lift.force, [[-0.2, 0.0, -0.9]])
    assert lift.frame.kind == "stability"
    components = c.CoefficientInput("components", c.FrameChoice("axes", "BRU")).build(
        cases, REFERENCE
    )
    np.testing.assert_array_equal(components.force, [[-0.1, 0.0, -1.0]])
    assert components.frame.name == "BRU"
    assert components.reference is REFERENCE


# Calculations: reference values


def _transform(
    source: c.CoefficientInput,
    cases: dict[str, np.ndarray],
    target: c.FrameChoice | None = None,
    transfer: c.PointTransfer | None = None,
    new_reference: ReferenceQuantities | None = None,
) -> c.Columns:
    return c.transform_cases(
        source, cases, REFERENCE, target=target, transfer=transfer, new_reference=new_reference
    )


def test_frame_change_gives_lift_and_drag() -> None:
    # Anderson, Fundamentals of Aerodynamics, Sec. 1.5, at alpha = 30 deg:
    # CD = CN sin(a) + CA cos(a) = 0.5866025, CL = CN cos(a) - CA sin(a) = 0.8160254.
    cases = c.single_case({"CA": 0.1, "CY": 0, "CN": 1, "Cl": 0, "Cm": 0, "Cn": 0, "alpha_deg": 30})
    result = _transform(AXIAL_NORMAL, cases, c.FrameChoice("stability"))
    assert list(result) == ["CX", "CY", "CZ", "Cl", "Cm", "Cn", "CD", "CL"]
    np.testing.assert_allclose(result["CD"], [0.1 * np.sqrt(3) / 2 + 0.5], rtol=1e-15)
    np.testing.assert_allclose(result["CL"], [np.sqrt(3) / 2 - 0.05], rtol=1e-15)


def test_frame_change_round_trip_over_a_batch() -> None:
    cases = _cases(
        CA=[0.02, 0.03], CY=[0.01, -0.02], CN=[0.1, 0.5], Cl=[0.001, 0.0],
        Cm=[-0.01, -0.05], Cn=[0.002, 0.004], alpha_deg=[2.0, 10.0], beta_deg=[1.0, -3.0],
    )  # fmt: skip
    wind = _transform(AXIAL_NORMAL, cases, c.FrameChoice("wind"))
    assert list(wind) == ["CX", "CY", "CZ", "Cl", "Cm", "Cn"]
    back = _transform(
        c.CoefficientInput("components", c.FrameChoice("wind")),
        {**cases, **wind},
        c.FrameChoice("body"),
    )
    for name in ("CA", "CY", "CN", "Cl", "Cm", "Cn"):
        np.testing.assert_allclose(back[name], cases[name], atol=1e-15)


def test_moment_transfer_and_reference_change() -> None:
    # ADR 0002: CN = 1 moved to a point 0.5 m aft (given in BRU) with l_pitch = 2 m
    # gives Delta Cm = +0.25.
    transfer = c.PointTransfer((0.0, 0.0, 0.0), (0.5, 0.0, 0.0), "BRU")
    moved = _transform(BODY_COMPONENTS, _body(CZ=-1.0), transfer=transfer)
    np.testing.assert_array_equal(moved["Cm"], [0.25])
    assert {"CA", "CN"} <= set(moved)
    # ADR 0002: S 2 -> 4 and l_pitch 2 -> 0.5 give CX' = CX / 2 and Cm' = 2 Cm.
    target = ReferenceQuantities(
        area_m2=4.0, length_roll_m=10.0, length_pitch_m=0.5, length_yaw_m=10.0
    )
    renormalized = _transform(BODY_COMPONENTS, _body(CX=1.0, Cm=1.0), new_reference=target)
    np.testing.assert_array_equal([renormalized["CX"], renormalized["Cm"]], [[0.5], [2.0]])
    unchanged = _transform(BODY_COMPONENTS, _body(CX=1.0))
    np.testing.assert_array_equal(unchanged["CX"], [1.0])


def test_all_three_changes_together() -> None:
    # CA = 0.1, CN = 1 moved 0.5 m aft (BRU) with l_pitch = 2 m: Cm = 0.25 (ADR 0002).
    # In stability axes at alpha = 30 deg the pitch axis is unchanged, and CD, CL are
    # the Anderson Sec. 1.5 values above. With S' = 4 and l_pitch' = 0.5 (ADR 0002):
    # CD' = CD / 2, CL' = CL / 2, and Cm' = 0.25 * (2 * 2) / (4 * 0.5) = 0.5.
    cases = c.single_case({"CA": 0.1, "CY": 0, "CN": 1, "Cl": 0, "Cm": 0, "Cn": 0, "alpha_deg": 30})
    result = _transform(
        AXIAL_NORMAL,
        cases,
        c.FrameChoice("stability"),
        c.PointTransfer((0.0, 0.0, 0.0), (0.5, 0.0, 0.0), "BRU"),
        ReferenceQuantities(area_m2=4.0, length_roll_m=10.0, length_pitch_m=0.5, length_yaw_m=10.0),
    )
    np.testing.assert_allclose(
        [result["CD"], result["CL"], result["Cm"]],
        [[0.5866025403784439 / 2], [0.8160254037844386 / 2], [0.5]],
        rtol=1e-14,
    )


def test_control_surface_components() -> None:
    # ADR 0003 verification: right tail, upward force CZ = -0.01 acting 0.1 m aft of
    # the hinge and 0.5 m outboard of the root, moments about the body origin:
    # CN_s = 0.1, Ch = -0.04, CB = 0.05.
    surface = ControlSurface(
        hinge_start_m=np.array([-5.0, 0.2, 0.0]),
        hinge_end_m=np.array([-5.0, 1.2, 0.0]),
        trailing_edge_direction=np.array([-1.0, 0.0, 0.0]),
        points_frame=Frame.body(),
        area_m2=0.2,
        hinge_moment_length_m=0.25,
        bending_moment_length_m=1.0,
    )
    moment = np.cross([-5.1, 0.7, 0.0], [0.0, 0.0, -0.01]) / REFERENCE.moment_lengths_m
    cases = _body(CZ=-0.01, Cl=moment[0], Cm=moment[1]) | c.single_case({"deflection_deg": 0.0})
    assert c.surface_columns(BODY_COMPONENTS)[-1] == "deflection_deg"
    result = c.surface_components(BODY_COMPONENTS, cases, REFERENCE, surface, (0.0, 0.0, 0.0))
    np.testing.assert_allclose(
        [result["CN_s"], result["Ch"], result["CB"]], [[0.1], [-0.04], [0.05]], rtol=1e-14
    )
    np.testing.assert_array_equal(result["CZ_h"], result["CN_s"])
    assert list(result)[3:] == list(c.HINGE_COLUMNS)


def test_loads_hand_values_and_inverse() -> None:
    # q = 0.5 * 1.225 * 50^2 = 1531.25 Pa (ISA sea level, U.S. Standard Atmosphere,
    # 1976), q S = 3062.5 N: Fx = -0.1 q S, Fz = -q S, My = -0.05 q S l_pitch.
    cases = c.single_case(
        {"CA": 0.1, "CY": 0, "CN": 1, "Cl": 0, "Cm": -0.05, "Cn": 0, "dynamic_pressure_pa": 1531.25}
    )
    assert c.loads_columns(AXIAL_NORMAL)[-1] == "dynamic_pressure_pa"
    loads = c.coefficients_to_loads(AXIAL_NORMAL, cases, REFERENCE)
    assert list(loads) == list(c.LOAD_COLUMNS)
    np.testing.assert_allclose(
        [loads[name][0] for name in c.LOAD_COLUMNS],
        [-306.25, 0.0, -3062.5, 0.0, -306.25, 0.0],
        rtol=1e-15,
    )
    body = c.FrameChoice("body")
    assert c.coefficient_from_loads_columns(body) == (*c.LOAD_COLUMNS, "dynamic_pressure_pa")
    restored = c.loads_to_coefficients(body, {**cases, **loads}, REFERENCE)
    np.testing.assert_allclose(
        [restored["CA"], restored["CN"], restored["Cm"]], [[0.1], [1.0], [-0.05]], rtol=1e-15
    )


def test_loads_in_stability_axes_give_lift_and_drag() -> None:
    # Fx_stability = -q S CD: q S = 1000 N with Fx = -100 N and Fz = -800 N.
    stability = c.FrameChoice("stability")
    assert c.coefficient_from_loads_columns(stability)[-2:] == (
        "alpha_deg",
        "dynamic_pressure_pa",
    )
    loads = dict.fromkeys(c.LOAD_COLUMNS, 0.0) | {"Fx_N": -100.0, "Fz_N": -800.0}
    cases = c.single_case(loads | {"alpha_deg": 5.0, "dynamic_pressure_pa": 500.0})
    result = c.loads_to_coefficients(stability, cases, REFERENCE)
    np.testing.assert_allclose([result["CD"], result["CL"]], [[0.1], [0.8]], rtol=1e-15)


def test_columns_are_merged_without_repeats() -> None:
    assert c.transform_columns(LIFT_DRAG, c.FrameChoice("wind")) == (
        "CD", "CY", "CL", "Cl", "Cm", "Cn", "alpha_deg", "beta_deg",
    )  # fmt: skip
    assert c.transform_columns(LIFT_DRAG, None) == LIFT_DRAG.required_columns


def test_errors_from_the_api_propagate() -> None:
    with pytest.raises(ValueError, match="axes"):
        _transform(BODY_COMPONENTS, _body(), c.FrameChoice("axes", "FRU"))
    cases = _body() | c.single_case({"dynamic_pressure_pa": 0.0})
    with pytest.raises(ValueError, match="dynamic_pressure_pa"):
        c.coefficients_to_loads(BODY_COMPONENTS, cases, REFERENCE)


def test_coefficient_columns_follow_the_frame_kind() -> None:
    wind = AeroCoefficients(
        np.zeros(3), np.zeros(3), Frame.wind(alpha_deg=0, beta_deg=0), REFERENCE
    )
    columns = c.coefficient_columns(wind, 2)
    assert list(columns) == ["CX", "CY", "CZ", "Cl", "Cm", "Cn"]
    assert columns["CX"].shape == (2,)


# CSV files

REQUIRED = ("CX", "alpha_deg")


def test_read_cases_csv_keeps_extra_columns() -> None:
    data = "﻿case, CX ,alpha_deg\nA,0.5,2\n\nB,-1e-3,4.5\n".encode()
    table = c.read_cases_csv(data, REQUIRED)
    assert table.header == ("case", "CX", "alpha_deg")
    assert table.rows == (("A", "0.5", "2"), ("B", "-1e-3", "4.5"))
    np.testing.assert_array_equal(table.values["CX"], [0.5, -0.001])
    np.testing.assert_array_equal(table.values["alpha_deg"], [2.0, 4.5])


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "empty"),
        ("\n \n", "empty"),
        ("CX,alpha_deg\n", "no data rows"),
        ("CX,CX,alpha_deg\n1,1,1\n", "repeats"),
        ("CX\n1\n", "needs the columns: alpha_deg"),
        ("CX,alpha_deg\n1\n", "line 2 has 1 values, expected 2"),
        ("CX,alpha_deg\n1,2\nx,3\n", "line 3, column CX: 'x' is not a number"),
        # Lines are counted in the file: blank lines count, and a quoted field
        # with a line break makes the next record start one line later.
        ("CX,alpha_deg\n0.5,2\n\nx,3\n", "line 4, column CX: 'x' is not a number"),
        ('CX,alpha_deg,note\n0.5,2,"a\nb"\nx,3,c\n', "line 4, column CX: 'x' is not"),
        ('CX,alpha_deg\n0.5,2\n\n"1\n",2,3\n', "line 4 has 3 values, expected 2"),
    ],
)
def test_read_cases_csv_rejects_bad_files(text: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        c.read_cases_csv(text, REQUIRED)


def test_write_results_csv_appends_results() -> None:
    table = c.read_cases_csv("case,CX,alpha_deg\nA,0.5,2\nB,1,3\n", REQUIRED)
    results = {"CX": np.array([0.25, 0.1]), "CD": np.array([1.0, 2.0])}
    assert c.write_results_csv(table, results) == (
        "case,CX,alpha_deg,CX_out,CD\nA,0.5,2,0.25,1.0\nB,1,3,0.1,2.0\n"
    )


def test_write_results_csv_keeps_result_names_unique() -> None:
    text = "case,CX,alpha_deg,CX_out,CX_out_out\nA,0.5,2,previous,older\n"
    table = c.read_cases_csv(text, REQUIRED)
    results = {"CX": np.array([0.25]), "CD": np.array([1.0])}
    written = c.write_results_csv(table, results)
    assert written == (
        "case,CX,alpha_deg,CX_out,CX_out_out,CX_out_out_out,CD\nA,0.5,2,previous,older,0.25,1.0\n"
    )
    again = c.read_cases_csv(written, ("CX", "CX_out_out_out", "CD"))
    assert again.rows == (("A", "0.5", "2", "previous", "older", "0.25", "1.0"),)
    np.testing.assert_array_equal(again.values["CX_out_out_out"], [0.25])


def test_template_and_single_case() -> None:
    assert c.cases_csv_template(REQUIRED) == "CX,alpha_deg\n"
    single = c.single_case({"CX": 1, "alpha_deg": 2.5})
    np.testing.assert_array_equal(single["alpha_deg"], [2.5])
    assert single["CX"].dtype == np.float64
