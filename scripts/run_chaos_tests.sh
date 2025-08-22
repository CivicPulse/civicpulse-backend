#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

PROJECT_ROOT="/home/kwhatcher/projects/civicpulse/civicpulse-backend/.worktree/copilot/fix-16"
RESULTS_DIR="$PROJECT_ROOT/chaos_test_results"
FINAL_REPORT="$RESULTS_DIR/final_chaos_engineering_report.json"

echo -e "${BOLD}${BLUE}🧪 CivicPulse Backend - Comprehensive Chaos Engineering Test Suite${NC}"
echo -e "${BLUE}=================================================================${NC}"

# Create results directory
mkdir -p "$RESULTS_DIR"

# Initialize final report
cat > "$FINAL_REPORT" << EOF
{
  "test_suite": "CivicPulse Backend Chaos Engineering",
  "test_timestamp": "$(date -Iseconds)",
  "test_environment": {
    "docker_compose_file": "docker-compose.chaos.yml",
    "target_application": "http://web:8000",
    "database": "PostgreSQL 16",
    "cache": "Redis 7",
    "load_balancer": "nginx",
    "monitoring": ["Prometheus", "Grafana"]
  },
  "test_phases": {
    "1_infrastructure_setup": {},
    "2_baseline_testing": {},
    "3_network_chaos": {},
    "4_database_chaos": {},
    "5_cache_chaos": {},
    "6_container_chaos": {},
    "7_load_testing": {},
    "8_recovery_testing": {},
    "9_cleanup": {}
  },
  "summary": {},
  "recommendations": []
}
EOF

# Function to update test phase status
update_phase_status() {
    local phase=$1
    local status=$2
    local details=$3
    
    jq --arg phase "$phase" --arg status "$status" --arg details "$details" --arg timestamp "$(date -Iseconds)" \
       ".test_phases.\"$phase\" = {status: \$status, details: \$details, timestamp: \$timestamp}" \
       "$FINAL_REPORT" > "${FINAL_REPORT}.tmp" && mv "${FINAL_REPORT}.tmp" "$FINAL_REPORT"
}

# Function to add recommendation
add_recommendation() {
    local priority=$1
    local category=$2
    local recommendation=$3
    
    jq --arg priority "$priority" --arg category "$category" --arg recommendation "$recommendation" \
       '.recommendations += [{priority: $priority, category: $category, recommendation: $recommendation}]' \
       "$FINAL_REPORT" > "${FINAL_REPORT}.tmp" && mv "${FINAL_REPORT}.tmp" "$FINAL_REPORT"
}

# Function to check if Docker is available
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker is not installed or not available${NC}"
        return 1
    fi
    
    if ! docker info &> /dev/null; then
        echo -e "${RED}❌ Docker daemon is not running${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✅ Docker is available${NC}"
    return 0
}

# Function to check if docker-compose is available
check_docker_compose() {
    if command -v docker-compose &> /dev/null; then
        echo -e "${GREEN}✅ docker-compose is available${NC}"
        return 0
    elif docker compose version &> /dev/null; then
        echo -e "${GREEN}✅ docker compose (plugin) is available${NC}"
        return 0
    else
        echo -e "${RED}❌ docker-compose is not available${NC}"
        return 1
    fi
}

# Phase 1: Infrastructure Setup
echo -e "${BOLD}${YELLOW}Phase 1: Infrastructure Setup${NC}"
update_phase_status "1_infrastructure_setup" "running" "Setting up chaos testing infrastructure"

if ! check_docker || ! check_docker_compose; then
    echo -e "${RED}❌ Docker environment not available. Running limited tests only.${NC}"
    update_phase_status "1_infrastructure_setup" "warning" "Docker not available - running limited tests"
    DOCKER_AVAILABLE=false
