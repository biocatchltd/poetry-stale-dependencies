from __future__ import annotations

from collections.abc import Container, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from cleo.commands.command import Command
from cleo.io.outputs.output import Verbosity
from httpx import Client

from poetry_stale_dependencies.lock_spec import LegacyPackageSource, LockSpec, PackageDependency, unknown_marker
from poetry_stale_dependencies.project_spec import ProjectDependency, ProjectSpec
from poetry_stale_dependencies.remote import pull_remote_specs
from poetry_stale_dependencies.util import PackageName, render_timedelta


@dataclass
class PackageInspectSpecs:
    package: PackageName
    source: LegacyPackageSource | None
    time_to_stale: timedelta
    time_to_ripe: timedelta
    versions: Sequence[str]
    ignore_versions: Container[str]
    ignore_prereleases: bool

    def inspect_is_stale(
        self, session: Client, lock_spec: LockSpec, project_spec: ProjectSpec, com: Command
    ) -> list[StalePackageInspectResults | NonStalePackageInspectResults]:
        remote = pull_remote_specs(session, self, com)
        ret: list[StalePackageInspectResults | NonStalePackageInspectResults] = []
        for local_version in self.versions:
            # we need to get the time of the current releases
            if (local_spec := remote.by_version.get(local_version)) is None:
                com.line_error(
                    f"Local version {self.package} {local_version} not found in remote, skipping",
                    verbosity=Verbosity.NORMAL,
                )
                continue
            local_version_time = local_spec.upload_time().date()
            stale_time = local_version_time + self.time_to_stale
            ripe_time = max(datetime.now().date() - self.time_to_ripe, local_version_time)
            applicable_releases = remote.applicable_releases(self.package, ripe_time, com)
            latest = next(applicable_releases)
            latest_time = latest.upload_time().date()
            if latest_time > stale_time:
                # any release used that is before this time will be considered stale
                time_to_non_stale = latest_time - self.time_to_stale
                oldest_non_stale = None
                # note that there will always be at least one more applicable release: the local version
                for release in applicable_releases:
                    upload_time = release.upload_time().date()
                    if upload_time > time_to_non_stale:
                        oldest_non_stale = ResultsVersionSpec(release.version, upload_time)
                    else:
                        break

                dependencies: list[tuple[str, PackageDependency | ProjectDependency]] = [
                    (package_name, package_dep)
                    for package_name, package_specs in lock_spec.packages.items()
                    for package_spec in package_specs
                    if (package_dep := package_spec.dependencies.get(self.package)) is not None
                ]

                for group_name, group in project_spec.dependencies_groups.items():
                    if (group_deps := group.get(self.package)) is not None:
                        for project_dep in group_deps:
                            if group_name == "main":
                                group_desc = project_spec.name
                            else:
                                group_desc = f"{project_spec.name}[{group_name}]"
                            dependencies.append((group_desc, project_dep))

                ret.append(
                    StalePackageInspectResults(
                        self.package,
                        remote.source,
                        ResultsVersionSpec(local_version, local_version_time),
                        ResultsVersionSpec(latest.version, latest_time),
                        oldest_non_stale,
                        dependencies,
                    )
                )
            else:
                ret.append(
                    NonStalePackageInspectResults(
                        self.package,
                        remote.source,
                        ResultsVersionSpec(local_version, local_version_time),
                        ResultsVersionSpec(latest.version, latest_time),
                    )
                )
        return ret


@dataclass
class ResultsVersionSpec:
    version: str
    time: date


@dataclass
class NonStalePackageInspectResults:
    package: str
    source: LegacyPackageSource
    local_version: ResultsVersionSpec
    latest_version: ResultsVersionSpec

    def writelines(self, com: Command):
        com.line(
            f"<info>{self.package} [{self.source.reference}]</>: Package is up to date (<comment>{self.local_version.version}</>)",
            verbosity=Verbosity.VERY_VERBOSE,
        )
        if self.latest_version.version == self.local_version.version:
            com.line(f"\t{self.local_version.version} is latest", verbosity=Verbosity.VERY_VERBOSE)
        else:
            com.line(
                f"\t{self.local_version.version} was uploaded at {self.local_version.time.isoformat()}, latest ({self.latest_version.version}) was uploaded at {self.latest_version.time.isoformat()}",
                verbosity=Verbosity.VERY_VERBOSE,
            )


@dataclass
class StalePackageInspectResults:
    package: str
    source: LegacyPackageSource
    local_version: ResultsVersionSpec
    latest_version: ResultsVersionSpec
    oldest_non_stale: ResultsVersionSpec | None
    dependencies: list[tuple[str, PackageDependency | ProjectDependency]]

    def writelines(self, com: Command):
        delta = self.latest_version.time - self.local_version.time
        com.line(
            f"<info>{self.package} [{self.source.reference}]</>: local version <comment>{self.local_version.version}</> is stale, latest is <comment>{self.latest_version.version}</> (delta: <info>{render_timedelta(delta)}</>)"
        )
        com.line(
            f"\t<comment>{self.local_version.version}</> was uploaded at <comment>{self.local_version.time.isoformat()}</>, <comment>{self.latest_version.version}</> was uploaded at <comment>{self.latest_version.time.isoformat()}</>",
            verbosity=Verbosity.VERBOSE,
        )
        if self.oldest_non_stale is not None:
            com.line(
                f"\toldest non-stale release is <comment>{self.oldest_non_stale.version}</> (<comment>{self.oldest_non_stale.time.isoformat()}</>)",
                verbosity=Verbosity.VERBOSE,
            )
        if self.dependencies:
            use_plural = "usages" if len(self.dependencies) > 1 else "usage"
            com.line(f"\tfound {len(self.dependencies)} {use_plural}:", verbosity=Verbosity.VERBOSE)
            for package_name, dep in self.dependencies:
                if dep.marker is None:
                    marker_desc = ""
                elif dep.marker is unknown_marker:
                    marker_desc = " [unknown marker]"
                else:
                    marker_desc = f" [{dep.marker}]"
                com.line(
                    f"\t\t<info>{package_name}</>: {dep.version_req}<comment>{marker_desc}</>",
                    verbosity=Verbosity.VERBOSE,
                )
