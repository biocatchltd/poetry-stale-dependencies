from unittest.mock import MagicMock

from pytest import mark

from poetry_stale_dependencies.lock_spec import LegacyPackageSource, LockSpec, PackageSpec


@mark.parametrize("lock_version", ["2.0.1", "floofy", 5, None])
def test_parse_lock(lock_version):
    lock_content = {
        "metadata": {},
        "package": [
            {
                "name": "foo",
                "version": "1.0.0",
            },
            {
                "name": "bar",
            },
            {
                "version": "1.0.0",
            },
            {
                "name": "baz",
                "version": "2.0.0",
                "source": {"type": "legacy", "url": "https://pypi2.org/simple", "reference": "pypi2"},
            },
            {
                "name": "booz",
                "version": "2.1.0",
                "source": {"type": "new", "url": "https://pypi2.org/simple", "reference": "pypi2"},
            },
            {
                "name": "foo",
                "version": "5.6.7",
            },
        ],
    }
    if lock_version:
        lock_content["metadata"]["lock-version"] = lock_version

    lock = LockSpec.from_raw(lock_content, MagicMock())

    assert lock.packages == {
        "foo": [PackageSpec("1.0.0", None, {}), PackageSpec("5.6.7", None, {})],
        "baz": [PackageSpec("2.0.0", LegacyPackageSource("https://pypi2.org/simple", "pypi2"), {})],
        "booz": [PackageSpec("2.1.0", None, {})],
    }
