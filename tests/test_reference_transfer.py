import numpy as np
import pytest

from aerocoeff import AeroCoefficients, Frame, ReferenceQuantities

# Unequal lengths so that any mixing of moment axes without length scaling shows up.
REFERENCE = ReferenceQuantities(
    area_m2=2.0, length_roll_m=10.0, length_pitch_m=2.0, length_yaw_m=7.0
)
TARGET_REFERENCE = ReferenceQuantities(
    area_m2=0.3, length_roll_m=0.4, length_pitch_m=1.5, length_yaw_m=0.25
)
BODY = Frame.body()
BRU = Frame.from_axes("BRU")

RNG = np.random.default_rng(20261028)


def _random_body_coefficients(n: int = 200) -> AeroCoefficients:
    return AeroCoefficients(RNG.normal(size=(n, 3)), RNG.normal(size=(n, 3)), BODY, REFERENCE)


def _random_rotations(n: int = 200) -> np.ndarray:
    q, r = np.linalg.qr(RNG.normal(size=(n, 3, 3)))
    q = q * np.sign(np.diagonal(r, axis1=-2, axis2=-1))[..., np.newaxis, :]
    rotations: np.ndarray = q * np.sign(np.linalg.det(q))[..., np.newaxis, np.newaxis]
    return rotations


def _lift_force() -> AeroCoefficients:
    # CZ = -1: a normal force of 1 acting upward (ADR 0001).
    return AeroCoefficients.from_components(
        CX=0, CY=0, CZ=-1.0, Cl=0, Cm=0, Cn=0, reference=REFERENCE
    )


# Hand-checkable values (ADR 0002 verification table)


def test_aft_transfer_of_normal_force_pitches_nose_up() -> None:
    # ADR 0002, after Anderson Sec. 1.6: Cm_Q = Cm_P + CN (x_P - x_Q) / l_pitch with x
    # forward; CN = 1, Q 0.5 m aft of P, l_pitch = 2 m gives +0.25.
    moved = _lift_force().transfer_moment_reference(
        from_point_m=[0.0, 0.0, 0.0], to_point_m=[-0.5, 0.0, 0.0], points_frame=BODY
    )
    np.testing.assert_array_equal(moved.moment, [0.0, 0.25, 0.0])
    np.testing.assert_array_equal(moved.force, [0.0, 0.0, -1.0])
    assert moved.reference is REFERENCE


def test_points_in_bru_give_the_same_transfer() -> None:
    # ADR 0002: 0.5 m aft is +0.5 m along x_BRU, since x_body = -x_BRU (ADR 0001).
    moved = _lift_force().transfer_moment_reference(
        from_point_m=[0.0, 0.0, 0.0], to_point_m=[0.5, 0.0, 0.0], points_frame=BRU
    )
    np.testing.assert_array_equal(moved.moment, [0.0, 0.25, 0.0])


def test_lateral_transfer_of_lift_rolls_right_wing_down() -> None:
    # ADR 0002: Q 1 m toward the right wing; the upward force acts left of Q, so
    # the right wing goes down (positive roll), Delta Cl = 1 / l_roll = 0.1.
    moved = _lift_force().transfer_moment_reference(
        from_point_m=[0.0, 0.0, 0.0], to_point_m=[0.0, 1.0, 0.0], points_frame=BODY
    )
    np.testing.assert_array_equal(moved.moment, [0.1, 0.0, 0.0])


def test_reference_change_hand_values() -> None:
    # ADR 0002: S 2 -> 4 and l_pitch 2 -> 0.5 give CX' = CX / 2 and Cm' = 2 Cm.
    coefficients = AeroCoefficients.from_components(
        CX=1.0, CY=0, CZ=0, Cl=0, Cm=1.0, Cn=0, reference=REFERENCE
    )
    target = ReferenceQuantities(
        area_m2=4.0, length_roll_m=10.0, length_pitch_m=0.5, length_yaw_m=7.0
    )
    renormalized = coefficients.with_reference(target)
    np.testing.assert_array_equal(renormalized.force, [0.5, 0.0, 0.0])
    np.testing.assert_array_equal(renormalized.moment, [0.0, 2.0, 0.0])
    assert renormalized.reference is target
    assert renormalized.frame is coefficients.frame


