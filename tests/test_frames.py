import itertools

import numpy as np
import pytest

from aerocoeff import Frame


def test_body_frame_is_identity() -> None:
    frame = Frame.body()
    assert frame.name == "FRD"
    np.testing.assert_array_equal(frame.rotation_from_body, np.eye(3))
    assert frame.batch_shape == ()


def test_bru_matches_panelsolver_stl_mapping() -> None:
    # panelsolver "Coordinate and attitude conventions":
    # (x_body, y_body, z_body) = (-x_stl, +y_stl, -z_stl), so the STL frame is BRU.
    frame = Frame.from_axes("BRU")
    np.testing.assert_array_equal(frame.rotation_from_body, np.diag([-1.0, 1.0, -1.0]))
    # The nose direction (+x_body) points along -x_stl.
    np.testing.assert_array_equal(frame.rotation_from_body @ [1.0, 0.0, 0.0], [-1.0, 0.0, 0.0])


def test_axes_letters_name_the_body_direction_of_each_axis() -> None:
    # Derivation (ADR 0001): row i of R is the body-frame direction of frame axis i.
    # In "RDF", x points to the right wing, y down, and z forward.
    frame = Frame.from_axes("RDF")
    expected = np.array([[0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [1.0, 0.0, 0.0]])
    np.testing.assert_array_equal(frame.rotation_from_body, expected)


def test_axes_letters_are_case_insensitive() -> None:
    assert Frame.from_axes("bru").name == "BRU"


def test_all_right_handed_axis_letters_give_rotations() -> None:
    accepted = 0
    for letters in itertools.permutations("FBRLDU", 3):
        axes = "".join(letters)
        try:
            frame = Frame.from_axes(axes)
        except ValueError:
            continue
        accepted += 1
        assert np.isclose(np.linalg.det(frame.rotation_from_body), 1.0)
    # 6 axis orders x 8 sign choices, half of which are right-handed.
    assert accepted == 24


@pytest.mark.parametrize("axes", ["FLD", "BRD", "FRU"])
def test_left_handed_axis_letters_are_rejected(axes: str) -> None:
    with pytest.raises(ValueError, match="left-handed"):
        Frame.from_axes(axes)


@pytest.mark.parametrize("axes", ["FBD", "FRR", "RRD"])
def test_axis_letters_must_use_each_pair_once(axes: str) -> None:
    with pytest.raises(ValueError, match="exactly one"):
        Frame.from_axes(axes)


@pytest.mark.parametrize("axes", ["FR", "FRDX", "XYZ", ""])
def test_axis_letters_must_be_three_known_letters(axes: str) -> None:
    with pytest.raises(ValueError, match="three of the letters"):
        Frame.from_axes(axes)


def test_axis_letters_must_be_a_string() -> None:
    with pytest.raises(TypeError, match="string"):
        Frame.from_axes(123)  # type: ignore[arg-type]


def test_from_matrix_accepts_rotation_batches() -> None:
    angles = np.linspace(-np.pi, np.pi, 5)
    c, s = np.cos(angles), np.sin(angles)
    zeros, ones = np.zeros_like(angles), np.ones_like(angles)
    rotation = np.stack(
        [
            np.stack([c, zeros, s], -1),
            np.stack([zeros, ones, zeros], -1),
            np.stack([-s, zeros, c], -1),
        ],
        axis=-2,
    )
    frame = Frame.from_matrix(rotation, name="pitched")
    assert frame.batch_shape == (5,)
    assert frame.name == "pitched"


def test_from_matrix_rejects_reflections() -> None:
    with pytest.raises(ValueError, match="right-handed"):
        Frame.from_matrix(np.diag([1.0, -1.0, 1.0]))


def test_from_matrix_rejects_non_orthonormal_matrices() -> None:
    with pytest.raises(ValueError, match="orthonormal"):
        Frame.from_matrix(np.diag([1.0, 1.0, 1.0 + 1e-6]))


def test_from_matrix_accepts_rounding_within_tolerance() -> None:
    Frame.from_matrix(np.diag([1.0, 1.0, 1.0 + 1e-12]))


@pytest.mark.parametrize("matrix", [np.eye(2), np.zeros(3), np.zeros((3, 4))])
def test_from_matrix_rejects_wrong_shapes(matrix: np.ndarray) -> None:
    with pytest.raises(ValueError, match=r"\(\.\.\., 3, 3\)"):
        Frame.from_matrix(matrix)


def test_from_matrix_rejects_boolean_entries() -> None:
    with pytest.raises(TypeError, match="boolean"):
        Frame.from_matrix([[True, 0, 0], [0, 1, 0], [0, 0, 1]])


def test_frame_name_must_be_a_non_empty_string() -> None:
    with pytest.raises(TypeError, match="name"):
        Frame.from_matrix(np.eye(3), name="")
