# Duplicate Development Dependencies Fix Report
**Author:** Olivia Jones  
**Date:** 2025-08-18  
**Issue:** PR #35 Copilot feedback on duplicate development dependency definitions

## Problem Summary
The pyproject.toml file contained duplicate development dependency definitions in two different sections:
1. `[project.optional-dependencies]` - Legacy approach
2. `[dependency-groups]` - Modern uv approach

This duplication could lead to:
- Maintenance issues
- Version conflicts
- Confusion about which dependencies are actually used

## Changes Made

### 1. Removed Duplicate Section
- Completely removed the `[project.optional-dependencies]` section (lines 16-27)
- This section contained legacy-style development dependencies

### 2. Consolidated Dependencies
- Kept the modern `[dependency-groups]` section as the single source of truth
- Added missing `bandit[toml]>=1.8.6` dependency that was only in the removed section
- Maintained alphabetical ordering of dependencies for better maintainability

### 3. Final Development Dependencies
The consolidated `[dependency-groups]` dev section now contains:
- `bandit[toml]>=1.8.6` (security linting with TOML support)
- `django-debug-toolbar>=6.0.0` (Django debugging tool)
- `django-extensions>=4.1` (Django utilities)
- `mypy>=1.17.1` (static type checking)
- `pip-audit>=2.9.0` (dependency vulnerability scanning)
- `pre-commit>=4.3.0` (git hooks for code quality)
- `pytest>=8.4.1` (testing framework)
- `pytest-cov>=6.2.1` (test coverage)
- `pytest-django>=4.11.1` (Django-specific pytest features)
- `ruff>=0.12.9` (linting and formatting)

## Version Resolution Strategy
When consolidating dependencies, I kept the higher version requirements from the `[dependency-groups]` section since:
- These were more recent and likely better tested
- The section already contained additional modern tooling (pip-audit)
- uv dependency-groups is the recommended approach for modern Python projects

## Verification
- Ran `uv run ruff check pyproject.toml` - All checks passed
- Ran `uv run ruff format pyproject.toml` - File properly formatted
- No syntax errors or configuration issues detected

## Benefits of This Fix
1. **Single Source of Truth**: All development dependencies are now defined in one place
2. **Modern tooling**: Uses uv's recommended `[dependency-groups]` approach
3. **Maintainability**: Easier to update and manage dependencies
4. **No lost dependencies**: All unique dependencies from both sections are preserved
5. **Version consistency**: Eliminates potential conflicts from duplicate definitions

## Future Considerations
- The team should use `uv add --group dev <package>` to add new development dependencies
- Regular dependency updates should be easier now with consolidated definitions
- Consider using dependency scanning tools like `pip-audit` (now included) for security audits

## Files Modified
- `/home/kwhatcher/projects/civicpulse/civicpulse-backend-issue-10/pyproject.toml`

## Next Steps
- Commit these changes to the repository
- Mark the GitHub PR #35 conversation as resolved
- Ensure CI/CD pipelines use the new dependency group approach