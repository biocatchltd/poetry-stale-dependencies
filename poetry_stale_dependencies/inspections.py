from __future__ import annotations

from collections.abc import Container, Sequence
from dataclasses import dataclass
from datetime import timedelta
from threading import Lock

from cleo.commands.command import Command
from cleo.io.outputs.output import Verbosity
from httpx import Client

from poetry_stale_dependencies.lock_spec import LegacyPackageSource
from poetry_stale_dependencies.remote import pull_remote_specs
from poetry_stale_dependencies.util import render_timedelta


@dataclass
class PackageInspectSpecs:
    package: str
    source: LegacyPackageSource | None
    time_to_stale: timedelta
    versions: Sequence[str]
    ignore_versions: Container[str]
    ignore_prereleases: bool

    def inspect_is_stale(self, session: Client, com: Command, com_lock: Lock) -> bool:
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
            applicable_releases = remote.applicable_releases()
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
