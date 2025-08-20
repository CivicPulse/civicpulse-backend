# CivicPulse Backend

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Django](https://img.shields.io/badge/django-4.2%2B-green.svg)](https://www.djangoproject.com/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## 📋 Project Overview

CivicPulse is a comprehensive multi-tenant CRM/CMS platform designed specifically for nonprofits, civic organizations, and political groups. It centralizes outreach efforts, governance transparency, election tracking, volunteer coordination, and community engagement into a single, powerful platform.

The system is built with a focus on:
- **Security-first architecture** with multi-tenant data isolation
- **Accessibility** for users of all technical skill levels
- **Scalability** from small local organizations to large multi-organization deployments
- **Open-source transparency** while supporting commercial SaaS deployment

### Who Is This For?

- **Nonprofits** managing donors, volunteers, and community programs
- **Civic Organizations** tracking governance, meetings, and community issues
- **Political Groups** coordinating campaigns, canvassing, and voter outreach
- **Community Service Organizations** organizing events and volunteer efforts
- **Political Action Committees** managing compliance and member communications

## 🚀 Key Features

### Core Features

#### 📞 Contact & Outreach Management
- Comprehensive CRM for constituents, donors, volunteers, and officials
- Interaction logging with outcomes and follow-up scheduling
- Task assignment with hierarchical delegation
- AI-powered voice note transcription for field reporting
- Integrated voter database with registration status and vote history

#### 👥 Member Management
- Member status tracking (active/inactive)
- Dues payment management
- Certification and credential tracking
- Training completion monitoring
- Unified profiles (member can also be voter, volunteer, and/or official)

#### 🏛️ Governance & Elections
- **Elected Officials Database**: Profiles, voting records, and issue stances
- **Election Tracking**: Calendar of local/state/federal elections with candidate info
- **Governance Directory**: Local boards, commissions, and authorities
- **Public Transparency Portal**: Optional public-facing accountability features

#### 📄 Document Management
- Fine-grained role-based access control
- Full-text, knowledge graph, and AI vector search
- Public/private sharing with secure URLs
- Tag-based organization and categorization

#### 📅 Calendaring & Tasks
- Multiple public/private calendars
- CalDAV/.ics subscription support
- Hierarchical task assignment (team → individual)
- Integration with meetings and elections

### Advanced Features

#### 🎓 Training Modules
- Video-first content with YouTube/Vimeo integration
- Role-based training paths
- Progress tracking and acknowledgments
- Mobile-friendly with offline capability
- Quiz and certification support (v1+)

#### 💬 Community Input & Prioritization
- Structured submission system for concerns/ideas
- Voting-based prioritization (not a forum)
- Moderation workflows with duplicate detection
- GIS integration for geographic issue mapping
- Connection to meeting agendas and task creation

#### 🤖 AI-Powered Assistance
- Natural language Q&A ("Who covers zoning issues?")
- Automated meeting minute summarization
- Smart cross-entity search
- Content recommendations

#### 🗺️ GIS & Mapping
- Interactive district and precinct maps
- Layered data visualization
- Shapefile and GeoJSON support
- Heatmap analytics for issue concentration
- Integration with field operations

#### 🔐 Volunteer Safety & Field Tools
- Periodic location check-ins
- Admin visibility dashboard
- Quick route assignment
- Offline data collection with sync

#### 📊 Comprehensive Audit Trail System
- **Complete Activity Tracking**: Every model change, authentication event, and system action is logged
- **Security Monitoring**: Real-time detection of suspicious activities and security threats
- **Compliance Support**: Meets requirements for GDPR, CCPA, and other privacy regulations
- **Forensic Capabilities**: Detailed change tracking for investigations and audits
- **Administrative Insights**: Rich reporting and export capabilities for system analysis
- **Immutable Records**: Tamper-proof audit logs with UUID primary keys
- **Advanced Search**: Full-text search across all audit data with intelligent filtering
- **Export Functionality**: CSV exports and detailed audit reports for compliance

## 🛠️ Technology Stack

### Backend
- **Framework**: Django 4.2+ with Django REST Framework
- **Language**: Python 3.11+
- **Real-time**: Django Channels for WebSocket support
- **Task Queue**: Celery with Redis broker
- **CMS**: Wagtail (headless mode)

### Database & Storage
- **Primary DB**: PostgreSQL 14+ with PostGIS extension
- **Cache/Queue**: Redis 7+
- **Search**: PostgreSQL Full-Text (MVP), OpenSearch (production)
- **Media Storage**: S3-compatible or Cloudflare Images/Stream

### Infrastructure
- **Container**: Docker with multi-stage builds
- **Orchestration**: Kubernetes with Helm charts
- **Authentication**: Authentik for SSO/SAML/OIDC
- **Monitoring**: Prometheus + Grafana
- **Logging**: Loguru with centralized aggregation

### Development Tools
- **Package Manager**: uv (modern Python packaging)
- **Code Quality**: Ruff, Black, Bandit, pre-commit
- **Testing**: pytest with coverage reporting
- **CI/CD**: GitHub Actions
- **Documentation**: Sphinx with auto-generated API docs

## 🏗️ Architecture Overview

### Multi-Tenancy Approach

CivicPulse uses a **schema-per-tenant** architecture with PostgreSQL schemas, providing:
- Strong data isolation between organizations
- Shared reference data in public schema
- Subdomain-based routing (org1.civicpulse.com)
- Option for completely isolated deployments

### Modular Monolith Design

The application follows a modular monolith pattern:
- Core platform with plugin-like Django apps
- Clear bounded contexts between modules
- Internal APIs for module communication
- Migration path to microservices if needed

### API-First Development

All functionality exposed through documented REST APIs:
- OpenAPI/Swagger documentation
- Frontend consumes same APIs as third-party integrations
- No private/special frontend APIs
- Supports future mobile and desktop clients

## 🚦 Getting Started

### Prerequisites

- Python 3.11 or higher
- PostgreSQL 14+ with PostGIS extension
- Redis 7+
- Node.js 18+ (for frontend development)
- Docker and Docker Compose (optional but recommended)

### Installation

#### Using Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/your-org/civicpulse-backend.git
cd civicpulse-backend

# Copy environment template
cp .env.example .env
# Edit .env with your configuration

# Start services
docker-compose up -d

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser

# Access at http://localhost:8000
```

#### Local Development

```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and enter directory
git clone https://github.com/your-org/civicpulse-backend.git
cd civicpulse-backend

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv sync

# Setup PostgreSQL and Redis (or use Docker for these)
# Create database and enable PostGIS extension

# Copy and configure environment
cp .env.example .env
# Edit .env with database credentials

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

## 📁 Project Structure

```
civicpulse-backend/
├── civicpulse/              # Main application package
│   ├── core/                # Core functionality and base models
│   ├── members/             # Member management module
│   ├── contacts/            # CRM and outreach module
│   ├── elections/           # Election tracking module
│   ├── governance/          # Governance directory module
│   ├── documents/           # Document management module
│   ├── training/            # Training and LMS module
│   ├── community/           # Community input module
│   ├── gis/                 # GIS and mapping module
│   ├── cms/                 # Wagtail CMS integration
│   └── api/                 # API endpoints and serializers
├── config/                  # Django configuration
│   ├── settings/            # Environment-specific settings
│   ├── urls.py              # URL configuration
│   └── wsgi.py              # WSGI/ASGI configuration
├── docs/                    # Documentation
│   ├── api/                 # API documentation
│   ├── deployment/          # Deployment guides
│   └── development/         # Development guides
├── scripts/                 # Utility scripts
├── tests/                   # Test suites
├── docker/                  # Docker configurations
├── helm/                    # Kubernetes Helm charts
└── requirements/            # Python dependencies
```

## 🧑‍💻 Development

### Coding Standards

- **Python**: Follow PEP 8, enforced by Ruff and Black
- **Git**: Use Conventional Commits (feat:, fix:, docs:, etc.)
- **Testing**: Minimum 80% code coverage required
- **Documentation**: All public APIs must be documented

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=civicpulse --cov-report=html

# Run specific test module
pytest tests/test_members.py

# Run with parallel execution
pytest -n auto
```

### Code Quality Checks

```bash
# Format code
black .
ruff format .

# Lint code
ruff check .

# Security scan
bandit -r civicpulse/

# Type checking
mypy civicpulse/
```

### Database Migrations

```bash
# Create new migration
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Show migration SQL
python manage.py sqlmigrate app_name migration_number
```

## 🚀 Deployment

### Deployment Options

1. **SaaS Multi-Tenant**: Full platform with all organizations
2. **Self-Hosted Single Tenant**: One organization deployment
3. **Docker Compose**: Simple container deployment
4. **Kubernetes**: Production-grade with Helm charts

### Docker Deployment

```bash
# Build production image
docker build -t civicpulse-backend:latest .

# Run with docker-compose
docker-compose -f docker-compose.prod.yml up -d
```

### Kubernetes Deployment

```bash
# Add Helm repository
helm repo add civicpulse https://charts.civicpulse.org
helm repo update

# Install with custom values
helm install civicpulse civicpulse/backend \
  --values values.yaml \
  --namespace civicpulse \
  --create-namespace
```

### Environment Variables

Key environment variables (see `.env.example` for full list):

```bash
# Django
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=civicpulse.org,*.civicpulse.org

# Database
DATABASE_URL=postgresql://user:pass@localhost/civicpulse
REDIS_URL=redis://localhost:6379

# Multi-tenancy
PUBLIC_SCHEMA_NAME=public
TENANT_DOMAIN_MODEL=true

# Storage
MEDIA_STORAGE=cloudflare  # or s3, local
CLOUDFLARE_ACCOUNT_ID=xxx
CLOUDFLARE_API_TOKEN=xxx

# Authentication
AUTHENTIK_URL=https://auth.civicpulse.org
AUTHENTIK_TOKEN=xxx
```

## 📚 API Documentation

### RESTful API

The API follows REST principles with:
- Consistent resource naming
- Standard HTTP methods and status codes
- JSON request/response format
- Pagination, filtering, and sorting

### Authentication

```bash
# Obtain token
curl -X POST https://api.civicpulse.org/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "user", "password": "pass"}'

# Use token in requests
curl https://api.civicpulse.org/api/v1/members/ \
  -H "Authorization: Bearer <token>"
```

### Example Endpoints

- `GET /api/v1/members/` - List members
- `POST /api/v1/contacts/` - Create contact
- `GET /api/v1/elections/upcoming/` - Get upcoming elections
- `PUT /api/v1/documents/{id}/` - Update document
- `WS /ws/notifications/` - WebSocket for real-time updates

Full API documentation available at `/api/docs/` when running.

## 🔒 Security & Compliance

### Security Features

- **Encryption**: At rest (database) and in transit (TLS)
- **Authentication**: Multi-factor, SSO, SAML support
- **Authorization**: Fine-grained RBAC with attribute-based rules
- **Comprehensive Audit Trail**: Complete activity tracking with immutable logs (see [Audit Trail Documentation](docs/audit_trail_emily_miller.md))
- **Data Isolation**: Complete tenant separation
- **Input Validation**: Strict sanitization and validation

### Compliance Standards

- **PCI-DSS**: Payment card data handling
- **CCPA/GDPR**: Privacy rights and data protection
- **PDPA/GPIPA**: Georgia-specific privacy laws
- **WCAG 2.1**: Accessibility compliance
- **SOC 2 Type II**: (Roadmap) Security and availability

### Security Reporting

Found a security issue? Please email security@civicpulse.org instead of using the issue tracker.

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/amazing-feature`)
3. Commit changes (`git commit -m 'feat: add amazing feature'`)
4. Push to branch (`git push origin feat/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Install development dependencies
uv sync --dev

# Setup pre-commit hooks
pre-commit install

# Run linting and tests
./scripts/check.sh
```

## 🧪 Testing Strategy

### Test Types

- **Unit Tests**: Individual component testing
- **Integration Tests**: Module interaction testing
- **API Tests**: Endpoint functionality and contracts
- **E2E Tests**: Full user workflow validation
- **Performance Tests**: Load and stress testing
- **Security Tests**: Vulnerability scanning

### Coverage Requirements

- Minimum 80% overall coverage
- 90% coverage for critical paths
- 100% coverage for security functions

## 📖 Documentation

### Available Documentation

- **[User Guide](docs/user-guide.md)**: End-user documentation
- **[Admin Guide](docs/admin-guide.md)**: System administration
- **[Developer Guide](docs/developer-guide.md)**: Development setup and practices
- **[API Reference](docs/api-reference.md)**: Complete API documentation
- **[Deployment Guide](docs/deployment-guide.md)**: Production deployment
- **[Architecture Decisions](docs/consult/ADRs.md)**: Technical decision records

### Generating Documentation

```bash
# Generate API docs
python manage.py spectacular --file schema.yml

# Build Sphinx documentation
cd docs && make html
```

## 📜 License

This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0).

