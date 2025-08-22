#!/bin/bash
# Complete code quality check before committing
# Runs linting, formatting, type checking, and security scans

echo "🔍 Running complete code quality checks..."

# Format code
echo "📝 Formatting code..."
uv run ruff format .

# Check and fix linting issues
echo "🧹 Checking and fixing linting issues..."
uv run ruff check --fix .

# Type checking
echo "🔬 Running type checks..."
uv run mypy civicpulse/

# Security scan
echo "🔐 Running security scan..."
uv run bandit -r civicpulse/

# Final linting check (should be clean now)
echo "✨ Final linting check..."
uv run ruff check .

if [ $? -eq 0 ]; then
    echo "✅ All quality checks passed! Code is ready to commit."
else
    echo "❌ Some quality checks failed. Please review and fix issues above."
    exit 1
fi