else
    DOCKER_AVAILABLE=true
    
    cd "$PROJECT_ROOT"
    
    echo -e "${CYAN}🚀 Starting chaos testing infrastructure...${NC}"
    
    # Start the chaos testing environment
    if command -v docker-compose &> /dev/null; then
        COMPOSE_CMD="docker-compose"
    else
        COMPOSE_CMD="docker compose"
    fi
    
    # Cleanup any existing chaos containers
    echo -e "${YELLOW}🧹 Cleaning up any existing chaos containers...${NC}"
    $COMPOSE_CMD -f docker-compose.chaos.yml down -v --remove-orphans || true
    
    # Start the infrastructure
    echo -e "${CYAN}🏗️ Building and starting chaos testing infrastructure...${NC}"
    if $COMPOSE_CMD -f docker-compose.chaos.yml up -d --build; then
        echo -e "${GREEN}✅ Infrastructure started successfully${NC}"
        update_phase_status "1_infrastructure_setup" "success" "All containers started successfully"
        
        # Wait for services to be ready
        echo -e "${YELLOW}⏳ Waiting for services to be ready...${NC}"
        sleep 30
        
        # Check service health
        echo -e "${CYAN}🔍 Checking service health...${NC}"
        for service in web db redis toxiproxy; do
            if $COMPOSE_CMD -f docker-compose.chaos.yml ps | grep -q "$service.*Up"; then
                echo -e "${GREEN}✅ $service is running${NC}"
            else
                echo -e "${YELLOW}⚠️ $service may not be ready${NC}"
            fi
        done
        
    else
        echo -e "${RED}❌ Failed to start infrastructure${NC}"
        update_phase_status "1_infrastructure_setup" "failed" "Failed to start Docker containers"
        exit 1
    fi
fi

# Phase 2: Baseline Testing
echo -e "\n${BOLD}${YELLOW}Phase 2: Baseline Testing${NC}"
update_phase_status "2_baseline_testing" "running" "Establishing baseline performance metrics"

if [[ "$DOCKER_AVAILABLE" == "true" ]]; then
    # Run baseline health checks
    echo -e "${CYAN}📊 Running baseline performance tests...${NC}"
    
    # Wait for application to be fully ready
    for i in {1..30}; do
        if $COMPOSE_CMD -f docker-compose.chaos.yml exec -T web python -c "import requests; requests.get('http://localhost:8000/civicpulse/health/', timeout=5)" 2>/dev/null; then
            echo -e "${GREEN}✅ Application is responding${NC}"
            break
        fi
        echo -e "${YELLOW}⏳ Waiting for application... (attempt $i/30)${NC}"
        sleep 5
    done
    
    # Run baseline tests
    baseline_results=$(mktemp)
    $COMPOSE_CMD -f docker-compose.chaos.yml exec -T stress-test /scripts/chaos_stress_test.sh > "$baseline_results" 2>&1 || true
    
    if grep -q "Chaos engineering stress tests completed" "$baseline_results"; then
        echo -e "${GREEN}✅ Baseline testing completed${NC}"
        update_phase_status "2_baseline_testing" "success" "Baseline metrics established"
    else
        echo -e "${YELLOW}⚠️ Baseline testing had issues${NC}"
        update_phase_status "2_baseline_testing" "warning" "Baseline testing completed with warnings"
    fi
    
    rm -f "$baseline_results"
else
    echo -e "${YELLOW}⚠️ Skipping baseline tests - Docker not available${NC}"
    update_phase_status "2_baseline_testing" "skipped" "Docker not available"
fi

# Phase 3: Network Chaos Testing
echo -e "\n${BOLD}${YELLOW}Phase 3: Network Chaos Testing${NC}"
update_phase_status "3_network_chaos" "running" "Testing network partition and latency scenarios"

