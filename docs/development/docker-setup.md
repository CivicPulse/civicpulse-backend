# Docker Development Environment Setup

This guide will help you set up the CivicPulse backend development environment using Docker.

## Prerequisites

- **Docker**: Version 20.0+ 
- **Docker Compose**: Version 2.0+ (Docker Compose V2)
- **Git**: For cloning the repository

### Installing Docker

#### Windows/Mac
Download and install [Docker Desktop](https://www.docker.com/products/docker-desktop/)

#### Linux (Ubuntu/Debian)
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER

# Log out and log back in, then test
docker --version
docker compose version
```

## Quick Start

The fastest way to get started is using our setup script:

```bash
# Clone the repository
git clone https://github.com/CivicPulse/civicpulse-backend.git
cd civicpulse-backend

# Run the setup script
./scripts/setup.sh
```

This script will:
1. Create your `.env` file from the template
2. Build the Docker images
3. Start all services
4. Initialize the database
5. Create a default superuser

## Manual Setup

If you prefer to set up manually or need to customize the process:

### 1. Environment Configuration

```bash
# Create environment file
cp .env.example .env

# Edit configuration (optional)
nano .env
```

Key environment variables for Docker:
- `DATABASE_URL=postgresql://civicpulse:civicpulse@db:5432/civicpulse`
- `REDIS_URL=redis://redis:6379/0`
- `DEBUG=True`

### 2. Build and Start Services

```bash
# Build Docker images
docker compose build

# Start services in background
docker compose up -d

# View logs (optional)
docker compose logs -f
```

### 3. Initialize Database

```bash
# Run database setup
docker compose exec web python manage.py setup_development

# Or run the initialization script
docker compose exec web /app/scripts/init-db.sh
```

## Services Overview

The Docker environment includes these services:

| Service | Description | Port | Health Check |
|---------|-------------|------|--------------|
| **web** | Django application | 8000 | N/A |
| **db** | PostgreSQL 16 database | 5432 | `pg_isready` |
| **redis** | Redis cache/broker | 6379 | `redis-cli ping` |
| **celery** | Background task worker | - | N/A |
| **celery-beat** | Task scheduler | - | N/A |

## Access Points

Once running, you can access:

- **Application**: http://localhost:8000
- **Admin Panel**: http://localhost:8000/admin
  - Username: `admin`
  - Password: `admin123`
- **Database**: localhost:5432
  - Database: `civicpulse`
  - Username: `civicpulse`
  - Password: `civicpulse`
- **Redis**: localhost:6379

## Development Workflow

### Hot Reload

Code changes are automatically detected and reloaded:

```bash
# Edit any Python file
echo "# This change will trigger reload" >> civicpulse/models.py

# Watch the logs to see reload
docker compose logs -f web
```

### Running Django Commands

```bash
# Make migrations
docker compose exec web python manage.py makemigrations

# Run migrations
docker compose exec web python manage.py migrate

# Create superuser
docker compose exec web python manage.py createsuperuser

# Django shell
docker compose exec web python manage.py shell

# Run tests
docker compose exec web python manage.py test

# Install new dependencies (rebuild required)
docker compose exec web uv add package-name
docker compose build web
docker compose restart web
```

### Database Operations

```bash
# Access PostgreSQL shell
docker compose exec db psql -U civicpulse -d civicpulse

# Backup database
docker compose exec db pg_dump -U civicpulse civicpulse > backup.sql

# Restore database
docker compose exec -T db psql -U civicpulse -d civicpulse < backup.sql

# Reset database
docker compose down
docker volume rm civicpulse-backend_postgres_data
docker compose up -d
docker compose exec web python manage.py setup_development
```

### Managing Services

```bash
# View status
docker compose ps

# View logs
docker compose logs -f [service_name]

# Restart specific service
docker compose restart web

# Stop all services
docker compose down

# Stop and remove volumes
docker compose down -v

# Rebuild and restart
docker compose build && docker compose up -d
```

## Troubleshooting

### Common Issues

#### Port Already in Use
```bash
# Find process using port 8000
lsof -i :8000
# or
netstat -tulpn | grep 8000

# Kill process or use different port
docker compose -f docker-compose.yml -p civicpulse_alt up -d
```

#### Database Connection Issues
```bash
# Check database logs
docker compose logs db

# Restart database
docker compose restart db

# Check database health
docker compose exec db pg_isready -U civicpulse -d civicpulse
```

#### Redis Connection Issues
```bash
# Check Redis logs
docker compose logs redis

# Test Redis connection
docker compose exec redis redis-cli ping

# Restart Redis
docker compose restart redis
```

#### Container Build Issues
```bash
# Clean build (no cache)
docker compose build --no-cache

# Remove all containers and volumes
docker compose down -v
docker system prune -a
```

### Performance Issues

#### Slow Database Queries
- Check Django Debug Toolbar at http://localhost:8000
- Review database logs: `docker compose logs db`

#### Memory Issues
```bash
# Check container resource usage
docker stats

# Increase Docker memory limit in Docker Desktop settings
```

## Environment Variables

Key variables you can customize in `.env`:

```bash
# Database
DATABASE_URL=postgresql://civicpulse:civicpulse@db:5432/civicpulse

# Redis
REDIS_URL=redis://redis:6379/0

# Django
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

# Email (development)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

# Security
SECURE_SSL_REDIRECT=False
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
```

## Production Differences

This setup is for **development only**. For production:

- Use `docker-compose.prod.yml` (if available)
- Set `DEBUG=False`
- Use proper SECRET_KEY
- Configure SSL/TLS
- Use external database and Redis services
- Set up proper logging and monitoring

## Getting Help

If you encounter issues:

1. Check the logs: `docker compose logs -f`
2. Verify your `.env` file matches the template
3. Ensure Docker has enough resources allocated
4. Try a clean rebuild: `docker compose build --no-cache`
5. Check the troubleshooting section above

For more help, check the main README.md or open an issue on GitHub.