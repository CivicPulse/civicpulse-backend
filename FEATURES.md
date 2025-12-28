# CivicPulse

## The All-in-One Platform for Civic Engagement & Community Organizing

---

### Empowering Nonprofits, Civic Organizations & Political Groups

CivicPulse is a powerful, open-source platform that brings together everything you need to mobilize communities, track elections, manage campaigns, and drive meaningful civic change—all in one place.

---

## Why CivicPulse?

| Challenge | CivicPulse Solution |
|-----------|---------------------|
| Scattered tools and spreadsheets | **Unified platform** with CRM, campaigns, and voter data in one place |
| Expensive per-seat SaaS pricing | **Open-source** with self-hosting option—no per-user fees |
| Data silos between departments | **Multi-tenant architecture** with seamless data sharing |
| Complex compliance requirements | **Built-in audit trails** for GDPR, CCPA, and organizational transparency |
| Limited geographic targeting | **GIS-powered district mapping** for precise outreach |
| Difficulty tracking constituents | **Smart duplicate detection** keeps your database clean |

---

## Core Features

### 👥 Contact & Constituent Management

Build lasting relationships with the people who matter most to your mission.

- **Comprehensive Profiles**: Track contact information, communication history, relationships, and engagement scores
- **Smart Duplicate Detection**: AI-powered matching prevents duplicate entries and keeps your database clean
- **Advanced Search**: Find contacts instantly with powerful filtering by location, tags, engagement level, and custom fields
- **Interaction Logging**: Record every touchpoint—calls, emails, meetings, door knocks—with outcomes and follow-ups
- **Import & Export**: Bulk import from CSV/Excel with intelligent field mapping; export anytime

### 🎯 Campaign Management

Plan, execute, and measure campaigns that drive real impact.

- **Campaign Builder**: Create targeted campaigns with defined goals, timelines, and success metrics
- **Audience Targeting**: Build segments based on geography, demographics, engagement history, or custom criteria
- **District-Based Targeting**: Reach voters in specific electoral districts, precincts, or custom boundaries
- **Progress Tracking**: Real-time dashboards show campaign performance and team activity
- **Multi-Channel Outreach**: Coordinate phone banks, canvassing, email, and text campaigns from one hub

### 🗳️ Voter & Election Tracking

Stay informed and mobilize voters effectively.

- **Voter Database Integration**: Import and manage voter files with registration status and vote history
- **Election Calendar**: Track upcoming local, state, and federal elections with key dates and deadlines
- **Candidate Tracking**: Monitor candidates, their positions, endorsements, and campaign activities
- **Turnout Analytics**: Analyze voter participation patterns to optimize your GOTV efforts
- **Registration Drives**: Track voter registration activities and measure success

### 🗺️ GIS & District Mapping

Precision targeting with powerful geographic tools.

- **Interactive Maps**: Visualize your data on dynamic, layered maps
- **District Boundaries**: Import and display electoral districts, precincts, wards, and custom regions
- **Automated Assignment**: Automatically assign contacts to districts based on their addresses
- **Officeholder Directory**: Know who represents each district at every level of government
- **Shapefile Support**: Import standard GIS formats including Shapefiles, GeoJSON, and KML

### 🔐 Security & Compliance

Enterprise-grade security that organizations of all sizes can trust.

- **Comprehensive Audit Trail**: Every action is logged—who did what, when, and what changed
- **Role-Based Access Control**: Fine-grained permissions ensure users see only what they need
- **Multi-Factor Authentication**: Protect accounts with 2FA and SSO integration
- **Data Encryption**: All data encrypted at rest and in transit
- **GDPR & CCPA Ready**: Built-in tools for data subject requests and privacy compliance
- **Account Protection**: Automatic lockout after failed login attempts with admin alerts

### 📊 Reporting & Analytics

Turn data into actionable insights.

- **Custom Dashboards**: Build personalized views with the metrics that matter to you
- **Activity Reports**: Track team productivity, outreach volume, and response rates
- **Engagement Scoring**: Identify your most engaged supporters and at-risk contacts
- **Export Anywhere**: Generate reports in CSV, Excel, or PDF formats
- **Scheduled Reports**: Automated report delivery to stakeholders

---

## Built for Your Organization

### Nonprofits & Community Organizations

- Manage donors, volunteers, and program participants in one system
- Track grant deliverables and report on community impact
- Coordinate events, training, and community programs
- Build lasting relationships with constituents and partners

### Political Campaigns & PACs

- Target voters with precision using GIS-powered district mapping
- Manage canvassers, phone bankers, and volunteers efficiently
- Track voter contacts, pledges, and GOTV commitments
- Maintain FEC-compliant records with comprehensive audit trails

### Civic Engagement Groups

- Monitor elected officials and track their voting records
- Organize advocacy campaigns around issues that matter
- Mobilize supporters for public meetings and hearings
- Build coalitions across organizations with shared data

