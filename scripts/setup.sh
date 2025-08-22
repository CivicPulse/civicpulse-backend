#!/bin/bash
# Quick setup script for CivicPulse Docker development environment

set -e

echo "🏗️  Setting up CivicPulse development environment..."
echo ""

# Check if Docker and Docker Compose are available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not available. Please install Docker Compose."
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📄 Creating .env file from template..."
    cp .env.example .env
    echo "✅ .env file created. You can customize it if needed."
else
    echo "📄 .env file already exists."
fi

# Build and start services
echo ""
echo "🏗️  Building Docker images..."
docker compose build

echo ""
echo "🚀 Starting services..."
docker compose up -d

# Wait a moment for services to start
echo ""
echo "⏳ Waiting for services to start..."
sleep 10

# Initialize database
echo ""
echo "🗄️  Initializing database..."
docker compose exec web /app/scripts/init-db.sh

echo ""
echo "🎉 Setup complete! Your development environment is ready."
echo ""
echo "📍 Useful commands:"
echo "  • View logs: docker compose logs -f"
echo "  • Stop services: docker compose down"
echo "  • Restart services: docker compose restart"
echo "  • Run Django commands: docker compose exec web python manage.py <command>"
echo ""
echo "🌐 Access points:"
echo "  • Application: http://localhost:8000"
echo "  • Admin panel: http://localhost:8000/admin"
echo "  • Database: localhost:5432 (civicpulse/civicpulse)"
echo "  • Redis: localhost:6379"
echo ""