from datetime import timedelta

from pytest import mark

from poetry_stale_dependencies.util import render_timedelta


@mark.parametrize(
    ("td", "expected"),
    [
        (timedelta(days=1), "1d"),
        (timedelta(days=36), "1mo"),
        (timedelta(days=365), "1y"),
        (timedelta(days=395), "1y 1mo"),
        (timedelta(days=425), "1y 2mo"),
        (timedelta(days=731), "2y"),
    ],
)
def test_render_timedelta(td, expected):
    assert render_timedelta(td) == expected
