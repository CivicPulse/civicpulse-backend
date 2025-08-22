#!/bin/bash
# Security Validation Script for CivicPulse CI/CD Pipeline
# Tests branch protection, security scanning, and secret management

# Don't exit on error - we want to run all tests
set +e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test results tracking
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

# Function to print colored output
print_status() {
    local status=$1
    local message=$2
    case $status in
        "PASS")
            echo -e "${GREEN}✅ PASS${NC}: $message"
            ((TESTS_PASSED++))
            ;;
        "FAIL")
            echo -e "${RED}❌ FAIL${NC}: $message"
            ((TESTS_FAILED++))
            ;;
        "SKIP")
            echo -e "${YELLOW}⚠️  SKIP${NC}: $message"
            ((TESTS_SKIPPED++))
            ;;
        "INFO")
            echo -e "${BLUE}ℹ️  INFO${NC}: $message"
            ;;
    esac
}

# Function to check command availability
check_command() {
    if command -v $1 &> /dev/null; then
        return 0
    else
        return 1
    fi
}

echo "================================"
echo "Security Validation Report"
echo "Repository: CivicPulse/civicpulse-backend"
echo "Date: $(date)"
echo "================================"
echo ""

# 1. Environment and Tool Verification
echo "## 1. Environment and Tool Verification"
echo "----------------------------------------"

if check_command gh; then
    print_status "PASS" "GitHub CLI (gh) is installed"
else
    print_status "FAIL" "GitHub CLI (gh) is not installed"
fi

if uv run python -c "import bandit" 2>/dev/null; then
    print_status "PASS" "Bandit security scanner is available"
else
    print_status "FAIL" "Bandit security scanner is not available"
fi

if uv run python -c "import pip_audit" 2>/dev/null; then
    print_status "PASS" "pip-audit vulnerability scanner is available"
else
    print_status "FAIL" "pip-audit vulnerability scanner is not available"
fi

echo ""

# 2. Branch Protection Rules Testing
echo "## 2. Branch Protection Rules Testing"
echo "-------------------------------------"

# Check if main branch exists
if git show-ref --verify --quiet refs/remotes/origin/main; then
    print_status "PASS" "Main branch exists"
    
    # Check if main branch is protected
    PROTECTION_STATUS=$(gh api repos/CivicPulse/civicpulse-backend/branches/main --jq '.protected' 2>/dev/null || echo "false")
    if [ "$PROTECTION_STATUS" = "true" ]; then
        print_status "PASS" "Main branch is marked as protected"
    else
        print_status "FAIL" "Main branch is NOT protected"
    fi
else
    print_status "FAIL" "Main branch does not exist"
fi

# Test direct push prevention (simulated)
print_status "INFO" "Direct push to main should be blocked (requires actual test)"

echo ""

# 3. Security Scanning Integration
echo "## 3. Security Scanning Integration"
echo "-----------------------------------"

# Run Bandit security scan
echo "Running Bandit security scan..."
if uv run bandit -r civicpulse/ -ll -f json -o /tmp/bandit-validation.json 2>/dev/null; then
    VULNERABILITIES=$(cat /tmp/bandit-validation.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('results', [])))")
    if [ "$VULNERABILITIES" -eq 0 ]; then
        print_status "PASS" "No security vulnerabilities found by Bandit"
    else
        print_status "FAIL" "Bandit found $VULNERABILITIES security issues"
    fi
else
    print_status "FAIL" "Bandit scan failed to execute"
fi

# Run pip-audit for dependency vulnerabilities
echo "Running pip-audit dependency scan..."
if uv run pip-audit --desc 2>/dev/null | grep -q "No known vulnerabilities"; then
    print_status "PASS" "No vulnerable dependencies found"
else
    VULN_COUNT=$(uv run pip-audit 2>/dev/null | grep -c "^[[:space:]]*CVE" || echo "0")
    if [ "$VULN_COUNT" -gt 0 ]; then
        print_status "FAIL" "Found $VULN_COUNT vulnerable dependencies"
    else
        print_status "PASS" "No vulnerable dependencies found"
    fi
fi

echo ""

# 4. Secret Management and Detection
echo "## 4. Secret Management and Detection"
echo "------------------------------------"

# Check for .env file (should not exist in repo)
if [ -f ".env" ]; then
    if git ls-files --error-unmatch .env 2>/dev/null; then
        print_status "FAIL" ".env file is tracked in git (CRITICAL)"
    else
        print_status "PASS" ".env file exists but is not tracked in git"
    fi
