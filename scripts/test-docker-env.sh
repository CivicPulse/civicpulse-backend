#!/bin/bash
# Test script for Docker development environment

set -e

echo "🧪 Testing CivicPulse Docker development environment..."
echo ""

# Test 1: Validate Docker Compose configuration
echo "1. 📋 Testing Docker Compose configuration..."
if docker compose config --quiet; then
    echo "   ✅ Docker Compose configuration is valid"
else
    echo "   ❌ Docker Compose configuration has errors"
    exit 1
fi

# Test 2: Check required files exist
echo ""
echo "2. 📁 Checking required files..."
FILES_TO_CHECK=(
    ".env"
    "Dockerfile"
    "docker-compose.yml"
    "pyproject.toml"
    "uv.lock"
    "scripts/setup.sh"
    "scripts/init-db.sh"
    "civicpulse/management/commands/setup_development.py"
)

for file in "${FILES_TO_CHECK[@]}"; do
    if [ -f "$file" ]; then
        echo "   ✅ $file exists"
    else
        echo "   ❌ $file is missing"
        exit 1
    fi
done

# Test 3: Validate environment file
echo ""
echo "3. 🔧 Checking environment configuration..."
if grep -q "DATABASE_URL=postgresql://civicpulse:civicpulse@db:5432/civicpulse" .env; then
    echo "   ✅ Database URL is configured for Docker"
else
    echo "   ❌ Database URL is not configured for Docker"
    exit 1
fi

if grep -q "REDIS_URL=redis://redis:6379/0" .env; then
    echo "   ✅ Redis URL is configured for Docker"
else
    echo "   ❌ Redis URL is not configured for Docker"
    exit 1
fi

# Test 4: Check script permissions
echo ""
echo "4. 🔑 Checking script permissions..."
SCRIPTS_TO_CHECK=(
    "scripts/setup.sh"
    "scripts/init-db.sh"
)

for script in "${SCRIPTS_TO_CHECK[@]}"; do
    if [ -x "$script" ]; then
        echo "   ✅ $script is executable"
    else
        echo "   ❌ $script is not executable"
        chmod +x "$script"
        echo "   🔧 Fixed permissions for $script"
    fi
done

# Test 5: Validate Python code syntax
echo ""
echo "5. 🐍 Checking Python syntax..."
if python -m py_compile civicpulse/management/commands/setup_development.py; then
    echo "   ✅ setup_development.py syntax is valid"
else
    echo "   ❌ setup_development.py has syntax errors"
    exit 1
fi

# Test 6: Check documentation
echo ""
echo "6. 📚 Checking documentation..."
if [ -f "docs/development/docker-setup.md" ]; then
    echo "   ✅ Docker setup documentation exists"
else
    echo "   ❌ Docker setup documentation is missing"
    exit 1
fi

echo ""
echo "✅ All tests passed! The Docker development environment is ready."
echo ""
echo "🚀 To start the environment, run:"
echo "   ./scripts/setup.sh"
echo ""
echo "📖 For detailed instructions, see:"
echo "   docs/development/docker-setup.md"
echo ""