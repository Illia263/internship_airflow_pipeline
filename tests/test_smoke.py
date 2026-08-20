


def test_reference_exists():
    from pathlib import Path
    assert Path("expected/reference.csv").exists(), "make setup first"


def test_source_has_13_files():
    from pathlib import Path
    files = list(Path("source").glob("*.csv"))
    assert len(files) == 13, f"expected 13, found {len(files)}: make setup first"
