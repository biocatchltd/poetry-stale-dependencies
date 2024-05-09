from datetime import timedelta
from unittest.mock import MagicMock

from pytest import fixture, mark

from poetry_stale_dependencies.inspections import PackageInspectSpecs
from tests.util import simple_v1_package, simple_v1_release


@fixture()
def foo_package(client):
    client.sources["https://pypi.org/simple"]["foo"] = simple_v1_package(
        {
            "0.1.0": [
                simple_v1_release("foo-0.1.0-py3-none-any.whl", "2020-01-01T00:00:00Z"),
            ],
            "1.0.0": [
                simple_v1_release("foo-1.0.0-py3-none-any.whl", "2021-01-01T00:00:00Z"),
                simple_v1_release("foo-1.0.0-py3-none-any.whl", "2021-05-01T00:00:00+00:00"),
                simple_v1_release("foo-1.0.0-py3-none-any.whl", "2021-05-01T00:00:00+00:00", yanked=True),
            ],
            "1.0.0post": [simple_v1_release("foo-1.0.0post-py3-none-any.whl", "2021-01-02T00:00:00Z")],
            "1.0.0post2": [simple_v1_release("foo-1.0.0post2-py3-none-any.whl", "2021-05-02T00:00:00Z")],
            "1.0.1": [simple_v1_release("foo-1.0.1-py3-none-any.whl", "2022-01-01T00:00:00Z")],
            "1.1.1": [simple_v1_release("foo-1.1.1-py3-none-any.whl", "2023-01-01T00:00:00Z")],
            "2.0.0": [simple_v1_release("unknown_name", "2050-01-01T00:00:00Z")],
            "3.0.0b1": [
                simple_v1_release("unknown_name-3.0.0b1", "2050-01-01T00:00:00Z"),
                simple_v1_release("foo-3.0.0b12-py3-none-any.whl", "2050-01-01T00:00:00Z"),
            ],
            "4.0.0": [simple_v1_release("foo-4.0.0-py3-none-any.whl", "2050-01-01T00:00:00Z", yanked=True)],
        }
    )


@mark.parametrize("ignore_post2", [True, False])
def test_inspect_stale(foo_package, client, source, ignore_post2):
    inspect_specs = PackageInspectSpecs(
        "foo",
        source=source,
        time_to_stale=timedelta(days=2),
        versions=["1.0.0", "2.5.0"],
        ignore_versions=["1.1.1"],
        ignore_prereleases=True,
    )
    if ignore_post2:
        inspect_specs.ignore_versions.append("1.0.0post2")
    assert inspect_specs.inspect_is_stale(client, MagicMock(), MagicMock()) is True


@mark.parametrize("ignore_post1", [True, False])
def test_inspect_not_stale(foo_package, client, source, ignore_post1):
    inspect_specs = PackageInspectSpecs(
        "foo",
        source=source,
        time_to_stale=timedelta(days=2),
        versions=["1.0.0", "2.5.0"],
        ignore_versions=["1.1.1", "1.0.1", "1.0.0post2"],
        ignore_prereleases=True,
    )
    if ignore_post1:
        inspect_specs.ignore_versions.append("1.0.0post")
    assert inspect_specs.inspect_is_stale(client, MagicMock(), MagicMock()) is False
