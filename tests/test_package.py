from importlib.resources import files

import aerocoeff


def test_package_is_importable() -> None:
    assert aerocoeff.__doc__


def test_package_ships_py_typed_marker() -> None:
    assert files("aerocoeff").joinpath("py.typed").is_file()
