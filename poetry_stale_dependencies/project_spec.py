from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cleo.commands.command import Command

from poetry_stale_dependencies.lock_spec import UnkownMarker, unknown_marker
from poetry_stale_dependencies.util import PackageName, to_package_name


@dataclass
class ProjectDependency:
    version_req: str
    marker: str | None | UnkownMarker

    @classmethod
    def from_raw(cls, raw: Any) -> ProjectDependency | None:
        if isinstance(raw, str):
            return cls(raw, None)

        version = raw.get("version")
        if version is None:
            return None
        marker_parts = []
        raw_marker = raw.get("markers")
        if raw_marker is not None:
            marker_parts.append(raw_marker)
        python = raw.get("python")
        if python is not None:
            marker_parts.append(f"python_version{python}")

        is_optional = raw.get("optional", False)
        marker: str | None | UnkownMarker
        if is_optional and not marker_parts:
            marker = unknown_marker
        elif not marker_parts:
            marker = None
        else:
            marker = " and ".join(marker_parts)

        return cls(version, marker)


@dataclass
class ProjectSpec:
    name: str = "root"
    dependencies_groups: dict[str, dict[PackageName, list[ProjectDependency]]] = field(default_factory=dict)

    @classmethod
    def from_raw(cls, raw: dict[str, Any], com: Command) -> ProjectSpec:
        poetry = raw.get("tool", {}).get("poetry", {})
        if not poetry:  # poetry section is missing
            com.line_error("No poetry section found in the project spec")
            return cls()
        name = poetry.get("name", "root")
        groups: dict[str, dict[PackageName, list[ProjectDependency]]] = {}

        def add_group(name: str, root: dict[str, Any]):
            if name not in groups:
                groups[name] = {}
            for package, package_requirements in root.items():
                if isinstance(package_requirements, list):
                    raw_dep_specs = package_requirements
                else:
                    raw_dep_specs = [package_requirements]

                dep_specs = []
                for raw_dep_spec in raw_dep_specs:
                    if (dep := ProjectDependency.from_raw(raw_dep_spec)) is not None:
                        dep_specs.append(dep)
                    else:
                        com.line_error(f"Invalid dependency specification: {raw_dep_spec!r}")
                if dep_specs:
                    groups[name][to_package_name(package)] = dep_specs

        add_group("main", poetry.get("dependencies", {}))
        add_group("dev", poetry.get("dev-dependencies", {}))

        for group_name, group in poetry.get("group", {}).items():
            add_group(group_name, group.get("dependencies", {}))

        return cls(name, groups)
