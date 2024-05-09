from __future__ import annotations

from collections.abc import Container, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Lock

from cleo.commands.command import Command
from cleo.io.outputs.output import Verbosity
from httpx import Client

from poetry_stale_dependencies.lock_spec import LegacyPackageSource, LockSpec, PackageDependency, unknown_marker
from poetry_stale_dependencies.project_spec import ProjectDependency, ProjectSpec
from poetry_stale_dependencies.remote import pull_remote_specs
from poetry_stale_dependencies.util import render_timedelta


@dataclass
class PackageInspectSpecs:
    package: str
    source: LegacyPackageSource | None
    time_to_stale: timedelta
    time_to_ripe: timedelta
    versions: Sequence[str]
    ignore_versions: Container[str]
    ignore_prereleases: bool

    def inspect_is_stale(
        self, session: Client, lock_spec: LockSpec, project_spec: ProjectSpec, com: Command, com_lock: Lock
    ) -> bool:
        remote = pull_remote_specs(session, self, com)
        ret = False
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
            delta = latest_time - local_version_time
            if latest_time > stale_time:
                with com_lock:
                    ret = True
                    com.line(
                        f"{self.package} [{remote.source.reference}]: local version {local_version} is stale, latest is {latest.version} (delta: {render_timedelta(delta)})",
                        verbosity=Verbosity.NORMAL,
                    )
                    com.line(
                        f"\t{local_version} was uploaded at {local_version_time.isoformat()}, {latest.version} was uploaded at {latest_time.isoformat()}",
                        verbosity=Verbosity.VERBOSE,
                    )
                    if com.io.is_verbose():
                        oldest_non_stale = None
                        # note that there will always be at least one more applicable release: the local version
                        for release in applicable_releases:
                            upload_time = release.upload_time().date()
                            if upload_time > stale_time:
                                oldest_non_stale = (release, upload_time)
                            else:
                                break
                        if oldest_non_stale is not None:
                            com.line(
                                f"\toldest non-stale release is {oldest_non_stale[0].version} ({oldest_non_stale[1].isoformat()})",
                                verbosity=Verbosity.VERBOSE,
                            )

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

                        if dependencies:
                            com.line(
                                f"\tused by {len(dependencies)}:",
                                verbosity=Verbosity.VERBOSE,
                            )
                            for package_name, dep in dependencies:
                                if dep.marker is None:
                                    marker_desc = ""
                                elif dep.marker is unknown_marker:
                                    marker_desc = " [unknown marker]"
                                else:
                                    marker_desc = f" [{dep.marker}]"
                                com.line(
                                    f"\t\t{package_name}: {dep.version_req}{marker_desc}",
                                    verbosity=Verbosity.VERBOSE,
                                )
            else:
                with com_lock:
                    com.line(
                        f"{self.package} [{remote.source.reference}]: Package is up to date ({local_version})",
                        verbosity=Verbosity.VERBOSE,
                    )
                    if latest.version == local_version:
                        com.line(f"\t{local_version} is latest", verbosity=Verbosity.VERY_VERBOSE)
                    else:
                        com.line(
                            f"\t{local_version} was uploaded at {local_version_time.isoformat()}, latest ({latest.version}) was uploaded at {latest_time.isoformat()} (delta: {render_timedelta(delta)})",
                            verbosity=Verbosity.VERY_VERBOSE,
                        )
        return ret
