import numpy as np
import pytest

from aerocoeff import AeroCoefficients, Frame, ReferenceQuantities
from aerocoeff.coefficients import LATERAL_ATOL
from aerocoeff.frames import FrameKind

# Unequal lengths so that any mixing of moment axes without length scaling shows up.
REFERENCE = ReferenceQuantities(
    area_m2=2.0, length_roll_m=10.0, length_pitch_m=2.0, length_yaw_m=7.0
)

RNG = np.random.default_rng(20261027)
ALPHA_RAD = RNG.uniform(-np.pi, np.pi, 200)
BETA_RAD = RNG.uniform(-np.pi / 2, np.pi / 2, 200)


def _random_body_coefficients(n: int = 200) -> AeroCoefficients:
    return AeroCoefficients(
        RNG.normal(size=(n, 3)), RNG.normal(size=(n, 3)), Frame.body(), REFERENCE
    )


def _random_rotations(n: int = 200) -> np.ndarray:
    q, r = np.linalg.qr(RNG.normal(size=(n, 3, 3)))
    q = q * np.sign(np.diagonal(r, axis1=-2, axis2=-1))[..., np.newaxis, :]
    rotations: np.ndarray = q * np.sign(np.linalg.det(q))[..., np.newaxis, np.newaxis]
    return rotations


# Frame construction


def test_wind_rotation_matches_adr_closed_form() -> None:
    # ADR 0001: C_wind<-body written out in closed form.
    a, b = ALPHA_RAD, BETA_RAD
    ca, sa, cb, sb = np.cos(a), np.sin(a), np.cos(b), np.sin(b)
    expected = np.stack(
        [
            np.stack([ca * cb, sb, sa * cb], -1),
            np.stack([-ca * sb, cb, -sa * sb], -1),
            np.stack([-sa, np.zeros_like(a), ca], -1),
        ],
        axis=-2,
    )
    frame = Frame.wind(alpha_rad=a, beta_rad=b)
    np.testing.assert_allclose(frame.rotation_from_body, expected, rtol=0, atol=1e-15)


def test_wind_x_axis_is_the_vehicle_velocity() -> None:
    # ADR 0001: V_body = V (cos a cos b, sin b, sin a cos b) maps to +x_wind.
    a, b = ALPHA_RAD, BETA_RAD
    velocity_body = np.stack([np.cos(a) * np.cos(b), np.sin(b), np.sin(a) * np.cos(b)], -1)
    frame = Frame.wind(alpha_rad=a, beta_rad=b)
    velocity_wind = (frame.rotation_from_body @ velocity_body[..., np.newaxis])[..., 0]
    np.testing.assert_allclose(velocity_wind, np.tile([1.0, 0.0, 0.0], (200, 1)), atol=1e-15)


def test_wind_frame_matches_panelsolver_beta_sin_freestream() -> None:
    # panelsolver "Coordinate and attitude conventions", beta_sin:
    # Vhat_stl = (cos a cos b, -sin b, sin a cos b) is the freestream, i.e. -V_body,
    # and the STL frame is BRU.
    a, b = ALPHA_RAD, BETA_RAD
    vhat_stl = np.stack([np.cos(a) * np.cos(b), -np.sin(b), np.sin(a) * np.cos(b)], -1)
    stl_from_body = Frame.from_axes("BRU").rotation_from_body
    freestream_body = vhat_stl @ stl_from_body  # R^T @ v for each row vector v
    x_wind_in_body = Frame.wind(alpha_rad=a, beta_rad=b).rotation_from_body[..., 0, :]
    np.testing.assert_allclose(freestream_body, -x_wind_in_body, atol=1e-15)


