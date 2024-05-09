from __future__ import annotations

import re
from collections.abc import Container, Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from re import Pattern
from sys import version_info
from typing import TYPE_CHECKING, Any

from cleo.commands.command import Command
from cleo.io.outputs.output import Verbosity
from httpx import Client

from poetry_stale_dependencies.lock_spec import LegacyPackageSource

if TYPE_CHECKING:
    from poetry_stale_dependencies.config import PackageInspectSpecs


@dataclass
class RemoteReleaseSpec:
    version: str
    files: list[RemoteFileSpec]

    def upload_time(self) -> datetime:
        return min(file.upload_time for file in self.files)


@dataclass
class RemoteFileSpec:
    yanked: bool
    upload_time: datetime  # with timezone

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> RemoteFileSpec:
        raw_upload_time = raw["upload-time"]
        if version_info < (3, 11) and raw_upload_time.endswith("Z"):
            # in older python versions we need to manually fix a "Z" suffix
            raw_upload_time = raw_upload_time[:-1] + "+00:00"
        return cls(
            yanked=raw.get("yanked", False),
            upload_time=datetime.fromisoformat(raw_upload_time),
        )


class RemoteSpecs:
    def __init__(self, source: LegacyPackageSource, releases: list[RemoteReleaseSpec]):
        self.source = source
        self.releases = releases
        self.by_version = {release.version: release for release in releases}

    @classmethod
    def from_simple(
        cls,
        package_name: str,
        source: LegacyPackageSource,
        raw: dict[str, Any],
        com: Command,
        ignore_version: Container[str],
        ignore_prerelease: bool,
    ) -> RemoteSpecs:
        grouped_releases: dict[str, list[RemoteFileSpec]] = {}
        raw_files = raw.get("files", ())
        versions: Sequence[str] = raw.get("versions", ())
        version_extractor = VersionExtractor(versions)
        for file in raw_files:
            filename = file.get("filename")
            if filename is None:
                continue
            version = version_extractor.extract_version(filename)
            if version is None:
                com.line_error(f"Could not extract version from filename: {filename}", verbosity=Verbosity.VERBOSE)
                continue
            grouped_releases.setdefault(version, []).append(RemoteFileSpec.from_raw(file))
        releases = []
        for version in versions:
            files = grouped_releases.get(version)
            if not files:
                com.line(
                    f"{package_name} [{source.reference}]: Ignoring remote version {version} because it has no files",
                    verbosity=Verbosity.VERY_VERBOSE,
                )
                continue
            if ignore_prerelease and is_prerelease(version):
                com.line(
                    f"{package_name} [{source.reference}]: Ignoring remote version {version} because it is a prerelease",
                    verbosity=Verbosity.VERY_VERBOSE,
                )
                continue
            if version in ignore_version:
                com.line(
                    f"{package_name} [{source.reference}]: Ignoring remote version {version} because it is set to ignore in config",
                    verbosity=Verbosity.VERY_VERBOSE,
                )
                continue

            releases.append(RemoteReleaseSpec(version, files))
        return cls(source, releases)

    def applicable_releases(self) -> Iterator[RemoteReleaseSpec]:
        return (release for release in reversed(self.releases) if any(not file.yanked for file in release.files))


prerelease_pattern = re.compile(r".*(rc|a|b|dev)\d*$")


def is_prerelease(version: str) -> bool:
    return bool(prerelease_pattern.fullmatch(version))


class VersionExtractor:
    """
    A helper class to extract versions from filenames

    AFAICT, pypi file names are of the following structures:
    {package_name_with_underscores}-{version}-*.whl
    {package_name_with_dashes_or_underscores}-{version}.tar.gz
    if the filename doesn't conform to these, we will simply run through all known versions of the project, looking for a match
    """

    whl_pattern = re.compile(r"^(.+?)-(?P<version>.+?)(-.+)?\.whl$")
    tar_pattern = re.compile(r"^(.+)-(?P<version>.+)\.tar\.gz$")

    def __init__(self, known_versions: Sequence[str]):
        self.known_versions = known_versions
        self._known_versions_set = frozenset(known_versions)
        self._version_pattern: Pattern | None = None

    def version_pattern(self) -> Pattern:
        if self._version_pattern is None:
            # this ordering will result in the longest versions being matched first, with versions of the same length being matched in by latest-first
            versions = sorted(self.known_versions, key=len, reverse=True)
            self._version_pattern = re.compile(
                "|".join(re.escape(version) for version in versions),
            )
        return self._version_pattern

    def extract_version(self, filename: str) -> str | None:
        structured_match = self.whl_pattern.fullmatch(filename) or self.tar_pattern.fullmatch(filename)
        if structured_match:
            structured_version = structured_match.group("version")
            if structured_version in self._known_versions_set:
                return structured_version
        else:
            structured_version = None
        # structures are either no match, or resulted in an unrecognized version, we'll try to parse the version manually
        version_match = self.version_pattern().search(filename)
        if version_match:
            return version_match[0]
        # if there is no version match, we'll return the structured version if it exists
        return structured_version


def pull_remote_specs(session: Client, specs: PackageInspectSpecs, com: Command) -> RemoteSpecs:
    source = specs.source or LegacyPackageSource.Pypi
    response = session.get(
        f"{source.url}/{specs.package}",
        headers={"Accept": "application/vnd.pypi.simple.v1+json"},
        follow_redirects=True,
    )
    if response.status_code != 200:
        raise ValueError(
            f"Failed to fetch remote specs for {specs.package} ({source.reference}): {response.status_code}"
        )
    return RemoteSpecs.from_simple(
        specs.package, source, response.json(), com, specs.ignore_versions, specs.ignore_prereleases
    )
