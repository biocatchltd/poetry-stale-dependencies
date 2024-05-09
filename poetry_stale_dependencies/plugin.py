from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
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

from poetry_stale_dependencies.config import Config
from poetry_stale_dependencies.inspections import PackageInspectSpecs
from poetry_stale_dependencies.lock_spec import LockSpec


class ShowStaleCommand(Command):
    """
    Show stale dependencies in a python project
    stale-dependencies show
        {project_path? : Path to the pyproject.toml file}
    """

    arguments: ClassVar[list[Argument]] = [
        Argument(
            "project_path", required=False, description="Path to the pyproject.toml file", default="pyproject.toml"
        )
    ]

    options: ClassVar[list[Option]] = [
        Option("multi_threading_workers", "w", flag=False, requires_value=False, default=None),
    ]

    name = "stale-dependencies show"

    def _get_config(self, application: CleoApplication, project_path: str) -> Config:
        try:
            poetry: Poetry = application.poetry  # type: ignore[attr-defined]
        except AttributeError:
            with Path(project_path).open("rb") as f:
                pyproject = tomli.load(f)
        else:
            pyproject = poetry.pyproject.data

        raw = pyproject.get("tool", {}).get("stale-dependencies", {})
        return Config.from_raw(raw)

    def handle(self) -> int:
        project_path: str = self.argument("project_path")
        raw_workers = self.option("multi_threading_workers")
        n_workers: int | None
        if raw_workers is not None:
            n_workers = int(raw_workers)
            if n_workers < 1:
                n_workers = None
        else:
            n_workers = None

        if not (application := self.application):
            raise Exception("Application not found")
        config = self._get_config(application, project_path)
        lock_path = config.lockfile_path()
        if project_path and not lock_path.is_absolute():
            project_root = Path(project_path).parent
            lock_path = lock_path.relative_to(project_root)
        with lock_path.open("rb") as f:
            lockfile = tomli.load(f)
        lock_spec = LockSpec.from_raw(lockfile, self)
        inspec_specs: list[PackageInspectSpecs] = []
        for package, specs in lock_spec.packages.items():
            inspec_specs.extend(config.inspect_specs(package, specs))
        any_stale = False
        lock = Lock()
        with Client() as client:
            with ThreadPoolExecutor(n_workers) as pool:
                inspect_results = pool.map(lambda spec: spec.inspect(client, self, lock), inspec_specs)

            for result in inspect_results:
                any_stale |= result
        if any_stale:
            return 1
        self.line("No stale dependencies found", verbosity=Verbosity.NORMAL)
        return 0


class StaleDependenciesPlugin(ApplicationPlugin):
    def activate(self, application: PoetryApplication) -> None:
        application.command_loader.register_factory(ShowStaleCommand.name, ShowStaleCommand)
        return super().activate(application)