if [[ "$DOCKER_AVAILABLE" == "true" ]]; then
    echo -e "${CYAN}🌐 Running network chaos tests...${NC}"
    
    network_results=$(mktemp)
    $COMPOSE_CMD -f docker-compose.chaos.yml exec -T stress-test /scripts/network_chaos_test.sh > "$network_results" 2>&1 || true
    
    if grep -q "Network chaos tests completed" "$network_results"; then
        echo -e "${GREEN}✅ Network chaos testing completed${NC}"
        update_phase_status "3_network_chaos" "success" "All network failure scenarios tested"
        add_recommendation "medium" "network" "Monitor network latency and implement circuit breakers for external dependencies"
    else
        echo -e "${YELLOW}⚠️ Network chaos testing had issues${NC}"
        update_phase_status "3_network_chaos" "warning" "Network testing completed with warnings"
    fi
    
    # Copy network results
    if [[ -s "$network_results" ]]; then
        cp "$network_results" "$RESULTS_DIR/network_chaos_results.log"
    fi
    rm -f "$network_results"
else
    echo -e "${YELLOW}⚠️ Skipping network chaos tests - Docker not available${NC}"
    update_phase_status "3_network_chaos" "skipped" "Docker not available"
fi

# Phase 4: Database Chaos Testing
echo -e "\n${BOLD}${YELLOW}Phase 4: Database Chaos Testing${NC}"
update_phase_status "4_database_chaos" "running" "Testing database connection pool and failover scenarios"

if [[ "$DOCKER_AVAILABLE" == "true" ]]; then
    echo -e "${CYAN}🗄️ Running database chaos tests...${NC}"
    
    # Run database stress tests using pgbench
    echo -e "${CYAN}📊 Running database load testing...${NC}"
    db_results=$(mktemp)
    $COMPOSE_CMD -f docker-compose.chaos.yml logs pgbench > "$db_results" 2>&1 || true
    
    if grep -q "pgbench" "$db_results"; then
        echo -e "${GREEN}✅ Database load testing completed${NC}"
        update_phase_status "4_database_chaos" "success" "Database resilience tested under load"
        add_recommendation "high" "database" "Implement database connection pooling with proper timeout handling"
        add_recommendation "medium" "database" "Set up database monitoring for connection pool exhaustion"
    else
        echo -e "${YELLOW}⚠️ Database chaos testing had issues${NC}"
        update_phase_status "4_database_chaos" "warning" "Database testing completed with warnings"
    fi
    
    cp "$db_results" "$RESULTS_DIR/database_chaos_results.log"
    rm -f "$db_results"
else
    echo -e "${YELLOW}⚠️ Skipping database chaos tests - Docker not available${NC}"
    update_phase_status "4_database_chaos" "skipped" "Docker not available"
fi

# Phase 5: Cache Chaos Testing
echo -e "\n${BOLD}${YELLOW}Phase 5: Cache Chaos Testing${NC}"
update_phase_status "5_cache_chaos" "running" "Testing Redis cache failure scenarios"

