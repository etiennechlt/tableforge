import tableforge


def test_version_is_exposed():
    assert isinstance(tableforge.__version__, str)
    assert tableforge.__version__