def test_degrees_and_radians_give_the_same_frames() -> None:
    by_rad = Frame.wind(alpha_rad=np.deg2rad(12.5), beta_rad=np.deg2rad(-4.0))
    by_deg = Frame.wind(alpha_deg=12.5, beta_deg=-4.0)
    np.testing.assert_array_equal(by_rad.rotation_from_body, by_deg.rotation_from_body)
    np.testing.assert_array_equal(
        Frame.stability(alpha_deg=30.0).rotation_from_body,
        Frame.stability(alpha_rad=np.pi / 6).rotation_from_body,
    )


def test_angle_arrays_broadcast_into_frame_batches() -> None:
    frame = Frame.wind(alpha_deg=[[0.0], [5.0]], beta_deg=[0.0, 1.0, 2.0])
    assert frame.batch_shape == (2, 3)
    assert Frame.stability(alpha_deg=0.0).batch_shape == ()


@pytest.mark.parametrize(
    "kwargs",
    [{}, {"alpha_rad": 0.1, "alpha_deg": 5.0}],
)
def test_stability_requires_exactly_one_alpha(kwargs: dict[str, float]) -> None:
    with pytest.raises(TypeError, match="exactly one of alpha_rad and alpha_deg"):
        Frame.stability(**kwargs)


def test_wind_requires_exactly_one_beta() -> None:
    with pytest.raises(TypeError, match="exactly one of beta_rad and beta_deg"):
        Frame.wind(alpha_deg=1.0)


@pytest.mark.parametrize("value", [np.nan, np.inf, True])
def test_angles_are_validated_with_unit_in_name(value: float) -> None:
    with pytest.raises((TypeError, ValueError), match="alpha_deg"):
        Frame.stability(alpha_deg=value)


def test_frame_kinds() -> None:
    assert Frame.body().kind == "body"
    assert Frame.from_axes("BRU").kind == "custom"
    assert Frame.from_matrix(np.eye(3)).kind == "custom"
    assert Frame.stability(alpha_deg=3.0).kind == "stability"
    assert Frame.wind(alpha_deg=3.0, beta_deg=1.0).kind == "wind"


def test_declared_kinds_are_checked_against_the_rotation() -> None:
    roll = Frame.from_matrix(
        np.array([[1, 0, 0], [0, 0.6, 0.8], [0, -0.8, 0.6]])
    ).rotation_from_body
    pitch = Frame.stability(alpha_deg=20.0).rotation_from_body
    assert Frame(pitch, "pitch", "stability").kind == "stability"
    assert Frame(pitch, "pitch", "wind").kind == "wind"
    kinds: tuple[FrameKind, ...] = ("body", "stability", "wind")
    for kind in kinds:
        with pytest.raises(ValueError, match=f"not a {kind} frame"):
            Frame(roll, "roll", kind)
    with pytest.raises(ValueError, match="kind must be one of"):
        Frame(pitch, "pitch", "inertial")  # type: ignore[arg-type]


# Coefficient transformations: reference values


def test_lift_and_drag_from_axial_and_normal_force() -> None:
    # Anderson, Fundamentals of Aerodynamics, Sec. 1.5:
    # L = N cos a - A sin a, D = N sin a + A cos a; identical to panelsolver's CD/CL.
    body = AeroCoefficients.from_axial_normal(
        CA=0.1, CY=0.0, CN=1.0, Cl=0.0, Cm=0.0, Cn=0.0, reference=REFERENCE
    )
    stability = body.to_frame(Frame.stability(alpha_deg=30.0))
    np.testing.assert_allclose(stability.CD, 0.1 * np.sqrt(3) / 2 + 0.5, rtol=1e-15)
    np.testing.assert_allclose(stability.CL, np.sqrt(3) / 2 - 0.05, rtol=1e-15)
    np.testing.assert_allclose(stability.CD, 0.5866025403784439, rtol=1e-15)
    np.testing.assert_allclose(stability.CL, 0.8160254037844386, rtol=1e-15)