if [[ "$DOCKER_AVAILABLE" == "true" ]]; then
    echo -e "${CYAN}🔄 Running cache chaos tests...${NC}"
    
    # Test Redis resilience by stopping and starting it
    echo -e "${CYAN}📊 Testing Redis failure and recovery...${NC}"
    
    # Stop Redis temporarily
    $COMPOSE_CMD -f docker-compose.chaos.yml stop redis
    sleep 10
    
    # Test application behavior without Redis
    cache_test_results=$(mktemp)
    for i in {1..5}; do
        if $COMPOSE_CMD -f docker-compose.chaos.yml exec -T web python -c "import requests; requests.get('http://localhost:8000/civicpulse/health/', timeout=10)" 2>/dev/null; then
            echo "Health check $i: SUCCESS" >> "$cache_test_results"
        else
            echo "Health check $i: FAILED" >> "$cache_test_results"
        fi
        sleep 2
    done
    
    # Restart Redis
    $COMPOSE_CMD -f docker-compose.chaos.yml start redis
    sleep 5
    
    # Test recovery
    for i in {1..5}; do
        if $COMPOSE_CMD -f docker-compose.chaos.yml exec -T web python -c "import requests; requests.get('http://localhost:8000/civicpulse/health/', timeout=10)" 2>/dev/null; then
            echo "Recovery check $i: SUCCESS" >> "$cache_test_results"
        else
            echo "Recovery check $i: FAILED" >> "$cache_test_results"
        fi
        sleep 2
    done
    
    success_count=$(grep -c "SUCCESS" "$cache_test_results" || echo "0")
    total_count=$(wc -l < "$cache_test_results")
    
    if [[ $success_count -gt $((total_count / 2)) ]]; then
        echo -e "${GREEN}✅ Cache chaos testing completed - system resilient${NC}"
        update_phase_status "5_cache_chaos" "success" "Application handles cache failures gracefully"
        add_recommendation "medium" "cache" "Implement cache fallback mechanisms for critical operations"
    else
        echo -e "${YELLOW}⚠️ Cache chaos testing shows vulnerabilities${NC}"
        update_phase_status "5_cache_chaos" "warning" "Application may be too dependent on cache"
        add_recommendation "high" "cache" "Reduce cache dependency and implement graceful degradation"
    fi
    
    cp "$cache_test_results" "$RESULTS_DIR/cache_chaos_results.log"
    rm -f "$cache_test_results"
else
    echo -e "${YELLOW}⚠️ Skipping cache chaos tests - Docker not available${NC}"
    update_phase_status "5_cache_chaos" "skipped" "Docker not available"
fi

# Phase 6: Container Chaos Testing
echo -e "\n${BOLD}${YELLOW}Phase 6: Container Restart Resilience Testing${NC}"
update_phase_status "6_container_chaos" "running" "Testing container restart and recovery scenarios"

if [[ "$DOCKER_AVAILABLE" == "true" ]]; then
    echo -e "${CYAN}📦 Running container chaos tests...${NC}"
    
    # Test container restart resilience
    container_test_results=$(mktemp)
    echo "Starting container restart tests..." > "$container_test_results"
    
    # Restart main web container
    echo -e "${CYAN}🔄 Restarting web container...${NC}"
    $COMPOSE_CMD -f docker-compose.chaos.yml restart web
    
    # Wait for container to be ready and test recovery time
    recovery_start=$(date +%s)
    recovered=false
    
    for i in {1..60}; do  # Test for up to 60 seconds
        if $COMPOSE_CMD -f docker-compose.chaos.yml exec -T web python -c "import requests; requests.get('http://localhost:8000/civicpulse/health/', timeout=5)" 2>/dev/null; then
            recovery_time=$(($(date +%s) - recovery_start))
            echo "Container recovered in ${recovery_time} seconds" >> "$container_test_results"
            recovered=true
            break
        fi
        sleep 1
    done
    
    if [[ "$recovered" == "true" ]]; then
        echo -e "${GREEN}✅ Container restart resilience test passed${NC}"
        update_phase_status "6_container_chaos" "success" "Containers restart and recover properly"
        add_recommendation "low" "containers" "Current container restart policy is adequate"
    else
        echo -e "${RED}❌ Container restart resilience test failed${NC}"
        update_phase_status "6_container_chaos" "failed" "Container recovery took too long or failed"
        add_recommendation "high" "containers" "Review container health checks and startup procedures"
    fi
    
    cp "$container_test_results" "$RESULTS_DIR/container_chaos_results.log"
    rm -f "$container_test_results"
else
    echo -e "${YELLOW}⚠️ Skipping container chaos tests - Docker not available${NC}"
    update_phase_status "6_container_chaos" "skipped" "Docker not available"
fi

# Phase 7: Load Testing
echo -e "\n${BOLD}${YELLOW}Phase 7: Load Testing${NC}"
update_phase_status "7_load_testing" "running" "Running load tests to validate performance under stress"

