#!/bin/sh
# run various linters
set -e
echo "formatting..."
python -m ruff format poetry_stale_dependencies tests
echo "sorting import with ruff..."
python -m ruff check poetry_stale_dependencies tests --select I,F401 --fix --show-fixes