def test_normal_force_is_drag_at_ninety_degrees() -> None:
    # Derivation: at alpha = 90 deg, x_stability = +z_body and z_stability = -x_body,
    # so CD = -CZ_body = CN and CL = CX_body = -CA.
    body = AeroCoefficients.from_axial_normal(
        CA=0.2, CY=0.0, CN=1.5, Cl=0.0, Cm=0.0, Cn=0.0, reference=REFERENCE
    )
    stability = body.to_frame(Frame.stability(alpha_deg=90.0))
    np.testing.assert_allclose([stability.CD, stability.CL], [1.5, -0.2], atol=1e-15)


def test_moments_are_rotated_as_length_scaled_vectors() -> None:
    # ADR 0001 example: l_roll = 10, l_pitch = 2, Cm_body = 0.1, beta = 10 deg:
    # Cl_wind = 0.1 * 2 * sin(10 deg) / 10, not 0.1 * sin(10 deg).
    body = AeroCoefficients.from_components(
        CX=0, CY=0, CZ=0, Cl=0, Cm=0.1, Cn=0, reference=REFERENCE
    )
    wind = body.to_frame(Frame.wind(alpha_deg=0.0, beta_deg=10.0))
    np.testing.assert_allclose(wind.Cl, 0.003472963553338607, rtol=1e-14)
    np.testing.assert_allclose(wind.Cm, 0.1 * np.cos(np.deg2rad(10.0)), rtol=1e-15)
    np.testing.assert_allclose(wind.Cn, 0.0, atol=1e-18)


def test_bru_flips_x_and_z_components() -> None:
    # panelsolver STL-to-body mapping (x, y, z)_body = (-x, +y, -z)_stl applies to
    # forces and, as a proper rotation, to moments.
    body = AeroCoefficients.from_components(
        CX=1.0, CY=2.0, CZ=3.0, Cl=0.1, Cm=0.2, Cn=0.3, reference=REFERENCE
    )
    stl = body.to_frame(Frame.from_axes("BRU"))
    np.testing.assert_array_equal(stl.force, [-1.0, 2.0, -3.0])
    np.testing.assert_allclose(stl.moment, [-0.1, 0.2, -0.3], rtol=1e-15)
    assert stl.frame.name == "BRU"


def test_lift_is_the_same_in_stability_and_wind_axes() -> None:
    # ADR 0001: CL = -CZ_stability = -CZ_wind.
    body = _random_body_coefficients()
    stability = body.to_frame(Frame.stability(alpha_rad=ALPHA_RAD))
    wind = body.to_frame(Frame.wind(alpha_rad=ALPHA_RAD, beta_rad=BETA_RAD))
    np.testing.assert_allclose(stability.CL, -wind.CZ, atol=1e-14)


def test_wind_drag_relation() -> None:
    # ADR 0001: -CX_wind = cos(beta) CD - sin(beta) CY.
    body = _random_body_coefficients()
    stability = body.to_frame(Frame.stability(alpha_rad=ALPHA_RAD))
    wind = body.to_frame(Frame.wind(alpha_rad=ALPHA_RAD, beta_rad=BETA_RAD))
    expected = np.cos(BETA_RAD) * stability.CD - np.sin(BETA_RAD) * stability.CY
    np.testing.assert_allclose(-wind.CX, expected, atol=1e-14)


# Coefficient transformations: round trips


@pytest.mark.parametrize(
    "target",
    [
        Frame.stability(alpha_rad=ALPHA_RAD),
        Frame.wind(alpha_rad=ALPHA_RAD, beta_rad=BETA_RAD),
        Frame.from_axes("BRU"),
        Frame.from_matrix(_random_rotations()),
    ],
    ids=["stability", "wind", "BRU", "random"],
)
def test_round_trip_through_frame(target: Frame) -> None:
    body = _random_body_coefficients()
    back = body.to_frame(target).to_body()
    assert back.frame.kind == "body"
    np.testing.assert_allclose(back.force, body.force, rtol=0, atol=1e-13)
    np.testing.assert_allclose(back.moment, body.moment, rtol=0, atol=1e-13)


