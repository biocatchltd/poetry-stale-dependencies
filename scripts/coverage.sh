#!/bin/sh
set -e
coverage run --branch --include="poetry_stale_dependencies/*" -m pytest -s tests "$@"
coverage html
coverage report -m
coverage xml