#!/bin/bash
# Fast test run for quick development feedback
# Runs tests with minimal output and early exit on first failure

echo "🚀 Running fast tests (first failure exits)..."
uv run pytest -x -q --tb=short --disable-warnings