def test_direct_and_chained_transformations_agree() -> None:
    body = _random_body_coefficients()
    stability = Frame.stability(alpha_rad=ALPHA_RAD)
    wind = Frame.wind(alpha_rad=ALPHA_RAD, beta_rad=BETA_RAD)
    direct = body.to_frame(wind)
    chained = body.to_frame(stability).to_frame(wind)
    np.testing.assert_allclose(chained.force, direct.force, rtol=0, atol=1e-13)
    np.testing.assert_allclose(chained.moment, direct.moment, rtol=0, atol=1e-13)


def test_transformations_preserve_length_scaled_magnitudes() -> None:
    body = _random_body_coefficients()
    wind = body.to_frame(Frame.wind(alpha_rad=ALPHA_RAD, beta_rad=BETA_RAD))
    lengths = REFERENCE.moment_lengths_m
    np.testing.assert_allclose(
        np.linalg.norm(wind.force, axis=-1), np.linalg.norm(body.force, axis=-1), rtol=1e-13
    )
    np.testing.assert_allclose(
        np.linalg.norm(wind.moment * lengths, axis=-1),
        np.linalg.norm(body.moment * lengths, axis=-1),
        rtol=1e-13,
    )


def test_scalar_coefficients_broadcast_over_frame_batches() -> None:
    body = AeroCoefficients.from_axial_normal(
        CA=0.1, CY=0.0, CN=1.0, Cl=0.0, Cm=0.0, Cn=0.0, reference=REFERENCE
    )
    alpha_deg = np.array([0.0, 30.0, 90.0])
    stability = body.to_frame(Frame.stability(alpha_deg=alpha_deg))
    assert stability.force.shape == (3, 3)
    alpha = np.deg2rad(alpha_deg)
    np.testing.assert_allclose(stability.CD, 0.1 * np.cos(alpha) + np.sin(alpha), atol=1e-15)


# Named quantities


def test_axial_normal_round_trip() -> None:
    body = AeroCoefficients.from_axial_normal(
        CA=0.3, CY=-0.1, CN=1.2, Cl=0.01, Cm=-0.02, Cn=0.03, reference=REFERENCE
    )
    np.testing.assert_array_equal([body.CX, body.CY, body.CZ], [-0.3, -0.1, -1.2])
    np.testing.assert_array_equal([body.CA, body.CN], [0.3, 1.2])


def test_named_quantities_require_their_frame() -> None:
    body = _random_body_coefficients(1)
    stability = body.to_frame(Frame.stability(alpha_deg=5.0))
    with pytest.raises(ValueError, match="CD is defined in stability axes"):
        _ = body.CD
    with pytest.raises(ValueError, match="CL is defined in stability axes"):
        _ = body.to_frame(Frame.wind(alpha_deg=5.0, beta_deg=0.0)).CL
    with pytest.raises(ValueError, match="CA is defined in body axes"):
        _ = stability.CA
    with pytest.raises(ValueError, match="CN is defined in body axes"):
        _ = body.to_frame(Frame.from_matrix(np.eye(3))).CN


def test_to_frame_requires_a_frame() -> None:
    with pytest.raises(TypeError, match="Frame"):
        _random_body_coefficients(1).to_frame("FRD")  # type: ignore[arg-type]


# Array and stability-axis inputs


def test_from_components_array_splits_six_columns_in_order() -> None:
    table = np.array([[1.0, 2.0, 3.0, 0.1, 0.2, 0.3], [4.0, 5.0, 6.0, 0.4, 0.5, 0.6]])
    coefficients = AeroCoefficients.from_components_array(table, reference=REFERENCE)
    assert coefficients.frame.kind == "body"
    np.testing.assert_array_equal(coefficients.CX, [1.0, 4.0])
    np.testing.assert_array_equal(coefficients.Cn, [0.3, 0.6])
    np.testing.assert_array_equal(coefficients.to_components_array(), table)


