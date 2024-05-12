from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from itertools import chain
from pathlib import Path
from typing import ClassVar

import tomli
from cleo.application import Application as CleoApplication
from cleo.commands.command import Command
from cleo.io.inputs.argument import Argument
from cleo.io.inputs.option import Option
from cleo.io.outputs.output import Verbosity
from httpx import Client
from poetry.console.application import Application as PoetryApplication
from poetry.plugins import ApplicationPlugin
from poetry.poetry import Poetry

from poetry_stale_dependencies.config import Config, parse_timedelta
from poetry_stale_dependencies.inspections import (
    NonStalePackageInspectResults,
    PackageInspectSpecs,
    StalePackageInspectResults,
)
from poetry_stale_dependencies.lock_spec import LockSpec
from poetry_stale_dependencies.project_spec import ProjectSpec


class ShowStaleCommand(Command):
    """
    Show stale dependencies in a python project
    """

    arguments: ClassVar[list[Argument]] = [
        Argument("packages", description="The packages to inspect", required=False, is_list=True)
    ]

    options: ClassVar[list[Option]] = [
        Option(
            "multi_threading_workers",
            "w",
            flag=False,
            requires_value=False,
            default=None,
            description="Number of workers to use for multi-threading IO lookups",
        ),
        Option(
            "project_path",
            "p",
            flag=False,
            requires_value=False,
            description="Path to the pyproject.toml file, not used if project is called from poetry",
            default="pyproject.toml",
        ),
        Option("time_to_stale", "s", flag=False, requires_value=False, description="Time to stale", default=None),
        Option("time_to_ripe", "r", flag=False, requires_value=False, description="Time to ripe", default=None),
    ]

    name = "stale-dependencies show"

    def _get_raw_pyproject(self, application: CleoApplication, project_path: str) -> dict:
        try:
            poetry: Poetry = application.poetry  # type: ignore[attr-defined]
        except AttributeError:
            with Path(project_path).open("rb") as f:
                return tomli.load(f)
        else:
            return poetry.pyproject.data

    def _get_config(self, pyproject: dict, time_to_stale: timedelta | None, time_to_ripe: timedelta | None) -> Config:
        raw = pyproject.get("tool", {}).get("stale-dependencies", {})
        ret = Config.from_raw(raw)
        if time_to_stale is not None:
            ret.time_to_stale = time_to_stale
        if time_to_ripe is not None:
            ret.time_to_ripe = time_to_ripe
        return ret

    def handle(self) -> int:
        packages_whitelist: list[str] = self.argument("packages")
        project_path: str = self.option("project_path")
        raw_workers = self.option("multi_threading_workers")
        n_workers: int | None
        if raw_workers is not None:
            n_workers = int(raw_workers)
            if n_workers < 1:
                n_workers = None
        else:
            n_workers = None
        raw_time_to_stale = self.option("time_to_stale")
        if raw_time_to_stale is not None:
            time_to_stale = parse_timedelta(raw_time_to_stale)
        else:
            time_to_stale = None
        raw_time_to_ripe = self.option("time_to_ripe")
        if raw_time_to_ripe is not None:
            time_to_ripe = parse_timedelta(raw_time_to_ripe)
        else:
            time_to_ripe = None

        if not (application := self.application):
            raise Exception("Application not found")
        raw_pyproject = self._get_raw_pyproject(application, project_path)
        config = self._get_config(raw_pyproject, time_to_stale, time_to_ripe)
        project = ProjectSpec.from_raw(raw_pyproject, self)
        lock_path = config.lockfile_path()
        if project_path and not lock_path.is_absolute():
            project_root = Path(project_path).parent
            lock_path = lock_path.relative_to(project_root)
        with lock_path.open("rb") as f:
            lockfile = tomli.load(f)
        lock_spec = LockSpec.from_raw(lockfile, self)
        inspec_specs: list[PackageInspectSpecs] = []
        for package, specs in lock_spec.get_packages(packages_whitelist, self):
            inspec_specs.extend(config.inspect_specs(package, specs))
        any_stale = False

        def inspect(spec: PackageInspectSpecs) -> list[StalePackageInspectResults | NonStalePackageInspectResults]:
            return spec.inspect_is_stale(client, lock_spec, project, self)

        with Client() as client, ThreadPoolExecutor(n_workers) as pool:
            inspect_results = pool.map(inspect, inspec_specs)

            for result in chain.from_iterable(inspect_results):
                if isinstance(result, StalePackageInspectResults):
                    any_stale = True
                result.writelines(self)
        if any_stale:
            return 1
        self.line("No stale dependencies found", verbosity=Verbosity.NORMAL)
        return 0


class StaleDependenciesPlugin(ApplicationPlugin):
    def activate(self, application: PoetryApplication) -> None:
        application.command_loader.register_factory(ShowStaleCommand.name, ShowStaleCommand)
        return super().activate(application)
