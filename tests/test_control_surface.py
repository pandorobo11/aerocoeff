import dataclasses

import numpy as np
import pytest

from aerocoeff import AeroCoefficients, ControlSurface, Frame, ReferenceQuantities

BODY = Frame.body()
BRU = Frame.from_axes("BRU")
VEHICLE = ReferenceQuantities(
    area_m2=2.0, length_roll_m=10.0, length_pitch_m=2.0, length_yaw_m=10.0
)
# Right horizontal tail of the ADR 0003 verification example, in body axes.
ROOT_BODY = np.array([-5.0, 0.2, 0.0])
TIP_BODY = np.array([-5.0, 1.2, 0.0])
AFT_BODY = np.array([-1.0, 0.0, 0.0])

RNG = np.random.default_rng(20261029)


def _tail(
    points_frame: Frame = BODY,
    start: np.ndarray = ROOT_BODY,
    end: np.ndarray = TIP_BODY,
    trailing: np.ndarray = AFT_BODY,
) -> ControlSurface:
    return ControlSurface(
        hinge_start_m=start,
        hinge_end_m=end,
        trailing_edge_direction=trailing,
        points_frame=points_frame,
        area_m2=0.2,
        hinge_moment_length_m=0.25,
        bending_moment_length_m=1.0,
    )


def _example_load() -> AeroCoefficients:
    # ADR 0003: upward force CZ = -0.01 acting 0.1 m aft of the hinge and 0.5 m
    # outboard of the root, with moments about the body origin.
    force = np.array([0.0, 0.0, -0.01])
    moment = np.cross([-5.1, 0.7, 0.0], force) / VEHICLE.moment_lengths_m
    return AeroCoefficients(force, moment, BODY, VEHICLE)


# Hand-checkable values (ADR 0003 verification table)


def test_right_tail_example() -> None:
    # CN_s = 0.01 * 2 / 0.2; Ch = -0.1 * 0.01 * 2 / (0.2 * 0.25) (trailing edge
    # pushed up); CB = 0.5 * 0.01 * 2 / (0.2 * 1.0) (ADR 0003).
    result = _tail().three_components_array(
        _example_load(), moment_reference_m=[0.0, 0.0, 0.0], deflection_deg=0.0
    )
    np.testing.assert_allclose(result, [0.1, -0.04, 0.05], rtol=1e-14)


def test_right_tail_axes() -> None:
    # ADR 0003: x_h aft, y_h right, z_h up for an outboard axis and an aft trailing edge.
    rotation = _tail().frame(deflection_deg=0.0).rotation_from_body
    np.testing.assert_array_equal(rotation, [[-1, 0, 0], [0, 1, 0], [0, 0, -1]])


def test_same_geometry_in_bru() -> None:
    to_bru = BRU.rotation_from_body
    surface = _tail(BRU, to_bru @ ROOT_BODY, to_bru @ TIP_BODY, np.array([1.0, 0.0, 0.0]))
    result = surface.three_components_array(
        _example_load(), moment_reference_m=[0.0, 0.0, 0.0], deflection_deg=0.0
    )
    np.testing.assert_allclose(result, [0.1, -0.04, 0.05], rtol=1e-14)


def test_positive_deflection_moves_the_trailing_edge_down() -> None:
    # ADR 0003: x_h = cos(d) x0 - sin(d) z0; x0 aft and z0 up give a downward (+z_body)
    # trailing-edge component sin(d).
    x_axis = _tail().frame(deflection_deg=10.0).rotation_from_body[0]
    np.testing.assert_allclose(x_axis, [-np.cos(np.radians(10)), 0, np.sin(np.radians(10))])


def test_deflection_changes_normal_force_and_bending_but_not_hinge_moment() -> None:
    # The example force lies along z0 and its root moment along x0 and y_h, so in
    # deflected axes CN_s and CB scale with cos(d) and Ch is unchanged (ADR 0003).
    deflection_deg = np.array([-20.0, 0.0, 15.0])
    result = _tail().three_components_array(
        _example_load(), moment_reference_m=[0.0, 0.0, 0.0], deflection_deg=deflection_deg
    )
    cos = np.cos(np.radians(deflection_deg))
    expected = np.stack([0.1 * cos, np.full(3, -0.04), 0.05 * cos], axis=-1)
    np.testing.assert_allclose(result, expected, rtol=1e-13)


def test_degrees_and_radians_give_the_same_frame() -> None:
    surface = _tail()
    np.testing.assert_allclose(
        surface.frame(deflection_deg=12.0).rotation_from_body,
        surface.frame(deflection_rad=np.radians(12.0)).rotation_from_body,
        rtol=0,
        atol=1e-15,
    )


