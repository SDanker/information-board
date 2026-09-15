import pytest

from app.file_responses import RangeNotSatisfiable, parse_range


def test_parse_range_variants():
    assert parse_range(None, 100) is None
    assert parse_range("bytes=0-9", 100) == (0, 9)
    assert parse_range("bytes=90-", 100) == (90, 99)
    assert parse_range("bytes=-10", 100) == (90, 99)
    assert parse_range("bytes=50-500", 100) == (50, 99)
    # Multiple or malformed ranges fall back to the full file.
    assert parse_range("bytes=0-1,5-6", 100) is None
    assert parse_range("items=0-1", 100) is None


@pytest.mark.parametrize("header", ["bytes=100-", "bytes=-0", "bytes=9-3"])
def test_parse_range_rejects_unsatisfiable_ranges(header):
    with pytest.raises(RangeNotSatisfiable):
        parse_range(header, 100)
