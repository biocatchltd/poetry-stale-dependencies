from datetime import datetime, timedelta
from unittest.mock import MagicMock

from poetry_stale_dependencies.inspections import PackageInspectSpecs
from poetry_stale_dependencies.remote import RemoteFileSpec, RemoteReleaseSpec, pull_remote_specs
from tests.util import simple_v1_package, simple_v1_release

try:
    from datetime import UTC
except ImportError:
    from zoneinfo import ZoneInfo

    UTC = ZoneInfo("UTC")


def test_pull_remote(client, source):
    client.sources["https://pypi.org/simple"]["foo"] = simple_v1_package(
        {
            "1.0.0": [
                simple_v1_release("foo-1.0.0-py3-none-any.whl", "2021-01-01T00:00:00Z"),
                simple_v1_release("foo-1.0.0-py3-none-any.whl", "2021-05-01T00:00:00+00:00"),
                simple_v1_release("foo-1.0.0-py3-none-any.whl", "2021-05-01T00:00:00+00:00", yanked=True),
            ],
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

    specs = PackageInspectSpecs(
        "foo",
        source=source,
        time_to_stale=timedelta(days=2),
        time_to_ripe=timedelta(),
        versions=["1.0.0"],
        ignore_versions=["1.1.1"],
        ignore_prereleases=True,
    )
    remote = pull_remote_specs(client, specs, MagicMock())
    releases = remote.releases
    assert releases == [
        RemoteReleaseSpec(
            "1.0.0",
            [
                RemoteFileSpec(False, datetime(2021, 1, 1, tzinfo=UTC)),
                RemoteFileSpec(False, datetime(2021, 5, 1, tzinfo=UTC)),
                RemoteFileSpec(True, datetime(2021, 5, 1, tzinfo=UTC)),
            ],
        ),
        RemoteReleaseSpec("1.0.1", [RemoteFileSpec(False, datetime(2022, 1, 1, tzinfo=UTC))]),
        RemoteReleaseSpec("4.0.0", [RemoteFileSpec(True, datetime(2050, 1, 1, tzinfo=UTC))]),
    ]

    assert releases[0].upload_time() == datetime(2021, 1, 1, tzinfo=UTC)
    assert releases[1].upload_time() == datetime(2022, 1, 1, tzinfo=UTC)
    assert releases[2].upload_time() == datetime(2050, 1, 1, tzinfo=UTC)