@pytest.mark.parametrize("kwargs", [{}, {"deflection_rad": 0.0, "deflection_deg": 0.0}])
def test_deflection_is_required(kwargs: dict[str, float]) -> None:
    with pytest.raises(TypeError, match="exactly one of deflection_rad and deflection_deg"):
        _tail().loads(_example_load(), moment_reference_m=[0.0, 0.0, 0.0], **kwargs)


# Geometry


def test_swept_hinge_uses_the_perpendicular_trailing_edge_direction() -> None:
    sweep = np.radians(30.0)
    tip = ROOT_BODY + np.array([-np.tan(sweep), 1.0, 0.0])
    rotation = _tail(end=tip).frame(deflection_deg=0.0).rotation_from_body
    # x_h is aft and inboard, perpendicular to the swept hinge; z_h stays up.
    np.testing.assert_allclose(rotation[0], [-np.cos(sweep), -np.sin(sweep), 0], atol=1e-15)
    np.testing.assert_allclose(rotation[2], [0, 0, -1], atol=1e-15)
    # A trailing-edge point minus a hinge point gives the same frame.
    trailing_point = ROOT_BODY + np.array([-0.3, 0.4, 0.0])
    from_point = _tail(end=tip, trailing=trailing_point - ROOT_BODY).frame(deflection_deg=0.0)
    np.testing.assert_allclose(from_point.rotation_from_body, rotation, atol=1e-15)


def test_dihedral_tilts_the_normal_inboard() -> None:
    dihedral = np.radians(10.0)
    tip = ROOT_BODY + np.array([0.0, np.cos(dihedral), -np.sin(dihedral)])
    normal = _tail(end=tip).frame(deflection_deg=0.0).rotation_from_body[2]
    np.testing.assert_allclose(normal, [0, -np.sin(dihedral), -np.cos(dihedral)], atol=1e-15)


def test_left_tail_and_vertical_fin_axes() -> None:
    # ADR 0003: an outboard axis on the left gives z_h down; a fin with the axis up
    # and the trailing edge aft gives z_h to the left.
    left = _tail(start=np.array([-5.0, -0.2, 0.0]), end=np.array([-5.0, -1.2, 0.0]))
    np.testing.assert_array_equal(left.frame(deflection_deg=0.0).rotation_from_body[2], [0, 0, 1])
    fin = _tail(start=np.array([-5.0, 0.0, -0.2]), end=np.array([-5.0, 0.0, -1.2]))
    np.testing.assert_array_equal(fin.frame(deflection_deg=0.0).rotation_from_body[2], [0, -1, 0])


def test_reversing_the_hinge_axis_flips_normal_force_and_hinge_moment() -> None:
    # Same start point, axis reversed: y_h and z_h flip, x_h does not (ADR 0003).
    reversed_end = ROOT_BODY - (TIP_BODY - ROOT_BODY)
    kwargs = {"moment_reference_m": [0.0, 0.0, 0.0], "deflection_deg": 5.0}
    forward = _tail().three_components_array(_example_load(), **kwargs)  # type: ignore[arg-type]
    backward = _tail(end=reversed_end).three_components_array(
        _example_load(),
        **kwargs,  # type: ignore[arg-type]
    )
    np.testing.assert_allclose(backward, forward * [-1, -1, 1], rtol=1e-14)


# Agreement, round trips, and frames


def test_components_match_moments_about_the_hinge_axes() -> None:
    # Independent check: F and M_root = M_mrc + (r_mrc - r_root) x F per unit q,
    # projected on the deflected hinge axes and divided by the surface reference.
    n = 200
    force = RNG.normal(size=(n, 3))
    moment = RNG.normal(size=(n, 3))
    mrc_body = RNG.normal(size=3)
    deflection = RNG.uniform(-0.5, 0.5, n)
    coefficients = AeroCoefficients(force, moment, BODY, VEHICLE)
    surface = _tail()
    axes = surface.frame(deflection_rad=deflection).rotation_from_body

    force_m2 = VEHICLE.area_m2 * force
    moment_m3 = VEHICLE.area_m2 * VEHICLE.moment_lengths_m * moment
    root_moment_m3 = moment_m3 + np.cross(mrc_body - ROOT_BODY, force_m2)
    expected = np.stack(
        [
            np.einsum("nj,nj->n", axes[:, 2], force_m2) / 0.2,
            np.einsum("nj,nj->n", axes[:, 1], root_moment_m3) / (0.2 * 0.25),
            np.einsum("nj,nj->n", axes[:, 0], root_moment_m3) / (0.2 * 1.0),
        ],
        axis=-1,
    )
    result = surface.three_components_array(
        coefficients, moment_reference_m=mrc_body, deflection_rad=deflection
    )
    np.testing.assert_allclose(result, expected, rtol=1e-12, atol=1e-12)


