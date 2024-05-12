from datetime import date, timedelta
from unittest.mock import MagicMock

from pytest import fixture, mark

from poetry_stale_dependencies.inspections import (
    NonStalePackageInspectResults,
    PackageInspectSpecs,
    ResultsVersionSpec,
    StalePackageInspectResults,
)
from poetry_stale_dependencies.lock_spec import LegacyPackageSource
from poetry_stale_dependencies.project_spec import ProjectDependency, ProjectSpec
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
            "1.0.1b": [simple_v1_release("foo-1.0.1b-py3-none-any.whl", "2021-12-31T00:00:00Z")],
            "1.0.1": [simple_v1_release("foo-1.0.1-py3-none-any.whl", "2022-01-01T00:00:00Z")],
            "1.1.1": [simple_v1_release("foo-1.1.1-py3-none-any.whl", "2023-01-01T00:00:00Z")],
            "2.0.0": [simple_v1_release("unknown_name", "2050-01-01T00:00:00Z")],
            "4.0.0": [simple_v1_release("foo-4.0.0-py3-none-any.whl", "2050-01-01T00:00:00Z", yanked=True)],
        }
    )


@fixture()
def project():
    return ProjectSpec(
        dependencies_groups={
            "main": {
                "foo": [ProjectDependency("yankee do", "is a teapot")],
                "bar": [ProjectDependency("something", "else")],
            },
            "dev": {
                "foo": [ProjectDependency("yankee dev", "is a dev teapot")],
            },
            "docs": {"baz": [ProjectDependency("baz", "is a baz")]},
        }
    )


@mark.parametrize("ignore_post2", [True, False])
@mark.parametrize("ignore_prereleases", [True, False])
def test_inspect_stale(foo_package, client, source, ignore_post2, ignore_prereleases, project):
    inspect_specs = PackageInspectSpecs(
        "foo",
        source=source,
        time_to_stale=timedelta(days=2),
        time_to_ripe=timedelta(),
        versions=["1.0.0", "2.5.0"],
        ignore_versions=["1.1.1"],
        ignore_prereleases=ignore_prereleases,
    )
    if ignore_post2:
        inspect_specs.ignore_versions.append("1.0.0post2")
    assert inspect_specs.inspect_is_stale(client, MagicMock(), project, MagicMock()) == [
        StalePackageInspectResults(
            "foo",
            LegacyPackageSource.Pypi,
            ResultsVersionSpec("1.0.0", date(2021, 1, 1)),
            ResultsVersionSpec("1.0.1", date(2022, 1, 1)),
            None if ignore_prereleases else ResultsVersionSpec("1.0.1b", date(2021, 12, 31)),
            [
                ("root", ProjectDependency("yankee do", "is a teapot")),
                ("root[dev]", ProjectDependency("yankee dev", "is a dev teapot")),
            ],
        )
    ]


@mark.parametrize("ignore_post1", [True, False])
def test_inspect_not_stale(foo_package, client, source, ignore_post1):
    inspect_specs = PackageInspectSpecs(
        "foo",
        source=source,
        time_to_stale=timedelta(days=2),
        time_to_ripe=timedelta(),
        versions=["1.0.0", "2.5.0"],
        ignore_versions=["1.1.1", "1.0.1", "1.0.0post2"],
        ignore_prereleases=True,
    )
    if ignore_post1:
        inspect_specs.ignore_versions.append("1.0.0post")
    assert inspect_specs.inspect_is_stale(client, MagicMock(), MagicMock(), MagicMock()) == [
        NonStalePackageInspectResults(
            "foo",
            LegacyPackageSource.Pypi,
            ResultsVersionSpec("1.0.0", date(2021, 1, 1)),
            ResultsVersionSpec("1.0.0", date(2021, 1, 1))
            if ignore_post1
            else ResultsVersionSpec("1.0.0post", date(2021, 1, 2)),
        )
    ]
