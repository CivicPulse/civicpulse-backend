#!/bin/bash
# Test Branch Protection Rules
# This script simulates various scenarios to test branch protection

echo "================================"
echo "Branch Protection Test Scenarios"
echo "================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Test 1: Check current branch protection status
echo "Test 1: Verify Branch Protection Status"
echo "---------------------------------------"
MAIN_PROTECTED=$(gh api repos/CivicPulse/civicpulse-backend/branches/main --jq '.protected' 2>/dev/null || echo "false")
if [ "$MAIN_PROTECTED" = "true" ]; then
    echo -e "${GREEN}✅ Main branch is protected${NC}"
else
    echo -e "${RED}❌ Main branch is NOT protected${NC}"
fi

# Get more details about protection (if accessible)
echo ""
echo "Attempting to get protection details..."
gh api repos/CivicPulse/civicpulse-backend/branches/main/protection 2>&1 | head -20 || echo "Protection details not accessible (may require admin permissions)"

echo ""
echo "Test 2: Simulate Direct Push Attempt"
echo "------------------------------------"
echo -e "${BLUE}Scenario:${NC} Developer attempts to push directly to main"
echo "Expected: Push should be rejected"
echo "Command that would be run: git push origin main"
echo -e "${YELLOW}⚠️  Note:${NC} Not executing actual push to avoid repository changes"

echo ""
echo "Test 3: PR Without Required Checks"
echo "----------------------------------"
echo -e "${BLUE}Scenario:${NC} PR created without passing CI checks"
echo "Expected: Merge button should be disabled until checks pass"
echo "Required checks should include:"
echo "  - Lint & Format Check"
echo "  - Type Check"
echo "  - Test"
echo "  - Security Scan"
echo "  - CI Summary"

echo ""
echo "Test 4: Check for Security Workflow Integration"
echo "-----------------------------------------------"
# Check if security scans would block on findings
if grep -q "bandit.*-ll" .github/workflows/ci.yml 2>/dev/null; then
    echo -e "${GREEN}✅ Bandit configured to fail on medium/high issues${NC}"
else
    echo -e "${RED}❌ Bandit not properly configured to block on findings${NC}"
fi

if grep -q "pip-audit" .github/workflows/ci.yml 2>/dev/null; then
    echo -e "${GREEN}✅ pip-audit vulnerability scanning configured${NC}"
else
    echo -e "${RED}❌ pip-audit not configured in CI${NC}"
fi

echo ""
echo "Test 5: Administrator Override Capabilities"
echo "------------------------------------------"
echo -e "${BLUE}Scenario:${NC} Emergency hotfix needs admin override"
ENFORCE_ADMINS=$(gh api repos/CivicPulse/civicpulse-backend/branches/main --jq '.protection.enforce_admins.enabled' 2>/dev/null || echo "unknown")
if [ "$ENFORCE_ADMINS" = "false" ]; then
    echo -e "${GREEN}✅ Admins can bypass protection in emergencies${NC}"
elif [ "$ENFORCE_ADMINS" = "true" ]; then
    echo -e "${YELLOW}⚠️  Admins cannot bypass (more secure but less flexible)${NC}"
else
    echo -e "${BLUE}ℹ️  Admin bypass status: unknown (requires admin access to check)${NC}"
fi

echo ""
echo "Test 6: Review Requirements"
echo "---------------------------"
REQUIRED_REVIEWS=$(gh api repos/CivicPulse/civicpulse-backend/branches/main --jq '.protection.required_pull_request_reviews.required_approving_review_count' 2>/dev/null || echo "0")
if [ "$REQUIRED_REVIEWS" != "0" ] && [ "$REQUIRED_REVIEWS" != "null" ]; then
    echo -e "${GREEN}✅ Requires $REQUIRED_REVIEWS review(s) before merge${NC}"
else
    echo -e "${RED}❌ No review requirements configured${NC}"
fi

echo ""
echo "Test 7: Validate Settings File"
echo "------------------------------"
if [ -f ".github/settings.yml" ]; then
    echo -e "${GREEN}✅ GitHub settings.yml file exists${NC}"
    
    # Check if it matches expected configuration
    if grep -q "required_approving_review_count: 1" .github/settings.yml; then
        echo -e "${GREEN}✅ Settings file requires 1 review${NC}"
    fi
    
    if grep -q "dismiss_stale_reviews: true" .github/settings.yml; then
        echo -e "${GREEN}✅ Stale reviews are dismissed on new commits${NC}"
    fi
    
    if grep -q "require_conversation_resolution: true" .github/settings.yml; then
        echo -e "${GREEN}✅ Requires conversation resolution${NC}"
    fi
else
    echo -e "${RED}❌ No settings.yml file found${NC}"
fi

echo ""
echo "================================"
echo "Test Summary"
echo "================================"
echo ""
echo "Branch protection effectiveness depends on:"
echo "1. GitHub repository settings being properly configured"
echo "2. Required status checks being enforced"
echo "3. Review requirements being set"
echo "4. CI/CD pipeline integration"
echo ""
echo -e "${YELLOW}Note:${NC} Full validation requires attempting actual operations"
echo "which have been simulated here to avoid repository changes."
echo ""
echo "To fully test:"
echo "1. Create a test PR with failing checks - should not be mergeable"
echo "2. Create a test PR with passing checks - should be mergeable"
echo "3. Attempt direct push to main - should be rejected"
echo "4. Test admin override if needed - should work per policy"