### What This Means

- ✅ Commercial use allowed
- ✅ Modification allowed
- ✅ Distribution allowed
- ✅ Private use allowed
- ⚠️ Network use requires source disclosure
- ⚠️ Modified versions must use AGPL
- ⚠️ Must include copyright and license notices

See the [LICENSE](LICENSE) file for details.

## 💬 Support & Community

### Getting Help

- **Documentation**: Start with our [comprehensive docs](docs/)
- **Issues**: Check [existing issues](https://github.com/your-org/civicpulse-backend/issues) or create new ones
- **Discussions**: Join our [community forum](https://community.civicpulse.org)


## 🗺️ Roadmap

### Phase 1: Foundation (Q1 2025)
- ✅ Core architecture setup
- ✅ Multi-tenancy implementation
- 🔄 Basic member and contact management
- 🔄 Document management system
- 🔄 Authentication and authorization

### Phase 2: MVP (Q2 2025)
- ⬜ Election tracking module
- ⬜ Governance directory
- ⬜ Basic CMS functionality
- ⬜ Task management
- ⬜ Calendar system

### Phase 3: Advanced Features (Q3 2025)
- ⬜ Training modules with video support
- ⬜ Community input and prioritization
- ⬜ GIS and mapping integration
- ⬜ AI-powered assistance
- ⬜ Real-time notifications

### Phase 4: Scale & Polish (Q4 2025)
- ⬜ Performance optimization
- ⬜ Advanced analytics dashboard
- ⬜ Mobile applications
- ⬜ Third-party integrations
- ⬜ Enterprise features

### Phase 5: Ecosystem (2026)
- ⬜ Plugin marketplace
- ⬜ API ecosystem
- ⬜ White-label options
- ⬜ Advanced AI features
- ⬜ Global expansion support

## 🙏 Acknowledgments

- Django and Python communities for excellent frameworks
- PostgreSQL team for a robust database
- All open-source contributors whose work we build upon
- Early adopters and beta testers for valuable feedback

## 📊 Status

- **Build**: ![Build Status](https://img.shields.io/github/workflow/status/your-org/civicpulse-backend/CI)
- **Coverage**: ![Coverage](https://img.shields.io/codecov/c/github/your-org/civicpulse-backend)
- **Version**: ![Version](https://img.shields.io/github/v/release/your-org/civicpulse-backend)
- **Activity**: ![Last Commit](https://img.shields.io/github/last-commit/your-org/civicpulse-backend)

---

Built with ❤️ for civic engagement and community empowerment