def test_from_components_array_keeps_an_explicit_frame_and_batches() -> None:
    frame = Frame.stability(alpha_deg=[[0.0], [10.0]])
    table = RNG.normal(size=(2, 4, 6))
    coefficients = AeroCoefficients.from_components_array(table, reference=REFERENCE, frame=frame)
    assert coefficients.frame is frame
    assert coefficients.force.shape == (2, 4, 3)
    np.testing.assert_array_equal(coefficients.to_components_array(), table)


def test_array_round_trip_through_frames() -> None:
    table = RNG.normal(size=(200, 6))
    body = AeroCoefficients.from_components_array(table, reference=REFERENCE)
    wind = body.to_frame(Frame.wind(alpha_rad=ALPHA_RAD, beta_rad=BETA_RAD))
    back = AeroCoefficients.from_components_array(
        wind.to_components_array(), reference=REFERENCE, frame=wind.frame
    )
    np.testing.assert_allclose(back.to_body().to_components_array(), table, rtol=0, atol=1e-13)


@pytest.mark.parametrize("shape", [(), (6, 3), (5,)])
def test_from_components_array_requires_six_columns(shape: tuple[int, ...]) -> None:
    with pytest.raises(ValueError, match=r"\(\.\.\., 6\)"):
        AeroCoefficients.from_components_array(np.zeros(shape), reference=REFERENCE)


def test_from_components_array_validates_values() -> None:
    with pytest.raises(ValueError, match="array must be finite"):
        AeroCoefficients.from_components_array([0, 0, 0, 0, 0, np.nan], reference=REFERENCE)


def test_to_components_array_returns_a_new_writable_array() -> None:
    coefficients = _random_body_coefficients(3)
    array = coefficients.to_components_array()
    array[0, 0] = 99.0
    assert coefficients.CX[0] != 99.0


def test_from_lift_drag_inverts_the_anderson_example() -> None:
    # Anderson, Fundamentals of Aerodynamics, Sec. 1.5, inverted:
    # A = D cos a - L sin a, N = D sin a + L cos a.
    stability = AeroCoefficients.from_lift_drag(
        CD=0.5866025403784439,
        CY=0.0,
        CL=0.8160254037844386,
        Cl=0.0,
        Cm=0.0,
        Cn=0.0,
        reference=REFERENCE,
        alpha_deg=30.0,
    )
    assert stability.frame.kind == "stability"
    np.testing.assert_array_equal(
        [stability.CX, stability.CZ], [-0.5866025403784439, -0.8160254037844386]
    )
    body = stability.to_body()
    np.testing.assert_allclose([body.CA, body.CN], [0.1, 1.0], rtol=1e-14)


def test_from_lift_drag_moments_are_in_stability_axes() -> None:
    # Derivation: at alpha = 90 deg, x_stability = +z_body, so a stability roll
    # moment is a body yaw moment: Cn = Cl_stability * l_roll / l_yaw = 0.1 * 10 / 7.
    stability = AeroCoefficients.from_lift_drag(
        CD=0.0, CY=0.0, CL=0.0, Cl=0.1, Cm=0.0, Cn=0.0, reference=REFERENCE, alpha_deg=90.0
    )
    body = stability.to_body()
    np.testing.assert_allclose(body.moment, [0.0, 0.0, 0.1 * 10.0 / 7.0], atol=1e-16)


def test_from_lift_drag_round_trip_with_stability_output() -> None:
    body = _random_body_coefficients()
    stability = body.to_frame(Frame.stability(alpha_rad=ALPHA_RAD))
    rebuilt = AeroCoefficients.from_lift_drag(
        CD=stability.CD,
        CY=stability.CY,
        CL=stability.CL,
        Cl=stability.Cl,
        Cm=stability.Cm,
        Cn=stability.Cn,
        reference=REFERENCE,
        alpha_rad=ALPHA_RAD,
    )
    np.testing.assert_allclose(
        rebuilt.to_body().to_components_array(), body.to_components_array(), rtol=0, atol=1e-13
    )


