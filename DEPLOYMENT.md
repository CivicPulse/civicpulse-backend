# CivicPulse Backend Deployment Guide

## Overview

This document outlines the deployment infrastructure and processes for the CivicPulse Backend application. The CI/CD pipeline is designed for automated, secure, and reliable deployments with comprehensive quality gates.

## CI/CD Pipeline Architecture

### Current Status
- ✅ **CI Workflows**: Fully operational (lint, test, security, coverage)
- ✅ **Docker Configuration**: Production-ready containers
- ✅ **Branch Protection**: Configured via `.github/settings.yml`
- ⏳ **Deployment Workflows**: Ready but disabled pending infrastructure setup
- ⏳ **Environment Configuration**: Staging and Production environments defined

### Pipeline Stages

#### 1. Pull Request Validation
- **Trigger**: Pull request opened/updated
- **Workflow**: `.github/workflows/pr-validation.yml`
- **Checks**:
  - Code linting (Ruff)
  - Type checking (mypy)
  - Test suite with coverage (pytest)
  - Security scanning (Bandit, pip-audit)
  - Conventional commits validation
  - Large file detection

#### 2. Continuous Integration
- **Trigger**: Push to `main` or `develop` branches
- **Workflow**: `.github/workflows/ci.yml`
- **Quality Gates**:
  - **Lint & Format Check**: Ruff code formatting and linting
  - **Type Check**: MyPy static type analysis
  - **Test**: Full test suite with 80% coverage requirement
  - **Security Scan**: Bandit security analysis and dependency audit
  - **CI Summary**: Aggregated status check

#### 3. Deployment Pipeline (Ready for Activation)
- **Trigger**: Push to `main` branch (manual approval for production)
- **Workflow**: `.github/workflows/deploy.yml`
- **Stages**:
  1. **Test**: Re-run CI pipeline for final validation
  2. **Build**: Create Docker images and push to GHCR
  3. **Deploy Staging**: Automated staging deployment
  4. **Deploy Production**: Manual approval required

## Infrastructure Requirements

### Container Registry
- **Provider**: GitHub Container Registry (GHCR)
- **Images**: 
  - `ghcr.io/civicpulse/civicpulse-backend:latest`
  - `ghcr.io/civicpulse/civicpulse-backend:staging`
  - `ghcr.io/civicpulse/civicpulse-backend:production`
  - `ghcr.io/civicpulse/civicpulse-backend:${SHA}`

### Environment Configuration

#### Staging Environment
```bash
# Required Environment Variables
DATABASE_URL=postgresql://user:pass@staging-db:5432/civicpulse_staging
REDIS_URL=redis://staging-redis:6379/0
SECRET_KEY=${STAGING_SECRET_KEY}
ALLOWED_HOSTS=staging.civicpulse.com
DEBUG=False
DJANGO_SETTINGS_MODULE=cpback.settings.production

# Optional Performance Tuning
GUNICORN_WORKERS=2
GUNICORN_THREADS=2
GUNICORN_TIMEOUT=30
```

#### Production Environment
```bash
# Required Environment Variables
DATABASE_URL=postgresql://user:pass@prod-db:5432/civicpulse
REDIS_URL=redis://prod-redis:6379/0
SECRET_KEY=${PRODUCTION_SECRET_KEY}
ALLOWED_HOSTS=api.civicpulse.com,civicpulse.com
DEBUG=False
DJANGO_SETTINGS_MODULE=cpback.settings.production

# Performance Configuration
GUNICORN_WORKERS=4
GUNICORN_THREADS=2
GUNICORN_WORKER_CONNECTIONS=1000
GUNICORN_MAX_REQUESTS=1000
GUNICORN_TIMEOUT=30
```

### Required GitHub Secrets

#### Repository Secrets
```bash
# Production Environment
PRODUCTION_HOST            # SSH host for production deployment
PRODUCTION_URL            # Production application URL
PRODUCTION_SECRET_KEY     # Django secret key for production

# Staging Environment  
STAGING_HOST              # SSH host for staging deployment
STAGING_URL              # Staging application URL
STAGING_SECRET_KEY       # Django secret key for staging

# Database Configuration
POSTGRES_PASSWORD         # Database password
REDIS_PASSWORD           # Redis password (optional)

# External Services
CODECOV_TOKEN            # Code coverage reporting
DJANGO_SUPERUSER_USERNAME # Auto-create superuser
DJANGO_SUPERUSER_PASSWORD # Superuser password
DJANGO_SUPERUSER_EMAIL   # Superuser email
```

### Infrastructure Components

#### Database Requirements
- **PostgreSQL 16+** with PostGIS extension
- **Minimum Resources**: 2 CPU, 4GB RAM, 50GB storage
- **Backup Strategy**: Daily automated backups with 30-day retention
- **Connection Pool**: PgBouncer recommended for production

#### Cache & Message Broker
- **Redis 7+** for caching and Celery task queue
- **Minimum Resources**: 1 CPU, 2GB RAM, 10GB storage
- **Persistence**: AOF enabled for durability

