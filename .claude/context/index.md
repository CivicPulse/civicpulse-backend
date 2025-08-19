# CivicPulse Backend Context Index

## Active Contexts

### Issue #2 - Secure User Authentication System
- **File**: `issue-2-context-20250819.md`
- **Status**: Active Implementation
- **Agent**: Grace Davis
- **Last Updated**: 2025-08-19
- **Priority**: P0 Critical

## Context Management

### Quick Context (< 500 tokens)
- **Current Task**: Implementing Django authentication system
- **Branch**: issue/2-secure-user-authentication (to be created)
- **Technology**: Django, uv, pytest, ruff
- **Goal**: Role-based authentication with coordinator/field worker roles

### Full Context (< 2000 tokens)
- **See**: `issue-2-context-20250819.md`
- **Architecture**: Multi-tenant Django CRM/CMS
- **Security**: Password validation, session management, account lockout
- **Testing**: 80% coverage requirement with pytest

### Key Patterns
- **Package Management**: Always use uv (uv add, uv remove)
- **Code Quality**: ruff linting before commits
- **Git Workflow**: Feature branches, conventional commits
- **Django Settings**: Multi-environment structure (base/dev/prod)

## Agent Handoff Checklist
- [ ] Review authentication implementation progress
- [ ] Check test coverage status (must be 80%+)
- [ ] Verify ruff linting passes
- [ ] Update context with new decisions
- [ ] Document blockers/dependencies