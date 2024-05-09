from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

from cleo.commands.command import Command
from cleo.io.outputs.output import Verbosity


@dataclass
class LegacyPackageSource:
    url: str
    reference: str

    Pypi: ClassVar[LegacyPackageSource]


LegacyPackageSource.Pypi = LegacyPackageSource("https://pypi.org/simple", "pypi")


@dataclass
class PackageSpec:
    version: str
    source: LegacyPackageSource | None


@dataclass
class LockSpec:
    packages: dict[str, list[PackageSpec]] = field(default_factory=dict)

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

            packages.setdefault(name, []).append(PackageSpec(version, source))
        return cls(packages)
