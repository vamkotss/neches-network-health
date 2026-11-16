from neches import __version__


def test_version():
    # If this fails, the package did not import correctly.
    assert __version__ == "0.1.0"
