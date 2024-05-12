import re
from datetime import timedelta
from typing import NewType

PackageName = NewType("PackageName", str)
_package_repl_pattern = re.compile(r"[._-]+")


def to_package_name(name: str) -> PackageName:
    name = _package_repl_pattern.sub("-", name).lower()
    return PackageName(name)


def render_timedelta(td: timedelta) -> str:
    if td.days >= 365:
        if td.days % 365 >= 30:
            return f"{td.days // 365}y {td.days % 365 // 30}mo"
        return f"{td.days // 365}y"
    if td.days >= 30:
        return f"{td.days // 30}mo"
    return f"{td.days}d"
