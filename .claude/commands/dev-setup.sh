#!/bin/bash
# Quick development environment setup
# Sets up environment file and runs initial setup

echo "🛠️  Setting up development environment..."

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    
    # Generate a secure secret key
    echo "🔑 Generating secure SECRET_KEY..."
    SECRET_KEY=$(uv run python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
    
    # Update the .env file with the new secret key
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/SECRET_KEY=your-secret-key-here-generate-a-secure-50-char-key/SECRET_KEY=${SECRET_KEY}/" .env
    else
        # Linux
        sed -i "s/SECRET_KEY=your-secret-key-here-generate-a-secure-50-char-key/SECRET_KEY=${SECRET_KEY}/" .env
    fi
    
    echo "✅ .env file created with secure SECRET_KEY"
else
    echo "ℹ️  .env file already exists"
fi

# Install dependencies
echo "📦 Installing dependencies..."
uv sync

# Run migrations
echo "🗄️  Running database migrations..."
uv run python manage.py migrate

echo "✅ Development environment setup complete!"
echo "🚀 You can now run: uv run python manage.py runserver"