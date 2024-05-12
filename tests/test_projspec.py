from unittest.mock import MagicMock

from pytest import mark

from poetry_stale_dependencies.lock_spec import unknown_marker
from poetry_stale_dependencies.project_spec import ProjectDependency, ProjectSpec


@mark.parametrize("name", ["my_project", None])
def test_parse_projspec(name):
    content = {
        "tool": {
            "poetry": {
                "dependencies": {
                    "foo": "^1.0",
                    "bar": {
                        "version": "^2.0",
                        "markers": "sys_platform == 'win32'",
                    },
                },
                "dev-dependencies": {
                    "baz": "^3.0",
                },
                "group": {
                    "doc": {
                        "dependencies": {
                            "sphinx": [
                                {
                                    "version": "^4.0",
                                    "python": ">=3.6",
                                },
                                {
                                    "version": "^3.0",
                                    "python": "<3.6",
                                },
                            ],
                            "sphinx-rtd-theme": {
                                "version": "^5.0",
                            },
                            "myst-parser": {
                                "version": "^6.0",
                                "optional": True,
                            },
                        }
                    },
                    "dev": {"dependencies": {"jim": "^7.0", "too": {"im": "invalid"}}},
                },
            },
        }
    }
    if name:
        content["tool"]["poetry"]["name"] = name

    proj = ProjectSpec.from_raw(content, MagicMock())
    assert proj.name == (name or "root")
    assert proj.dependencies_groups == {
        "main": {
            "foo": [ProjectDependency("^1.0", None)],
            "bar": [ProjectDependency("^2.0", "sys_platform == 'win32'")],
        },
        "dev": {
            "baz": [ProjectDependency("^3.0", None)],
            "jim": [ProjectDependency("^7.0", None)],
        },
        "doc": {
            "sphinx": [
                ProjectDependency("^4.0", "python_version>=3.6"),
                ProjectDependency("^3.0", "python_version<3.6"),
            ],
            "sphinx-rtd-theme": [ProjectDependency("^5.0", None)],
            "myst-parser": [ProjectDependency("^6.0", unknown_marker)],
        },
    }


def test_empty_projspec():
    proj = ProjectSpec.from_raw({}, MagicMock())
    assert proj.name == "root"
    assert proj.dependencies_groups == {}