#### Application Servers
- **Staging**: 2 CPU, 4GB RAM, 20GB storage
- **Production**: 4 CPU, 8GB RAM, 50GB storage
- **Load Balancer**: Nginx or cloud load balancer
- **Auto-scaling**: Configure based on CPU/memory thresholds

#### Container Orchestration Options

##### Option 1: Docker Compose (Recommended for small deployments)
```bash
# Deploy using production compose file
docker-compose -f docker-compose.prod.yml up -d
```

##### Option 2: Kubernetes (Recommended for scale)
- **Namespace**: `civicpulse-staging`, `civicpulse-production`
- **Ingress Controller**: Nginx or cloud provider
- **Resource Limits**: Defined in deployment manifests
- **Horizontal Pod Autoscaling**: Based on CPU/memory metrics

## Deployment Activation Steps

### Prerequisites Checklist
- [ ] Container registry configured (GHCR)
- [ ] Staging environment provisioned
- [ ] Production environment provisioned  
- [ ] GitHub secrets configured
- [ ] Database servers ready
- [ ] Redis servers ready
- [ ] SSL certificates obtained
- [ ] Domain DNS configured
- [ ] Monitoring stack ready

### Step 1: Install GitHub Settings App
1. Visit: https://github.com/apps/settings
2. Install on the CivicPulse organization
3. Configure repository access for `civicpulse-backend`

### Step 2: Configure Branch Protection
The `.github/settings.yml` file will automatically configure:
- Main branch protection rules
- Required status checks
- Environment protection rules
- Repository labels

### Step 3: Test Staging Deployment
```bash
# Enable staging deployment workflow
git push origin main

# Monitor deployment progress
gh run list --workflow=deploy.yml --limit=1

# Verify staging health
curl -f https://staging.civicpulse.com/civicpulse/health/
```

### Step 4: Enable Production Deployment
1. Update `deploy.yml` workflow to remove deployment placeholders
2. Configure production environment secrets
3. Test production deployment with manual approval

## Monitoring and Observability

### Health Checks
- **Application**: `/civicpulse/health/`
- **Database**: Connection and migration status
- **Redis**: Ping and memory usage
- **Celery**: Worker and beat status

### Logging Strategy
- **Application Logs**: Structured JSON logging via Loguru
- **Access Logs**: Nginx/Gunicorn access logs
- **Error Logs**: Separate error log files
- **Centralized Logging**: Consider ELK stack or cloud logging

### Metrics Collection
- **Application Metrics**: Django performance metrics
- **Infrastructure Metrics**: CPU, memory, disk, network
- **Database Metrics**: Connection pool, query performance
- **Cache Metrics**: Redis hit rate and memory usage

## Security Considerations

### Container Security
- ✅ Non-root user execution
- ✅ Multi-stage Docker builds
- ✅ Minimal base images (Alpine/Slim)
- ✅ Security scanning in CI pipeline
- ✅ Dependency vulnerability scanning

### Network Security
- TLS/SSL termination at load balancer
- Internal service communication
- Database connection encryption
- Redis authentication (optional password)

### Secrets Management
- Environment variables for configuration
- GitHub Secrets for CI/CD credentials
- Consider HashiCorp Vault for advanced secrets management

## Rollback Procedures

### Automated Rollback Triggers
- Health check failures
- Smoke test failures
- High error rates (5xx responses)

### Manual Rollback Process
```bash
# Rollback to previous image
docker pull ghcr.io/civicpulse/civicpulse-backend:previous
docker tag ghcr.io/civicpulse/civicpulse-backend:previous ghcr.io/civicpulse/civicpulse-backend:production

# Or rollback via git
git revert <commit-hash>
git push origin main
```

## Performance Optimization

### Application Level
- Database query optimization
- Redis caching strategy  
- Static file serving via CDN
- Celery task optimization

### Infrastructure Level
- Database connection pooling
- Redis memory optimization
- Container resource limits
- Horizontal pod autoscaling

## Troubleshooting Guide

### Common Issues
1. **Database Connection Errors**: Check DATABASE_URL and network connectivity
2. **Redis Connection Issues**: Verify REDIS_URL and authentication
3. **Static Files Not Loading**: Ensure collectstatic ran successfully
4. **Celery Tasks Failing**: Check Redis connection and worker logs
5. **Health Check Failures**: Verify all dependencies are healthy

### Debug Commands
```bash
# Check container logs
docker logs <container-id>

# Access container shell
docker exec -it <container-id> /bin/bash

# Run Django management commands
docker exec -it <container-id> python manage.py <command>

# Check database connectivity
docker exec -it <container-id> python manage.py dbshell
```

## Contact and Support

### Team Contacts
- **DevOps Lead**: Kerry Hatcher (kerry@kerryhatcher.com)
- **Development Team**: CivicPulse GitHub Organization
- **Infrastructure Team**: TBD

### Documentation Updates
This document should be updated whenever:
- Infrastructure changes are made
- New deployment requirements are added
- Security procedures are modified
- Performance optimizations are implemented

---

**Last Updated**: August 22, 2025  
**Document Version**: 1.0  
**Author**: Grace Miller (Deployment Engineer)