def test_from_lift_drag_requires_exactly_one_alpha() -> None:
    with pytest.raises(TypeError, match="exactly one of alpha_rad and alpha_deg"):
        AeroCoefficients.from_lift_drag(CD=0, CY=0, CL=0, Cl=0, Cm=0, Cn=0, reference=REFERENCE)


def test_from_lift_drag_validates_by_name() -> None:
    with pytest.raises(ValueError, match="CL must be finite"):
        AeroCoefficients.from_lift_drag(
            CD=0, CY=0, CL=np.inf, Cl=0, Cm=0, Cn=0, reference=REFERENCE, alpha_deg=0.0
        )


# Named-column arrays


def test_axial_normal_array_columns() -> None:
    table = np.array([[0.3, -0.1, 1.2, 0.01, -0.02, 0.03], [0.4, 0.0, 1.5, 0.0, -0.04, 0.0]])
    body = AeroCoefficients.from_axial_normal_array(table, reference=REFERENCE)
    assert body.frame.kind == "body"
    # ADR 0001: CX = -CA, CZ = -CN.
    np.testing.assert_array_equal(body.to_components_array()[:, [0, 2]], -table[:, [0, 2]])
    np.testing.assert_array_equal(
        body.to_components_array()[:, [1, 3, 4, 5]], table[:, [1, 3, 4, 5]]
    )
    np.testing.assert_array_equal(body.to_axial_normal_array(), table)


def test_lift_drag_array_matches_from_lift_drag() -> None:
    # Anderson example inverted, as in test_from_lift_drag_inverts_the_anderson_example.
    table = np.array([0.5866025403784439, 0.0, 0.8160254037844386, 0.0, 0.0, 0.0])
    stability = AeroCoefficients.from_lift_drag_array(table, reference=REFERENCE, alpha_deg=30.0)
    assert stability.frame.kind == "stability"
    np.testing.assert_array_equal(stability.to_lift_drag_array(), table)
    np.testing.assert_allclose(stability.to_body().to_axial_normal_array()[[0, 2]], [0.1, 1.0])


def test_named_column_arrays_round_trip_through_frames() -> None:
    body = _random_body_coefficients()
    axial_normal = body.to_axial_normal_array()
    lift_drag = body.to_frame(Frame.stability(alpha_rad=ALPHA_RAD)).to_lift_drag_array()
    rebuilt = AeroCoefficients.from_lift_drag_array(
        lift_drag, reference=REFERENCE, alpha_rad=ALPHA_RAD
    ).to_body()
    np.testing.assert_allclose(rebuilt.to_axial_normal_array(), axial_normal, rtol=0, atol=1e-13)
    again = AeroCoefficients.from_axial_normal_array(axial_normal, reference=REFERENCE)
    np.testing.assert_array_equal(again.to_components_array(), body.to_components_array())


def test_lift_drag_table_differs_from_frame_component_table() -> None:
    # from_components_array reads stability columns as CX, CY, CZ = -CD, CY, -CL (ADR 0001).
    stability = _random_body_coefficients().to_frame(Frame.stability(alpha_rad=ALPHA_RAD))
    lift_drag = stability.to_lift_drag_array()
    components = stability.to_components_array()
    np.testing.assert_array_equal(components[:, [0, 2]], -lift_drag[:, [0, 2]])
    np.testing.assert_array_equal(components[:, [1, 3, 4, 5]], lift_drag[:, [1, 3, 4, 5]])


def test_named_column_arrays_require_their_frame() -> None:
    body = _random_body_coefficients(2)
    stability = body.to_frame(Frame.stability(alpha_deg=5.0))
    with pytest.raises(ValueError, match="lift-drag array is defined in stability axes"):
        body.to_lift_drag_array()
    with pytest.raises(ValueError, match="axial-normal array is defined in body axes"):
        stability.to_axial_normal_array()


