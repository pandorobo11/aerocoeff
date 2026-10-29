import math

import numpy as np
import pytest

from aerocoeff import AeroCoefficients, Frame, ReferenceQuantities

# Unequal lengths so that any mixing of moment axes or lengths shows up.
REFERENCE = ReferenceQuantities(
    area_m2=2.0, length_roll_m=10.0, length_pitch_m=2.0, length_yaw_m=7.0
)
BODY = Frame.body()

# q = 0.5 rho V^2 with the ISA sea-level density rho = 1.225 kg/m^3 (U.S. Standard
# Atmosphere, 1976) and V = 50 m/s.
SEA_LEVEL_Q_PA = 1531.25

RNG = np.random.default_rng(20261029)


def _random_rotations(n: int) -> np.ndarray:
    q, r = np.linalg.qr(RNG.normal(size=(n, 3, 3)))
    q = q * np.sign(np.diagonal(r, axis1=-2, axis2=-1))[..., np.newaxis, :]
    rotations: np.ndarray = q * np.sign(np.linalg.det(q))[..., np.newaxis, np.newaxis]
    return rotations


def _hand_coefficients() -> AeroCoefficients:
    return AeroCoefficients.from_components(
        CX=-0.05, CY=0.02, CZ=-0.8, Cl=0.01, Cm=-0.1, Cn=0.004, reference=REFERENCE
    )


# Hand values: F = q S C_F and M = q S (l C_M) per axis (ADR 0001; Anderson,
# Fundamentals of Aerodynamics, Sec. 1.5). Here q S = 1531.25 * 2 = 3062.5 N.
HAND_LOADS = [
    -0.05 * 3062.5,  # Fx = -153.125 N
    0.02 * 3062.5,  # Fy = 61.25 N
    -0.8 * 3062.5,  # Fz = -2450 N
    0.01 * 3062.5 * 10.0,  # Mx = 306.25 N m, divided by l_roll
    -0.1 * 3062.5 * 2.0,  # My = -612.5 N m, divided by l_pitch
    0.004 * 3062.5 * 7.0,  # Mz = 85.75 N m, divided by l_yaw
]


def test_to_loads_array_hand_values() -> None:
    loads = _hand_coefficients().to_loads_array(dynamic_pressure_pa=SEA_LEVEL_Q_PA)
    np.testing.assert_allclose(loads, [-153.125, 61.25, -2450.0, 306.25, -612.5, 85.75], rtol=1e-15)


def test_from_loads_array_hand_values() -> None:
    coefficients = AeroCoefficients.from_loads_array(
        HAND_LOADS, dynamic_pressure_pa=SEA_LEVEL_Q_PA, reference=REFERENCE
    )
    np.testing.assert_allclose(coefficients.force, [-0.05, 0.02, -0.8], rtol=1e-15)
    np.testing.assert_allclose(coefficients.moment, [0.01, -0.1, 0.004], rtol=1e-15)
    assert coefficients.frame.kind == "body"
    assert coefficients.reference is REFERENCE


def test_from_loads_array_keeps_the_given_frame() -> None:
    # Stability-axis loads: drag is -Fx_stability (ADR 0001), so Fx = -q S CD.
    frame = Frame.stability(alpha_deg=5.0)
    coefficients = AeroCoefficients.from_loads_array(
        [-306.25, 0.0, -3062.5, 0.0, 0.0, 0.0],
        dynamic_pressure_pa=SEA_LEVEL_Q_PA,
        reference=REFERENCE,
        frame=frame,
    )
    assert coefficients.frame is frame
    np.testing.assert_allclose(coefficients.CD, 0.1, rtol=1e-15)
    np.testing.assert_allclose(coefficients.CL, 1.0, rtol=1e-15)


def test_round_trips_with_batched_dynamic_pressure() -> None:
    frame = Frame.from_matrix(_random_rotations(50))
    coefficients = AeroCoefficients(
        RNG.normal(size=(50, 3)), RNG.normal(size=(50, 3)), frame, REFERENCE
    )
    q = RNG.uniform(10.0, 1e5, size=50)
    loads = coefficients.to_loads_array(dynamic_pressure_pa=q)
    restored = AeroCoefficients.from_loads_array(
        loads, dynamic_pressure_pa=q, reference=REFERENCE, frame=frame
    )
    np.testing.assert_allclose(restored.force, coefficients.force, rtol=1e-14, atol=1e-15)
    np.testing.assert_allclose(restored.moment, coefficients.moment, rtol=1e-14, atol=1e-15)
    np.testing.assert_allclose(
        restored.to_loads_array(dynamic_pressure_pa=q), loads, rtol=1e-14, atol=1e-10
    )


def test_loads_rotate_as_plain_vectors() -> None:
    # ADR 0001 example: Cm_body = 0.1, l_pitch = 2, beta = 10 deg. With q = 1 and
    # S = 2, My_body = 0.4 N m, and C_wind<-body row 1 at alpha = 0 is
    # (cos(beta), sin(beta), 0), so Mx_wind = 0.4 sin(10 deg) = 0.06946 N m
    # (Cl_wind = 0.06946 / (2 * 10) = 0.00347, as in ADR 0001).
    coefficients = AeroCoefficients.from_components(
        CX=0, CY=0, CZ=0, Cl=0, Cm=0.1, Cn=0, reference=REFERENCE
    )
    wind = coefficients.to_frame(Frame.wind(alpha_deg=0.0, beta_deg=10.0))
    loads = wind.to_loads_array(dynamic_pressure_pa=1.0)
    np.testing.assert_allclose(
        loads[3:],
        [0.4 * math.sin(math.radians(10.0)), 0.4 * math.cos(math.radians(10.0)), 0.0],
        rtol=1e-15,
        atol=1e-17,
    )