else
    print_status "PASS" "No .env file in repository"
fi

# Check .gitignore for proper secret exclusion
if grep -q "^\.env$" .gitignore; then
    print_status "PASS" ".env is in .gitignore"
else
    print_status "FAIL" ".env is not properly excluded in .gitignore"
fi

# Check for hardcoded secrets in code
echo "Scanning for potential hardcoded secrets..."
SECRET_PATTERNS=(
    "SECRET_KEY\s*=\s*['\"][^'\"]{20,}"
    "API_KEY\s*=\s*['\"][^'\"]{20,}"
    "PASSWORD\s*=\s*['\"][^'\"]{8,}"
    "TOKEN\s*=\s*['\"][^'\"]{20,}"
)

SECRETS_FOUND=0
for pattern in "${SECRET_PATTERNS[@]}"; do
    if grep -r -E "$pattern" civicpulse/ --exclude-dir=__pycache__ --exclude-dir=migrations 2>/dev/null | grep -v "test\|example\|dummy\|placeholder" > /dev/null; then
        ((SECRETS_FOUND++))
    fi
done

if [ $SECRETS_FOUND -eq 0 ]; then
    print_status "PASS" "No hardcoded secrets detected in code"
else
    print_status "FAIL" "Found $SECRETS_FOUND potential hardcoded secrets"
fi

echo ""

# 5. CI/CD Security Checks
echo "## 5. CI/CD Security Checks"
echo "---------------------------"

# Check if CI workflows exist
if [ -f ".github/workflows/ci.yml" ]; then
    print_status "PASS" "CI workflow exists"
    
    # Check for security job in CI
    if grep -q "security:" .github/workflows/ci.yml; then
        print_status "PASS" "Security job configured in CI workflow"
    else
        print_status "FAIL" "No security job in CI workflow"
    fi
    
    # Check for required status checks
    if grep -q "needs: \[.*security.*\]" .github/workflows/ci.yml; then
        print_status "PASS" "Security checks are required for CI completion"
    else
        print_status "FAIL" "Security checks are not enforced in CI"
    fi
else
    print_status "FAIL" "CI workflow not found"
fi

# Check PR validation workflow
if [ -f ".github/workflows/pr-validation.yml" ]; then
    print_status "PASS" "PR validation workflow exists"
    
    # Check for conventional commits validation
    if grep -q "conventional commits" .github/workflows/pr-validation.yml; then
        print_status "PASS" "Conventional commits validation configured"
    else
        print_status "FAIL" "No conventional commits validation"
    fi
else
    print_status "FAIL" "PR validation workflow not found"
fi

echo ""

# 6. Django Security Configuration
echo "## 6. Django Security Configuration"
echo "----------------------------------"

# Check for security middleware
if grep -q "SecurityMiddleware" cpback/settings/base.py; then
    print_status "PASS" "Django SecurityMiddleware is configured"
else
    print_status "FAIL" "Django SecurityMiddleware not found"
fi

# Check for HTTPS enforcement settings
if grep -q "SECURE_SSL_REDIRECT" cpback/settings/production.py 2>/dev/null; then
    print_status "PASS" "HTTPS redirect configured for production"
else
    print_status "SKIP" "HTTPS redirect not explicitly configured"
fi

# Check for security headers
SECURITY_HEADERS=(
    "SECURE_BROWSER_XSS_FILTER"
    "SECURE_CONTENT_TYPE_NOSNIFF"
    "X_FRAME_OPTIONS"
    "SECURE_REFERRER_POLICY"
)

for header in "${SECURITY_HEADERS[@]}"; do
    if grep -q "$header" cpback/settings/base.py; then
        print_status "PASS" "Security header configured: $header"
    else
        print_status "FAIL" "Security header missing: $header"
    fi
done

# Check for CSRF protection
if grep -q "CSRF_COOKIE_SECURE" cpback/settings/base.py; then
    print_status "PASS" "CSRF protection configured"
else
    print_status "FAIL" "CSRF protection not properly configured"
fi

echo ""

# 7. Authentication and Authorization
echo "## 7. Authentication and Authorization"
echo "-------------------------------------"

# Check for password validators
if grep -q "AUTH_PASSWORD_VALIDATORS" cpback/settings/base.py; then
    print_status "PASS" "Password validators configured"
    
    # Check for custom validators
    if grep -q "PasswordHistoryValidator" cpback/settings/base.py; then
        print_status "PASS" "Password history validation enabled"
    else
        print_status "FAIL" "No password history validation"
    fi
    
    if grep -q "PasswordStrengthValidator" cpback/settings/base.py; then
        print_status "PASS" "Password strength validation enabled"
    else
        print_status "FAIL" "No password strength validation"
    fi