@pytest.mark.parametrize("shape", [(), (2, 3), (5,)])
def test_named_column_arrays_require_six_columns(shape: tuple[int, ...]) -> None:
    with pytest.raises(ValueError, match=r"\(\.\.\., 6\)"):
        AeroCoefficients.from_axial_normal_array(np.zeros(shape), reference=REFERENCE)
    with pytest.raises(ValueError, match=r"\(\.\.\., 6\)"):
        AeroCoefficients.from_lift_drag_array(np.zeros(shape), reference=REFERENCE, alpha_deg=0.0)


def test_lift_drag_array_requires_exactly_one_alpha() -> None:
    with pytest.raises(TypeError, match="exactly one of alpha_rad and alpha_deg"):
        AeroCoefficients.from_lift_drag_array(np.zeros(6), reference=REFERENCE)


def test_reference_lengths_follow_axis_positions_in_permuted_frames() -> None:
    # ADR 0001 clarification: in RDF the x axis is the right wing, so a body pitching
    # moment Cm = 0.1 (l_pitch = 0.5) becomes the x-axis coefficient 0.1 * 0.5 / 4
    # (l_roll = 4). The physical moment, coefficient times length, is unchanged.
    reference = ReferenceQuantities(
        area_m2=2.0, length_roll_m=4.0, length_pitch_m=0.5, length_yaw_m=4.0
    )
    body = AeroCoefficients.from_components(
        CX=0, CY=0, CZ=0, Cl=0, Cm=0.1, Cn=0, reference=reference
    )
    rdf = body.to_frame(Frame.from_axes("RDF"))
    assert rdf.reference is reference
    np.testing.assert_allclose(rdf.moment, [0.0125, 0.0, 0.0], atol=1e-17)
    np.testing.assert_allclose(rdf.Cl * 4.0, body.Cm * 0.5, rtol=1e-15)
    np.testing.assert_allclose(rdf.to_body().moment, [0.0, 0.1, 0.0], atol=1e-17)


# Longitudinal three-component arrays


def test_longitudinal_anderson_example() -> None:
    # Anderson, Fundamentals of Aerodynamics, Sec. 1.5, as in
    # test_lift_and_drag_from_axial_and_normal_force. Cm is unchanged because the
    # stability frame shares the body y axis (ADR 0001).
    body = AeroCoefficients.from_longitudinal_axial_normal(
        CA=0.1, CN=1.0, Cm=-0.05, reference=REFERENCE
    )
    np.testing.assert_array_equal(body.to_components_array(), [-0.1, 0, -1.0, 0, -0.05, 0])
    stability = body.to_frame(Frame.stability(alpha_deg=30.0))
    np.testing.assert_allclose(
        stability.to_longitudinal_lift_drag_array(),
        [0.5866025403784439, 0.8160254037844386, -0.05],
        rtol=1e-15,
        atol=0,
    )


def test_longitudinal_arrays_match_six_component_entry_points() -> None:
    table = np.array([[0.5866025403784439, 0.8160254037844386, -0.05], [0.02, 0.3, 0.01]])
    stability = AeroCoefficients.from_longitudinal_lift_drag_array(
        table, reference=REFERENCE, alpha_deg=30.0
    )
    assert stability.frame.kind == "stability"
    np.testing.assert_array_equal(stability.to_lift_drag_array()[:, [0, 2, 4]], table)
    np.testing.assert_array_equal(stability.to_lift_drag_array()[:, [1, 3, 5]], 0.0)
    np.testing.assert_array_equal(stability.to_longitudinal_lift_drag_array(), table)
    body = AeroCoefficients.from_longitudinal_axial_normal_array(table, reference=REFERENCE)
    assert body.frame.kind == "body"
    np.testing.assert_array_equal(body.to_axial_normal_array()[:, [0, 2, 4]], table)
    np.testing.assert_array_equal(body.to_longitudinal_axial_normal_array(), table)