def test_loads_round_trip_to_vehicle_coefficients() -> None:
    coefficients = AeroCoefficients(
        RNG.normal(size=(50, 3)), RNG.normal(size=(50, 3)), BODY, VEHICLE
    )
    mrc_bru = np.array([4.0, 0.0, 0.3])
    to_bru = BRU.rotation_from_body
    surface = _tail(BRU, to_bru @ ROOT_BODY, to_bru @ TIP_BODY, np.array([1.0, 0.0, 0.0]))
    loads = surface.loads(coefficients, moment_reference_m=mrc_bru, deflection_deg=7.0)
    assert loads.frame.name == "hinge"
    assert loads.reference == surface.reference
    back = loads.transform(
        frame=BODY,
        reference=VEHICLE,
        from_point_m=surface.hinge_start_m,
        to_point_m=mrc_bru,
        points_frame=BRU,
    )
    np.testing.assert_allclose(
        back.to_components_array(), coefficients.to_components_array(), rtol=0, atol=1e-12
    )


def test_input_frame_does_not_matter() -> None:
    body = _example_load()
    stability = body.to_frame(Frame.stability(alpha_deg=8.0))
    kwargs = {"moment_reference_m": [0.0, 0.0, 0.0], "deflection_deg": -3.0}
    np.testing.assert_allclose(
        _tail().three_components_array(stability, **kwargs),  # type: ignore[arg-type]
        _tail().three_components_array(body, **kwargs),  # type: ignore[arg-type]
        rtol=1e-13,
    )


# Reference quantities


def test_reference_fills_hinge_axis_positions() -> None:
    surface = _tail()
    assert surface.reference == ReferenceQuantities(
        area_m2=0.2, length_roll_m=1.0, length_pitch_m=0.25, length_yaw_m=1.0
    )
    explicit = dataclasses.replace(surface, normal_moment_length_m=0.5)
    assert explicit.reference.length_yaw_m == 0.5


# Validation


@pytest.mark.parametrize(
    ("changes", "error", "message"),
    [
        ({"hinge_start_m": np.zeros((2, 3))}, ValueError, r"hinge_start_m must have shape \(3,\)"),
        ({"hinge_end_m": [0.0, np.nan, 0.0]}, ValueError, "hinge_end_m must be finite"),
        ({"trailing_edge_direction": [1.0, 0.0]}, ValueError, "trailing_edge_direction must"),
        ({"hinge_end_m": ROOT_BODY}, ValueError, "must be different points"),
        ({"trailing_edge_direction": [0.0, 0.0, 0.0]}, ValueError, "must not be zero or parallel"),
        ({"trailing_edge_direction": [1e-7, 1.0, 0.0]}, ValueError, "must not be zero or parallel"),
        ({"area_m2": 0.0}, ValueError, "area_m2 must be positive"),
        ({"hinge_moment_length_m": -1.0}, ValueError, "hinge_moment_length_m must be positive"),
        ({"bending_moment_length_m": True}, TypeError, "bending_moment_length_m must be numeric"),
        ({"normal_moment_length_m": 0.0}, ValueError, "normal_moment_length_m must be positive"),
        ({"points_frame": "BRU"}, TypeError, "points_frame must be a Frame"),
        (
            {"points_frame": Frame.stability(alpha_deg=[0.0, 1.0])},
            ValueError,
            "points_frame must be a single frame",
        ),
    ],
)
def test_geometry_and_reference_are_validated(
    changes: dict[str, object], error: type[Exception], message: str
) -> None:
    with pytest.raises(error, match=message):
        dataclasses.replace(_tail(), **changes)  # type: ignore[arg-type]


def test_nearly_perpendicular_trailing_edge_is_accepted() -> None:
    surface = _tail(trailing=np.array([-1e-5, 1.0, 0.0]))
    np.testing.assert_allclose(surface.frame(deflection_deg=0.0).rotation_from_body[0], AFT_BODY)


def test_loads_require_coefficients() -> None:
    with pytest.raises(TypeError, match="coefficients must be AeroCoefficients"):
        _tail().loads(
            "table",  # type: ignore[arg-type]
            moment_reference_m=[0.0, 0.0, 0.0],
            deflection_deg=0.0,
        )


def test_geometry_is_read_only() -> None:
    surface = _tail()
    assert not surface.hinge_start_m.flags.writeable
    with pytest.raises(dataclasses.FrozenInstanceError):
        surface.area_m2 = 1.0  # type: ignore[misc]