### Labor Unions & Member Organizations

- Track member status, dues, and engagement
- Coordinate organizing campaigns and contract negotiations
- Communicate with members across multiple worksites
- Monitor legislative issues affecting your members

---

## Technical Excellence

### Modern Architecture

- **Django 5.2** with Python 3.13 for robust, maintainable code
- **PostgreSQL with PostGIS** for powerful geographic queries
- **Redis** for high-performance caching and real-time features
- **REST API** for seamless integration with other tools

### Deployment Flexibility

- **One-Command Install**: Bootstrap script gets you running in minutes
- **Docker Ready**: Production-grade containerized deployment
- **Self-Hosted**: Run on your own infrastructure with full control
- **Cloud Native**: Deploy to AWS, GCP, Azure, or any Kubernetes cluster

### Developer Friendly

- **Open Source**: AGPL-licensed with active community development
- **API-First**: Every feature accessible via documented REST APIs
- **Extensible**: Plugin architecture for custom functionality
- **Well-Tested**: Comprehensive test suite with 80%+ code coverage

---

## Getting Started

### Quick Install

```bash
# One-command bootstrap (assumes Redis running on localhost)
curl -sSL https://raw.githubusercontent.com/CivicPulse/civicpulse-backend/main/scripts/bootstrap.sh | bash
```

The interactive installer will guide you through:
- Database configuration (PostgreSQL connection)
- Redis setup verification
- Admin account creation
- Environment selection (development/production)

### What You'll Need

- **Python 3.13+** for running the application
- **PostgreSQL 14+** with PostGIS extension for data storage
- **Redis 7+** for caching and background tasks
- **Git** for downloading the source code

---

## Why Open Source?

CivicPulse is built on the belief that powerful civic technology should be accessible to everyone—not just organizations with big budgets.

**Transparency**: See exactly how your data is handled. No black boxes.

**Control**: Self-host on your infrastructure. Your data stays yours.

**Community**: Benefit from contributions by organizations worldwide.

**Cost-Effective**: No per-seat licensing. Scale without limits.

**Customizable**: Modify the platform to fit your exact needs.

---

## Feature Comparison

| Feature | CivicPulse | Traditional CRMs | Voter File Tools |
|---------|------------|------------------|------------------|
| Contact Management | ✅ | ✅ | ⚠️ Limited |
| Campaign Tracking | ✅ | ⚠️ Basic | ✅ |
| GIS/District Mapping | ✅ | ❌ | ⚠️ Basic |
| Voter File Integration | ✅ | ❌ | ✅ |
| Audit Trail | ✅ | ⚠️ Basic | ❌ |
| Self-Hosting Option | ✅ | ❌ | ❌ |
| Open Source | ✅ | ❌ | ❌ |
| API Access | ✅ | ⚠️ Paid tier | ⚠️ Limited |
| Per-Seat Pricing | ❌ Free | ✅ | ✅ |

---

## Roadmap Highlights

### Available Now
- ✅ Contact & constituent management with duplicate detection
- ✅ Campaign management with district targeting
- ✅ Voter search with advanced filtering
- ✅ GIS integration with district import
- ✅ Comprehensive audit trail system
- ✅ Secure authentication with account protection
- ✅ REST API for integrations
- ✅ Docker deployment support

### Coming Soon
- 📅 Event management and RSVPs
- 📱 Mobile-optimized canvassing tools
- 📧 Email and SMS campaign integration
- 📊 Advanced analytics dashboards
- 🤖 AI-powered contact recommendations
- 🔗 Third-party integrations (ActBlue, NGP VAN, etc.)

---

## Join the Movement

CivicPulse is more than software—it's a community of organizers, developers, and civic leaders working together to strengthen democracy.

### Get Involved

- **Star us on GitHub**: Show your support and stay updated
- **Report Issues**: Help us improve by reporting bugs and requesting features
- **Contribute Code**: Join our community of developers
- **Share Your Story**: Tell us how CivicPulse is helping your organization

### Resources

- 📖 [Documentation](docs/)
- 💻 [GitHub Repository](https://github.com/CivicPulse/civicpulse-backend)
- 🐛 [Issue Tracker](https://github.com/CivicPulse/civicpulse-backend/issues)
- 💬 [Community Forum](https://community.civicpulse.org)

---

## License

CivicPulse is released under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.

This means you can:
- ✅ Use it for any purpose, including commercial
- ✅ Modify it to suit your needs
- ✅ Distribute it to others
- ✅ Self-host without restrictions

With the requirement that:
- 📋 You share source code of modifications
- 📋 You include license and copyright notices
- 📋 Network users can access the source code

---

<p align="center">
  <strong>Built with purpose. Powered by community. Ready for impact.</strong>
</p>

<p align="center">
  <a href="https://github.com/CivicPulse/civicpulse-backend">Get Started Today</a>
</p>