def test_longitudinal_arrays_round_trip_through_frames() -> None:
    axial_normal = RNG.normal(size=(200, 3))
    body = AeroCoefficients.from_longitudinal_axial_normal_array(axial_normal, reference=REFERENCE)
    lift_drag = body.to_frame(
        Frame.stability(alpha_rad=ALPHA_RAD)
    ).to_longitudinal_lift_drag_array()
    rebuilt = AeroCoefficients.from_longitudinal_lift_drag_array(
        lift_drag, reference=REFERENCE, alpha_rad=ALPHA_RAD
    ).to_body()
    np.testing.assert_allclose(
        rebuilt.to_longitudinal_axial_normal_array(), axial_normal, rtol=0, atol=1e-13
    )


def test_longitudinal_output_accepts_rounding_after_leaving_the_plane() -> None:
    # Through wind axes with beta = 10 deg and back, lateral components return to
    # zero up to rounding, which LATERAL_ATOL accepts.
    axial_normal = RNG.normal(size=(200, 3))
    body = AeroCoefficients.from_longitudinal_axial_normal_array(axial_normal, reference=REFERENCE)
    wind = body.to_frame(Frame.wind(alpha_rad=ALPHA_RAD, beta_deg=10.0))
    assert np.max(np.abs(wind.CY)) > 1e-3
    np.testing.assert_allclose(
        wind.to_body().to_longitudinal_axial_normal_array(), axial_normal, rtol=0, atol=1e-13
    )


@pytest.mark.parametrize("column", [1, 3, 5])  # CY, Cl, Cn
def test_longitudinal_output_rejects_lateral_components(column: int) -> None:
    components = np.zeros(6)
    components[column] = 2 * LATERAL_ATOL
    body = AeroCoefficients.from_components_array(components, reference=REFERENCE)
    with pytest.raises(ValueError, match="CY, Cl, and Cn within 1e-12 of zero"):
        body.to_longitudinal_axial_normal_array()
    stability = body.to_frame(Frame.stability(alpha_deg=0.0))
    with pytest.raises(ValueError, match="largest magnitude is 2e-12"):
        stability.to_longitudinal_lift_drag_array()


def test_longitudinal_arrays_require_their_frame() -> None:
    body = AeroCoefficients.from_longitudinal_axial_normal(
        CA=0.1, CN=1.0, Cm=0.0, reference=REFERENCE
    )
    with pytest.raises(ValueError, match="longitudinal lift-drag array is defined in stability"):
        body.to_longitudinal_lift_drag_array()
    with pytest.raises(ValueError, match="longitudinal axial-normal array is defined in body"):
        body.to_frame(Frame.stability(alpha_deg=5.0)).to_longitudinal_axial_normal_array()


@pytest.mark.parametrize("shape", [(), (2, 6), (5,)])
def test_longitudinal_arrays_require_three_columns(shape: tuple[int, ...]) -> None:
    with pytest.raises(ValueError, match=r"\(\.\.\., 3\)"):
        AeroCoefficients.from_longitudinal_axial_normal_array(np.zeros(shape), reference=REFERENCE)
    with pytest.raises(ValueError, match=r"\(\.\.\., 3\)"):
        AeroCoefficients.from_longitudinal_lift_drag_array(
            np.zeros(shape), reference=REFERENCE, alpha_deg=0.0
        )


def test_longitudinal_entry_points_validate_by_name() -> None:
    with pytest.raises(ValueError, match="CN must be finite"):
        AeroCoefficients.from_longitudinal_axial_normal(
            CA=0.0, CN=np.nan, Cm=0.0, reference=REFERENCE
        )
    with pytest.raises(TypeError, match="exactly one of alpha_rad and alpha_deg"):
        AeroCoefficients.from_longitudinal_lift_drag(CD=0.0, CL=0.0, Cm=0.0, reference=REFERENCE)
