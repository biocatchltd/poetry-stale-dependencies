from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, ClassVar

from poetry_stale_dependencies.inspections import PackageInspectSpecs
from poetry_stale_dependencies.lock_spec import PackageSpec

def parse_timedelta(v: Any)->timedelta:
    if not isinstance(v, str):
        raise ValueError("Timedelta must be a string (examples: 1d, 2w, 3mo, 4y)")
    if v.endswith("d"):
        return timedelta(days=int(v[:-1]))
    if v.endswith("w"):
        return timedelta(weeks=int(v[:-1]))
    if v.endswith("mo"):
        return timedelta(days=int(v[:-2]) * 30)
    if v.endswith("y"):
        return timedelta(days=int(v[:-1]) * 365)
    raise ValueError("Timedelta must end with one of d, w, mo, y")

@dataclass
class PackageConfig:
    ignore: bool
    ignore_versions: Sequence[str]
    time_to_stale: timedelta | None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> PackageConfig:
        tts = raw.get("time_to_stale")
        if tts is not None:
            time_to_stale = parse_timedelta(tts)
        else:
            time_to_stale = None
        return cls(
            ignore=raw.get("ignore", False),
            ignore_versions=raw.get("ignore_versions", []),
            time_to_stale=time_to_stale,
        )
    
    Default: ClassVar[PackageConfig]

PackageConfig.Default = PackageConfig(False, [], None)

@dataclass
class Config:
    lockfile: str
    sources: Sequence[str]
    packages: Mapping[str, PackageConfig]
    time_to_stale: timedelta

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Config:
        packages = {}
        for package, package_config in raw.get("packages", {}).items():
            packages[package] = PackageConfig.from_raw(package_config)

        return cls(
            lockfile=raw.get("lockfile", "poetry.lock"),
            sources=raw.get("sources", ("pypi",)),
            packages=packages,
            time_to_stale=parse_timedelta(raw.get("time_to_stale", "2w")),
        )
    
    def lockfile_path(self) -> Path:
        return Path(self.lockfile)
    
    def inspect_specs(self, package: str, specs: Sequence[PackageSpec]) -> Iterator[PackageInspectSpecs]:
        package_config = self.packages.get(package) or PackageConfig.Default
        if package_config.ignore:
            return None
        specs = [spec for spec in specs if (spec.source is None) or (spec.source.reference in self.sources)]
        if package_config.ignore_versions:
            specs = [spec for spec in specs if spec.version not in package_config.ignore_versions]
        if not specs:
            return
        by_source = {}
        for spec in specs:
            by_source.setdefault(spec.source, []).append(spec.version)
        time_to_stale = package_config.time_to_stale or self.time_to_stale
        for source, versions in by_source.items():
            yield PackageInspectSpecs(package, source, time_to_stale, versions)
    