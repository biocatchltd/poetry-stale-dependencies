from pathlib import Path
import tomli
from cleo.commands.command import Command
from cleo.application import Application as CleoApplication
from poetry.console.application import Application as PoetryApplication
from poetry.plugins import ApplicationPlugin
from poetry.poetry import Poetry
from poetry_stale_dependencies.config import Config
from poetry_stale_dependencies.inspections import PackageInspectSpecs
from poetry_stale_dependencies.lock_spec import LockSpec
from httpx import Client
from cleo.io.outputs.output import Verbosity
from cleo.io.inputs.argument import Argument

class ShowStaleCommand(Command):
    """
    Show stale dependencies in a python project
    stale-dependencies show
        {project_path? : Path to the pyproject.toml file}
    """

    arguments = [
        Argument("project_path", required=False, description="Path to the pyproject.toml file", default="pyproject.toml")
    ]

    name = "stale-dependencies show"

    def _get_config(self, application: CleoApplication, project_path: str) -> Config:
        try:
            poetry: Poetry = application.poetry
        except AttributeError:
            with Path(project_path).open() as f:
                pyproject = tomli.load(f)
        else:
            pyproject = poetry.pyproject.data
        
        raw = pyproject.get("tool", {}).get("stale-dependencies", {})
        return Config.from_raw(raw)

    def handle(self):
        project_path: str = self.argument("project_path")
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
        with Client() as client:
            for inspec_spec in inspec_specs:
                any_stale |= inspec_spec.inspect(client, self)
        if not any_stale:
            self.line("No stale dependencies found", verbosity=Verbosity.NORMAL)
        return 0

        
        
        


class StaleDependenciesPlugin(ApplicationPlugin):
    def activate(self, application: PoetryApplication) -> None:
        application.command_loader.register_factory(ShowStaleCommand.name, ShowStaleCommand)
        return super().activate(application)