from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from pytest import fixture

from poetry_stale_dependencies.lock_spec import LegacyPackageSource


@dataclass
class MockResponse:
    status_code: int
    _json: Any = ...

    def json(self):
        assert self._json is not ...

        ret = self._json
        # we assert that every response is only parsed once, and never parsed if an error
        self._json = ...

        return ret


class MockHTTPClient:
    def __init__(self):
        self.sources = defaultdict(dict)

    def get(self, url, **kwargs):
        source_url, _, package_name = url.rpartition("/")
        source = self.sources.get(source_url)
        if source is None:
            return MockResponse(404)
        package = source.get(package_name)
        if package is None:
            return MockResponse(404)
        return MockResponse(200, package)


@fixture()
def client():
    return MockHTTPClient()


@fixture(params=[LegacyPackageSource("https://pypi.org/simple", "pypi"), None])
def source(request):
    return request.param