def test_frame_change_commutes_with_dimensionalization() -> None:
    rotations = _random_rotations(200)
    coefficients = AeroCoefficients(
        RNG.normal(size=(200, 3)), RNG.normal(size=(200, 3)), BODY, REFERENCE
    )
    q = 1234.5
    body_loads = coefficients.to_loads_array(dynamic_pressure_pa=q)
    rotated = coefficients.to_frame(Frame.from_matrix(rotations)).to_loads_array(
        dynamic_pressure_pa=q
    )
    np.testing.assert_allclose(
        rotated[..., :3], (rotations @ body_loads[..., :3, np.newaxis])[..., 0], atol=1e-10
    )
    np.testing.assert_allclose(
        rotated[..., 3:], (rotations @ body_loads[..., 3:, np.newaxis])[..., 0], atol=1e-10
    )


def test_transfer_matches_the_dimensional_moment_transfer() -> None:
    # ADR 0002 sign check in newtons: CZ = -1 with q = 100 Pa and S = 2 m^2 is an
    # upward force of 200 N; 0.5 m ahead of the new point it pitches the nose up
    # by 200 * 0.5 = 100 N m (Anderson, Fundamentals of Aerodynamics, Sec. 1.6).
    coefficients = AeroCoefficients.from_components(
        CX=0, CY=0, CZ=-1.0, Cl=0, Cm=0, Cn=0, reference=REFERENCE
    )
    moved = coefficients.transfer_moment_reference(
        from_point_m=[0.0, 0.0, 0.0], to_point_m=[-0.5, 0.0, 0.0], points_frame=BODY
    )
    np.testing.assert_allclose(
        moved.to_loads_array(dynamic_pressure_pa=100.0),
        [0.0, 0.0, -200.0, 0.0, 100.0, 0.0],
        rtol=1e-15,
    )


def test_random_transfer_matches_moment_plus_displacement_cross_force() -> None:
    coefficients = AeroCoefficients(
        RNG.normal(size=(200, 3)), RNG.normal(size=(200, 3)), BODY, REFERENCE
    )
    from_point = RNG.normal(size=(200, 3))
    to_point = RNG.normal(size=(200, 3))
    q = 1234.5
    loads = coefficients.to_loads_array(dynamic_pressure_pa=q)
    moved = coefficients.transfer_moment_reference(
        from_point_m=from_point, to_point_m=to_point, points_frame=BODY
    ).to_loads_array(dynamic_pressure_pa=q)
    expected_moment = loads[..., 3:] + np.cross(from_point - to_point, loads[..., :3])
    np.testing.assert_allclose(moved[..., :3], loads[..., :3], rtol=1e-15)
    np.testing.assert_allclose(moved[..., 3:], expected_moment, atol=1e-9)


def test_dynamic_pressure_array_broadcasts_with_a_single_case() -> None:
    q = np.array([100.0, 200.0, 400.0])
    loads = _hand_coefficients().to_loads_array(dynamic_pressure_pa=q)
    assert loads.shape == (3, 6)
    np.testing.assert_allclose(loads[2], 4.0 * loads[0], rtol=1e-15)
    coefficients = AeroCoefficients.from_loads_array(
        np.ones(6), dynamic_pressure_pa=q, reference=REFERENCE
    )
    assert coefficients.force.shape == (3, 3)


def test_dynamic_pressure_must_broadcast_with_the_coefficients() -> None:
    coefficients = AeroCoefficients(np.zeros((2, 3)), np.zeros((2, 3)), BODY, REFERENCE)
    with pytest.raises(ValueError, match="dynamic_pressure_pa shape"):
        coefficients.to_loads_array(dynamic_pressure_pa=np.ones(3))
    with pytest.raises(ValueError, match="dynamic_pressure_pa shape"):
        AeroCoefficients.from_loads_array(
            np.zeros((2, 6)), dynamic_pressure_pa=np.ones(3), reference=REFERENCE
        )


def test_dynamic_pressure_must_broadcast_with_the_frame_batch() -> None:
    frame = Frame.stability(alpha_deg=[0.0, 5.0, 10.0])
    coefficients = AeroCoefficients(np.zeros(3), np.zeros(3), frame, REFERENCE)
    with pytest.raises(ValueError, match="dynamic_pressure_pa shape"):
        coefficients.to_loads_array(dynamic_pressure_pa=np.ones(2))


@pytest.mark.parametrize(
    ("value", "error"),
    [
        (0.0, ValueError),
        (-1.0, ValueError),
        ([100.0, 0.0], ValueError),
        (math.nan, ValueError),
        (math.inf, ValueError),
        (True, TypeError),
        ("100", TypeError),
    ],
)
def test_invalid_dynamic_pressure_is_rejected(value: object, error: type[Exception]) -> None:
    with pytest.raises(error, match="dynamic_pressure_pa"):
        _hand_coefficients().to_loads_array(dynamic_pressure_pa=value)  # type: ignore[arg-type]
    with pytest.raises(error, match="dynamic_pressure_pa"):
        AeroCoefficients.from_loads_array(
            np.zeros(6),
            dynamic_pressure_pa=value,  # type: ignore[arg-type]
            reference=REFERENCE,
        )


def test_from_loads_array_rejects_wrong_columns() -> None:
    with pytest.raises(ValueError, match=r"\(\.\.\., 6\)"):
        AeroCoefficients.from_loads_array(np.zeros(3), dynamic_pressure_pa=1.0, reference=REFERENCE)


def test_from_loads_array_rejects_a_non_reference() -> None:
    with pytest.raises(TypeError, match="reference"):
        AeroCoefficients.from_loads_array(
            np.zeros(6),
            dynamic_pressure_pa=1.0,
            reference=2.0,  # type: ignore[arg-type]
        )
