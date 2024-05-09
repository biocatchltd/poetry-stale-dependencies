from collections.abc import Mapping, Sequence
from typing import Any


def simple_v1_release(filename: str, upload_time: str, yanked: bool = False) -> Mapping[str, Any]:
    return {
        "filename": filename,
        "upload-time": upload_time,
        "yanked": yanked,
    }


def simple_v1_package(releases: Mapping[str, Sequence[Mapping[str, Any]]]):
    return {
        "versions": list(releases.keys()),
        "files": [file for files in releases.values() for file in files],
    }
