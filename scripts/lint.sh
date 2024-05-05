#!/bin/sh
# run various linters
set -e
echo "running ruff..."
python -m ruff format poatry_stale_dependencies tests --check
python -m ruff check poatry_stale_dependencies tests
echo "running mypy..."
python3 -m mypy --show-error-codes poatry_stale_dependencies
