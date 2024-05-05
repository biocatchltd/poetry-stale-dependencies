#!/bin/sh
set -e
coverage run --branch --include="poetry_lock_listener/*" -m pytest -sm "not requires_input" tests "$@"
echo 4 | coverage run --append --branch --include="poetry_lock_listener/*" -m pytest -sm "requires_input" tests "$@"
coverage html
coverage report -m
coverage xml