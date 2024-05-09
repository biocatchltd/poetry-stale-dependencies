from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar

from cleo.commands.command import Command
from cleo.io.outputs.output import Verbosity


@dataclass
class LegacyPackageSource:
    url: str
    reference: str

    Pypi: ClassVar[LegacyPackageSource]


LegacyPackageSource.Pypi = LegacyPackageSource("https://pypi.org/simple", "pypi")


class UnkownMarker(Enum):
    """
    This will be used in case the dependency is optional but no marker is provided
    """

    unknown_marker = "unknown_marker"


unknown_marker = UnkownMarker.unknown_marker


@dataclass
class PackageDependency:
    version_req: str
    marker: str | None | UnkownMarker

    @classmethod
    def from_raw(cls, raw: Any) -> PackageDependency | None:
        if isinstance(raw, str):
            return cls(raw, None)

        version = raw.get("version")
        if version is None:
            return None
        raw_marker = raw.get("markers")
        is_optional = raw.get("optional", False)
        if is_optional and raw_marker is None:
            marker = unknown_marker
        else:
            marker = raw_marker

        return cls(version, marker)


@dataclass
class PackageSpec:
    version: str
    source: LegacyPackageSource | None
    dependencies: Mapping[str, PackageDependency]


@dataclass
class LockSpec:
    packages: dict[str, list[PackageSpec]] = field(default_factory=dict)

    def get_packages(
        self, packages_to_inspect: Sequence[str], com: Command
    ) -> Iterator[tuple[str, Sequence[PackageSpec]]]:
        if packages_to_inspect:
            for package in packages_to_inspect:
                if specs := self.packages.get(package):
                    yield package, specs
                else:
                    com.line_error(f"Package {package!r} not found in lock file", verbosity=Verbosity.NORMAL)
        else:
            yield from self.packages.items()

    @classmethod
    def from_raw(cls, raw: dict[str, Any], com: Command) -> LockSpec:
        lock_version = raw.get("metadata", {}).get("lock-version", None)
        if lock_version is None:
            com.line_error("No lock version found, treating as v2")
            return cls.from_raw_v2(raw, com)

        if isinstance(lock_version, str) and lock_version.startswith("2."):
            return cls.from_raw_v2(raw, com)
        else:
            com.line_error(f"Unsupported lock version: {lock_version!r}, treating as v2")
            return cls.from_raw_v2(raw, com)

    @classmethod
    def from_raw_v2(cls, raw: dict[str, Any], com: Command) -> LockSpec:
        packages: dict[str, list[PackageSpec]] = {}
        for package in raw.get("package", ()):
            name = package.get("name")
            version = package.get("version")
            raw_source = package.get("source")
            if name is None or version is None:
                com.line_error(
                    f"Package missing name or version, package ({name=}, {version=}) will be ignored",
                    verbosity=Verbosity.NORMAL,
                )
                continue
            if raw_source is None:
                source = None
            elif raw_source.get("type") != "legacy":
                # I don't have any examples of this so far, so I'm not sure what to do
                com.line_error(
                    f"Unsupported source type: {raw_source.get('type')}, package {name} will be ignored",
                    verbosity=Verbosity.NORMAL,
                )
                source = None
            else:
                source = LegacyPackageSource(
                    url=raw_source.get("url"),
                    reference=raw_source.get("reference"),
                )

            dependencies = {}
            if raw_dependencies := package.get("dependencies"):
                for dep_name, dep_raw in raw_dependencies.items():
                    if dep := PackageDependency.from_raw(dep_raw):
                        dependencies[dep_name] = dep
                    else:
                        com.line_error(
                            f"Invalid dependency {dep_name!r} for package {name}, ignoring",
                            verbosity=Verbosity.NORMAL,
                        )

            packages.setdefault(name, []).append(PackageSpec(version, source, dependencies))
        return cls(packages)