else
    print_status "FAIL" "No password validators configured"
fi

# Check for session security
if grep -q "SESSION_COOKIE_SECURE" cpback/settings/base.py; then
    print_status "PASS" "Session cookie security configured"
else
    print_status "FAIL" "Session cookie security not configured"
fi

# Check for rate limiting
if grep -q "MAX_LOGIN_ATTEMPTS" cpback/settings/base.py; then
    print_status "PASS" "Login rate limiting configured"
else
    print_status "FAIL" "No login rate limiting configured"
fi

echo ""

# 8. Audit Trail and Logging
echo "## 8. Audit Trail and Logging"
echo "-----------------------------"

# Check for audit trail models
if [ -f "civicpulse/audit.py" ]; then
    print_status "PASS" "Audit trail system implemented"
    
    # Check for audit middleware
    if grep -q "AuditMiddleware" cpback/settings/base.py; then
        print_status "PASS" "Audit middleware configured"
    else
        print_status "FAIL" "Audit middleware not configured"
    fi
else
    print_status "FAIL" "No audit trail system found"
fi

# Check for security monitoring
if [ -f "civicpulse/utils/security_monitor.py" ]; then
    print_status "PASS" "Security monitoring utilities present"
else
    print_status "FAIL" "No security monitoring utilities found"
fi

echo ""

# 9. Container Security
echo "## 9. Container Security"
echo "-----------------------"

# Check Dockerfile for security best practices
if [ -f "Dockerfile" ]; then
    print_status "PASS" "Dockerfile exists"
    
    # Check for non-root user
    if grep -q "USER" Dockerfile; then
        print_status "PASS" "Container runs as non-root user"
    else
        print_status "FAIL" "Container may run as root user"
    fi
    
    # Check for minimal base image
    if grep -q "alpine\|slim" Dockerfile; then
        print_status "PASS" "Using minimal base image"
    else
        print_status "SKIP" "Not using minimal base image (may be intentional)"
    fi
else
    print_status "SKIP" "No Dockerfile found"
fi

echo ""

# 10. Summary and Recommendations
echo "## 10. Summary"
echo "============="
echo ""
echo "Tests Passed: $TESTS_PASSED"
echo "Tests Failed: $TESTS_FAILED"
echo "Tests Skipped: $TESTS_SKIPPED"
echo ""

# Calculate security score
TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))
if [ $TOTAL_TESTS -gt 0 ]; then
    SECURITY_SCORE=$((TESTS_PASSED * 100 / TOTAL_TESTS))
    echo "Security Score: ${SECURITY_SCORE}%"
    echo ""
    
    if [ $SECURITY_SCORE -ge 90 ]; then
        echo -e "${GREEN}✅ EXCELLENT${NC}: Security configuration is robust"
    elif [ $SECURITY_SCORE -ge 70 ]; then
        echo -e "${YELLOW}⚠️  GOOD${NC}: Security configuration is acceptable with room for improvement"
    elif [ $SECURITY_SCORE -ge 50 ]; then
        echo -e "${YELLOW}⚠️  FAIR${NC}: Security configuration needs attention"
    else
        echo -e "${RED}❌ CRITICAL${NC}: Security configuration requires immediate attention"
    fi
fi

echo ""
echo "## Recommendations"
echo "-----------------"

if [ $TESTS_FAILED -gt 0 ]; then
    echo "1. CRITICAL: Configure branch protection rules for the main branch"
    echo "   - Enable via GitHub Settings > Branches"
    echo "   - Require PR reviews and status checks"
    echo ""
    echo "2. Configure the following required status checks:"
    echo "   - Lint & Format Check"
    echo "   - Type Check"
    echo "   - Test (with coverage requirements)"
    echo "   - Security Scan"
    echo "   - CI Summary"
    echo ""
    echo "3. Enable additional security features:"
    echo "   - Dependabot security updates"
    echo "   - Secret scanning"
    echo "   - Code scanning with CodeQL"
    echo ""
    echo "4. Implement secret rotation procedures:"
    echo "   - Regular rotation schedule for API keys"
    echo "   - Use GitHub Secrets for sensitive data"
    echo "   - Implement secret scanning pre-commit hooks"
fi

echo ""
echo "Report generated at: $(date)"
echo "================================"

# Exit with appropriate code
if [ $TESTS_FAILED -gt 0 ]; then
    exit 1
else
    exit 0
fi