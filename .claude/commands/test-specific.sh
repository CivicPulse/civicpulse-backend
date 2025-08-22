#!/bin/bash
# Run specific tests by pattern or file
# Usage: ./test-specific.sh test_authentication
# Usage: ./test-specific.sh tests/test_models.py::TestCase::test_method

if [ -z "$1" ]; then
    echo "❌ Usage: $0 <test_pattern>"
    echo "Examples:"
    echo "  $0 test_authentication"
    echo "  $0 tests/test_models.py"
    echo "  $0 tests/test_models.py::TestCase::test_method"
    exit 1
fi

echo "🎯 Running specific tests matching: $1"
uv run pytest -v --tb=short "$1"