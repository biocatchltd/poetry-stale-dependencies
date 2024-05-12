# Poetry-Stale-Dependnecies

`poetry-stale-dependencies` is a poetry plugin that scans your dependencies and checks if there are newer versions available.

## Installation

```bash
poetry self add plugin poetry-stale-dependencies@latest
```

## Usage

```bash
# scan all dependencies for newer versions
poetry stale-dependencies show
# scan only specificed dependencies
poetry stale-dependencies show requests pytest
```

## Setup
You can customize the inspection settings by adding a `tool.stale-dependencies` section to your `pyproject.toml` file.

```toml
...
[tool.stale-dependencies]
# you can customize your lockfile location
lockfile = "poetry.lock"
# you can customize and include additional package sources (as they appear in your pyproject.toml)
sources = [
    "pypi",
    "my_custom_source"  # note that currently only unauthenticated sources are supported
]
time_to_stale = "1mo" # dependencies that have at lest this gap between their latest release and
# the installed release will be marked as satle, default is 2 weeks
time_to_ripe = "1d"  # releases that are less than 1 day old will not be considered, default is 3 days
# we can also have per-package configurations
[tool.stale-dependencies.packages]
requests = { time_to_stale = "2mo" }
pytest = { ignore_versions = ["6.0.0"] }
pydantic = { ignore = true }
numpy = { include_prereleases = true }
```