def test_pure_moment_is_independent_of_the_reference_point() -> None:
    # A couple has the same moment about every point (zero force).
    couple = AeroCoefficients.from_components(
        CX=0, CY=0, CZ=0, Cl=0.1, Cm=-0.2, Cn=0.3, reference=REFERENCE
    )
    moved = couple.transfer_moment_reference(
        from_point_m=[1.0, 2.0, 3.0], to_point_m=[-4.0, 5.0, 0.5], points_frame=BRU
    )
    np.testing.assert_array_equal(moved.moment, couple.moment)


# Agreement with the dimensional calculation


def test_transform_matches_dimensional_calculation() -> None:
    # Independent check in forces and moments: F = q S C_F, M = q S l C_M,
    # M_Q = M_P + (r_P - r_Q) x F, then rotate and normalize with the target.
    n = 200
    q_pa = 1234.5
    body = _random_body_coefficients(n)
    target = Frame.from_matrix(_random_rotations(n))
    points_rotation = _random_rotations(n)
    points_frame = Frame.from_matrix(points_rotation)
    from_point = RNG.normal(size=(n, 3))
    to_point = RNG.normal(size=(n, 3))

    force_n = q_pa * REFERENCE.area_m2 * body.force
    moment_nm = q_pa * REFERENCE.area_m2 * REFERENCE.moment_lengths_m * body.moment
    displacement_body = np.einsum("nji,nj->ni", points_rotation, from_point - to_point)
    moment_nm = moment_nm + np.cross(displacement_body, force_n)
    force_target = np.einsum("nij,nj->ni", target.rotation_from_body, force_n)
    moment_target = np.einsum("nij,nj->ni", target.rotation_from_body, moment_nm)
    expected_force = force_target / (q_pa * TARGET_REFERENCE.area_m2)
    expected_moment = moment_target / (
        q_pa * TARGET_REFERENCE.area_m2 * TARGET_REFERENCE.moment_lengths_m
    )

    result = body.transform(
        frame=target,
        reference=TARGET_REFERENCE,
        from_point_m=from_point,
        to_point_m=to_point,
        points_frame=points_frame,
    )
    assert result.frame is target
    assert result.reference is TARGET_REFERENCE
    np.testing.assert_allclose(result.force, expected_force, rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(result.moment, expected_moment, rtol=1e-12, atol=1e-12)


def test_operation_order_does_not_matter() -> None:
    # ADR 0002: renormalize, rotate, then transfer with the same points equals
    # transfer, rotate, then renormalize.
    body = _random_body_coefficients()
    target = Frame.wind(alpha_rad=RNG.uniform(-3, 3, 200), beta_rad=RNG.uniform(-1.5, 1.5, 200))
    from_point = RNG.normal(size=(200, 3))
    to_point = RNG.normal(size=(200, 3))
    direct = body.transform(
        frame=target,
        reference=TARGET_REFERENCE,
        from_point_m=from_point,
        to_point_m=to_point,
        points_frame=BRU,
    )
    reversed_order = (
        body.with_reference(TARGET_REFERENCE)
        .to_frame(target)
        .transfer_moment_reference(from_point_m=from_point, to_point_m=to_point, points_frame=BRU)
    )
    np.testing.assert_allclose(
        reversed_order.to_components_array(), direct.to_components_array(), rtol=1e-12, atol=1e-12
    )


# Round trips


def test_transfer_round_trip() -> None:
    body = _random_body_coefficients()
    p = RNG.normal(size=(200, 3))
    q = RNG.normal(size=(200, 3))
    there = body.transfer_moment_reference(from_point_m=p, to_point_m=q, points_frame=BRU)
    back = there.transfer_moment_reference(from_point_m=q, to_point_m=p, points_frame=BRU)
    np.testing.assert_allclose(back.moment, body.moment, rtol=0, atol=1e-12)
    np.testing.assert_array_equal(back.force, body.force)


def test_reference_round_trip() -> None:
    body = _random_body_coefficients()
    back = body.with_reference(TARGET_REFERENCE).with_reference(REFERENCE)
    np.testing.assert_allclose(back.to_components_array(), body.to_components_array(), rtol=1e-15)


def test_transform_round_trip() -> None:
    body = _random_body_coefficients()
    target = Frame.stability(alpha_deg=RNG.uniform(-180, 180, 200))
    p, q = RNG.normal(size=(2, 3))
    there = body.transform(
        frame=target, reference=TARGET_REFERENCE, from_point_m=p, to_point_m=q, points_frame=BRU
    )
    back = there.transform(
        frame=BODY, reference=REFERENCE, from_point_m=q, to_point_m=p, points_frame=BRU
    )
    np.testing.assert_allclose(
        back.to_components_array(), body.to_components_array(), rtol=0, atol=1e-12
    )


# Frames, batches, and longitudinal data


def test_transfer_in_any_frame_matches_body_transfer() -> None:
    body = _random_body_coefficients()
    stability = Frame.stability(alpha_rad=RNG.uniform(-3, 3, 200))
    p, q = RNG.normal(size=(2, 3))
    via_body = body.transfer_moment_reference(
        from_point_m=p, to_point_m=q, points_frame=BRU
    ).to_frame(stability)
    in_stability = body.to_frame(stability).transfer_moment_reference(
        from_point_m=p, to_point_m=q, points_frame=BRU
    )
    np.testing.assert_allclose(in_stability.moment, via_body.moment, rtol=0, atol=1e-12)


def test_point_batches_broadcast_over_single_coefficients() -> None:
    to_points = np.array([[-0.5, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 0.0]])
    moved = _lift_force().transfer_moment_reference(
        from_point_m=[0.0, 0.0, 0.0], to_point_m=to_points, points_frame=BODY
    )
    assert moved.force.shape == (3, 3)
    np.testing.assert_array_equal(moved.force, np.tile([0.0, 0.0, -1.0], (3, 1)))
    np.testing.assert_array_equal(moved.moment, [[0, 0.25, 0], [0.1, 0, 0], [0, 0, 0]])


def test_longitudinal_data_stays_longitudinal_for_points_in_the_symmetry_plane() -> None:
    # (dx, 0, dz) x (CX, 0, CZ) = (0, dz CX - dx CZ, 0): no lateral components.
    body = AeroCoefficients.from_longitudinal_axial_normal_array(
        RNG.normal(size=(200, 3)), reference=REFERENCE
    )
    in_plane = body.transform(
        frame=Frame.stability(alpha_deg=5.0),
        reference=TARGET_REFERENCE,
        from_point_m=[0.3, 0.0, -0.1],
        to_point_m=[1.2, 0.0, 0.4],
        points_frame=BRU,
    )
    assert in_plane.to_longitudinal_lift_drag_array().shape == (200, 3)
    off_plane = body.transfer_moment_reference(
        from_point_m=[0.0, 0.0, 0.0], to_point_m=[0.0, 0.5, 0.0], points_frame=BRU
    )
    with pytest.raises(ValueError, match="use the six-column array"):
        off_plane.to_longitudinal_axial_normal_array()


def test_transform_without_arguments_keeps_values() -> None:
    body = _random_body_coefficients(3)
    assert body.transform() is body


# Validation


@pytest.mark.parametrize(
    "kwargs",
    [
        {"from_point_m": [0.0, 0.0, 0.0]},
        {"from_point_m": [0.0, 0.0, 0.0], "to_point_m": [1.0, 0.0, 0.0]},
        {"points_frame": BRU},
    ],
)
def test_transform_requires_points_together(kwargs: dict[str, object]) -> None:
    with pytest.raises(TypeError, match="together or not at all"):
        _lift_force().transform(**kwargs)  # type: ignore[arg-type]


def test_transfer_validates_points_by_name() -> None:
    coefficients = _lift_force()
    with pytest.raises(ValueError, match="from_point_m must be finite"):
        coefficients.transfer_moment_reference(
            from_point_m=[np.nan, 0, 0], to_point_m=[0, 0, 0], points_frame=BODY
        )
    with pytest.raises(ValueError, match=r"to_point_m must have shape \(\.\.\., 3\)"):
        coefficients.transfer_moment_reference(
            from_point_m=[0, 0, 0], to_point_m=[0, 0], points_frame=BODY
        )
    with pytest.raises(TypeError, match="points_frame must be a Frame"):
        coefficients.transfer_moment_reference(
            from_point_m=[0, 0, 0],
            to_point_m=[0, 0, 0],
            points_frame="BRU",  # type: ignore[arg-type]
        )


def test_transfer_rejects_incompatible_batches() -> None:
    with pytest.raises(ValueError, match="do not broadcast with coefficient batch shape"):
        _random_body_coefficients(4).transfer_moment_reference(
            from_point_m=np.zeros((3, 3)), to_point_m=[0, 0, 0], points_frame=BODY
        )


def test_with_reference_requires_reference_quantities() -> None:
    with pytest.raises(TypeError, match="reference must be ReferenceQuantities"):
        _lift_force().with_reference(2.0)  # type: ignore[arg-type]
