#!/bin/bash
# Complete test run with coverage reporting
# Generates both terminal and HTML coverage reports

echo "📊 Running tests with full coverage analysis..."
uv run pytest --cov-report=term --cov-report=html --tb=short -q

if [ $? -eq 0 ]; then
    echo "✅ Tests passed! Coverage report generated in htmlcov/"
    echo "📈 Open htmlcov/index.html to view detailed coverage report"
else
    echo "❌ Tests failed. Check output above for details."
fi