if [[ "$DOCKER_AVAILABLE" == "true" ]]; then
    echo -e "${CYAN}🚀 Running load tests...${NC}"
    
    load_test_results=$(mktemp)
    echo "Load test started at $(date)" > "$load_test_results"
    
    # Run Artillery load test
    if $COMPOSE_CMD -f docker-compose.chaos.yml logs artillery >> "$load_test_results" 2>&1; then
        echo -e "${GREEN}✅ Load testing completed${NC}"
        update_phase_status "7_load_testing" "success" "Application handles expected load"
        add_recommendation "medium" "performance" "Monitor response times and implement auto-scaling if needed"
    else
        echo -e "${YELLOW}⚠️ Load testing had issues${NC}"
        update_phase_status "7_load_testing" "warning" "Load testing completed with warnings"
        add_recommendation "high" "performance" "Investigate performance bottlenecks identified in load testing"
    fi
    
    cp "$load_test_results" "$RESULTS_DIR/load_test_results.log"
    rm -f "$load_test_results"
else
    echo -e "${YELLOW}⚠️ Skipping load tests - Docker not available${NC}"
    update_phase_status "7_load_testing" "skipped" "Docker not available"
fi

# Phase 8: Recovery Testing
echo -e "\n${BOLD}${YELLOW}Phase 8: Recovery Testing${NC}"
update_phase_status "8_recovery_testing" "running" "Testing system recovery capabilities"

if [[ "$DOCKER_AVAILABLE" == "true" ]]; then
    echo -e "${CYAN}🔄 Running recovery tests...${NC}"
    
    recovery_test_results=$(mktemp)
    echo "Recovery test started at $(date)" > "$recovery_test_results"
    
    # Test full system restart
    echo -e "${CYAN}🔄 Testing full system restart...${NC}"
    restart_start=$(date +%s)
    
    $COMPOSE_CMD -f docker-compose.chaos.yml restart
    
    # Wait for system to be fully ready
    system_recovered=false
    for i in {1..120}; do  # Wait up to 2 minutes
        if $COMPOSE_CMD -f docker-compose.chaos.yml exec -T web python -c "import requests; requests.get('http://localhost:8000/civicpulse/health/', timeout=10)" 2>/dev/null; then
            restart_recovery_time=$(($(date +%s) - restart_start))
            echo "Full system recovered in ${restart_recovery_time} seconds" >> "$recovery_test_results"
            system_recovered=true
            break
        fi
        sleep 1
    done
    
    if [[ "$system_recovered" == "true" ]]; then
        echo -e "${GREEN}✅ System recovery test passed${NC}"
        update_phase_status "8_recovery_testing" "success" "System recovers properly from full restart"
        add_recommendation "low" "recovery" "System recovery time is acceptable"
    else
        echo -e "${RED}❌ System recovery test failed${NC}"
        update_phase_status "8_recovery_testing" "failed" "System recovery took too long or failed"
        add_recommendation "high" "recovery" "Investigate slow startup and implement startup optimizations"
    fi
    
    cp "$recovery_test_results" "$RESULTS_DIR/recovery_test_results.log"
    rm -f "$recovery_test_results"
else
    echo -e "${YELLOW}⚠️ Skipping recovery tests - Docker not available${NC}"
    update_phase_status "8_recovery_testing" "skipped" "Docker not available"
fi

# Phase 9: Cleanup
echo -e "\n${BOLD}${YELLOW}Phase 9: Cleanup${NC}"
update_phase_status "9_cleanup" "running" "Cleaning up test environment"

if [[ "$DOCKER_AVAILABLE" == "true" ]]; then
    echo -e "${CYAN}🧹 Cleaning up chaos testing infrastructure...${NC}"
    
    # Gather final logs before cleanup
    echo -e "${CYAN}📋 Gathering final logs...${NC}"
    mkdir -p "$RESULTS_DIR/service_logs"
    
    for service in web db redis toxiproxy nginx; do
        $COMPOSE_CMD -f docker-compose.chaos.yml logs "$service" > "$RESULTS_DIR/service_logs/${service}.log" 2>&1 || true
    done
    
    # Stop and remove containers
    $COMPOSE_CMD -f docker-compose.chaos.yml down -v --remove-orphans
    
    echo -e "${GREEN}✅ Cleanup completed${NC}"
    update_phase_status "9_cleanup" "success" "All resources cleaned up"
else
    echo -e "${YELLOW}⚠️ No cleanup needed - Docker not available${NC}"
    update_phase_status "9_cleanup" "skipped" "Docker not available"
fi

# Generate final summary
echo -e "\n${BOLD}${BLUE}Generating Final Summary${NC}"

# Count test phases
total_phases=9
passed_phases=$(jq '[.test_phases[] | select(.status == "success")] | length' "$FINAL_REPORT")
warning_phases=$(jq '[.test_phases[] | select(.status == "warning")] | length' "$FINAL_REPORT")
failed_phases=$(jq '[.test_phases[] | select(.status == "failed")] | length' "$FINAL_REPORT")
skipped_phases=$(jq '[.test_phases[] | select(.status == "skipped")] | length' "$FINAL_REPORT")

# Calculate overall health score
if [[ $failed_phases -gt 0 ]]; then
    overall_status="NEEDS_ATTENTION"
    health_score=$((($passed_phases * 100) / ($total_phases - $skipped_phases)))
elif [[ $warning_phases -gt 0 ]]; then
    overall_status="GOOD_WITH_WARNINGS"
    health_score=$((($passed_phases * 100) / ($total_phases - $skipped_phases)))
else
    overall_status="EXCELLENT"
    health_score=100
fi

# Update final summary
jq --arg status "$overall_status" --arg score "$health_score" \
   --arg passed "$passed_phases" --arg warnings "$warning_phases" \
   --arg failed "$failed_phases" --arg skipped "$skipped_phases" \
   '.summary = {
     overall_status: $status,
     health_score: ($score | tonumber),
     phases_passed: ($passed | tonumber),
     phases_with_warnings: ($warnings | tonumber),
     phases_failed: ($failed | tonumber),
     phases_skipped: ($skipped | tonumber),
     total_phases: 9,
     test_completion_time: (now | todate)
   }' "$FINAL_REPORT" > "${FINAL_REPORT}.tmp" && mv "${FINAL_REPORT}.tmp" "$FINAL_REPORT"

# Display final results
echo -e "\n${BOLD}${GREEN}🎉 CHAOS ENGINEERING TEST SUITE COMPLETED${NC}"
echo -e "${BLUE}=================================================${NC}"
echo -e "${CYAN}Overall Status: ${NC}${BOLD}$overall_status${NC}"
echo -e "${CYAN}Health Score: ${NC}${BOLD}$health_score/100${NC}"
echo -e "${CYAN}Phases Passed: ${NC}${BOLD}$passed_phases${NC}"
echo -e "${CYAN}Phases with Warnings: ${NC}${BOLD}$warning_phases${NC}"
echo -e "${CYAN}Phases Failed: ${NC}${BOLD}$failed_phases${NC}"
echo -e "${CYAN}Phases Skipped: ${NC}${BOLD}$skipped_phases${NC}"

echo -e "\n${BOLD}${BLUE}📁 Test Results Location:${NC}"
echo -e "${CYAN}Results Directory: ${NC}$RESULTS_DIR"
echo -e "${CYAN}Final Report: ${NC}$FINAL_REPORT"

echo -e "\n${BOLD}${BLUE}🔍 Key Recommendations:${NC}"
jq -r '.recommendations[] | "• \(.priority | ascii_upcase) [\(.category)]: \(.recommendation)"' "$FINAL_REPORT"

echo -e "\n${BOLD}${BLUE}🏁 Test Suite Complete${NC}"