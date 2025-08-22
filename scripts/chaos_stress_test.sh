#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

APP_URL="http://web:8000"
HEALTH_ENDPOINT="$APP_URL/civicpulse/health/"
RESULTS_FILE="/tmp/chaos_test_results.json"

echo -e "${BLUE}🧪 Starting Chaos Engineering Stress Tests${NC}"

# Function to check if service is healthy
check_health() {
    local endpoint=$1
    local timeout=${2:-5}
    
    if curl -sf --max-time $timeout "$endpoint" >/dev/null 2>&1; then
        echo "true"
    else
        echo "false"
    fi
}

# Function to measure response time
measure_response_time() {
    local endpoint=$1
    local timeout=${2:-10}
    
    local start_time=$(date +%s.%N)
    if curl -sf --max-time $timeout "$endpoint" >/dev/null 2>&1; then
        local end_time=$(date +%s.%N)
        local response_time=$(echo "$end_time - $start_time" | bc -l 2>/dev/null || echo "0")
        echo "$response_time"
    else
        echo "-1"
    fi
}

# Function to run concurrent requests
run_concurrent_test() {
    local concurrency=$1
    local requests=$2
    local endpoint=$3
    
    echo -e "${YELLOW}🔄 Running concurrent test: $concurrency concurrent, $requests total requests${NC}"
    
    local success_count=0
    local total_time=0
    local pids=()
    
    # Create temporary files for results
    local temp_dir=$(mktemp -d)
    
    for ((i=1; i<=concurrency; i++)); do
        {
            local requests_per_worker=$((requests / concurrency))
            local worker_success=0
            local worker_time=0
            
            for ((j=1; j<=requests_per_worker; j++)); do
                local response_time=$(measure_response_time "$endpoint" 10)
                if [[ "$response_time" != "-1" ]]; then
                    worker_success=$((worker_success + 1))
                    worker_time=$(echo "$worker_time + $response_time" | bc -l 2>/dev/null || echo "$worker_time")
                fi
                sleep 0.1  # Small delay between requests
            done
            
            echo "$worker_success $worker_time" > "$temp_dir/worker_$i"
        } &
        pids+=($!)
    done
    
    # Wait for all workers to complete
    for pid in "${pids[@]}"; do
        wait "$pid"
    done
    
    # Aggregate results
    for ((i=1; i<=concurrency; i++)); do
        if [[ -f "$temp_dir/worker_$i" ]]; then
            read worker_success worker_time < "$temp_dir/worker_$i"
            success_count=$((success_count + worker_success))
            total_time=$(echo "$total_time + $worker_time" | bc -l 2>/dev/null || echo "$total_time")
        fi
    done
    
    local success_rate=$(echo "scale=2; $success_count * 100 / $requests" | bc -l 2>/dev/null || echo "0")
    local avg_response_time=$(echo "scale=3; $total_time / $success_count" | bc -l 2>/dev/null || echo "0")
    
    echo -e "${GREEN}✅ Concurrent test results: $success_rate% success rate, ${avg_response_time}s avg response time${NC}"
    
    # Cleanup
    rm -rf "$temp_dir"
    
    # Return results via global variables (bash limitation workaround)
    LAST_SUCCESS_RATE=$success_rate
    LAST_AVG_RESPONSE_TIME=$avg_response_time
}

# Initialize results file
cat > "$RESULTS_FILE" << EOF
{
  "test_timestamp": "$(date -Iseconds)",
  "baseline_check": {},
  "concurrent_load_tests": [],
  "sustained_load_test": {},
  "recovery_test": {},
  "final_status": {}
}
EOF

# Baseline health check
echo -e "${YELLOW}📊 Performing baseline health check${NC}"
baseline_healthy=$(check_health "$HEALTH_ENDPOINT")
baseline_response_time=$(measure_response_time "$HEALTH_ENDPOINT")

if [[ "$baseline_healthy" == "true" ]]; then
    echo -e "${GREEN}✅ Baseline health check passed (${baseline_response_time}s)${NC}"
else
    echo -e "${RED}❌ Baseline health check failed${NC}"
    exit 1
fi

# Update results file
jq --arg healthy "$baseline_healthy" --arg response_time "$baseline_response_time" \
   '.baseline_check = {healthy: ($healthy == "true"), response_time: ($response_time | tonumber)}' \
   "$RESULTS_FILE" > "${RESULTS_FILE}.tmp" && mv "${RESULTS_FILE}.tmp" "$RESULTS_FILE"

# Concurrent load tests with increasing load
echo -e "${BLUE}🚀 Starting concurrent load tests${NC}"

concurrency_levels=(5 10 20 50)
for concurrency in "${concurrency_levels[@]}"; do
    requests=$((concurrency * 10))  # 10 requests per concurrent connection
    run_concurrent_test $concurrency $requests "$HEALTH_ENDPOINT"
    
    # Add results to JSON
    jq --arg concurrency "$concurrency" --arg success_rate "$LAST_SUCCESS_RATE" --arg avg_time "$LAST_AVG_RESPONSE_TIME" \
       '.concurrent_load_tests += [{
         concurrency: ($concurrency | tonumber),
         success_rate: ($success_rate | tonumber),
         avg_response_time: ($avg_time | tonumber)
       }]' "$RESULTS_FILE" > "${RESULTS_FILE}.tmp" && mv "${RESULTS_FILE}.tmp" "$RESULTS_FILE"
    
    sleep 5  # Cool down between tests
done

# Sustained load test
echo -e "${YELLOW}⏱️ Running sustained load test (2 minutes)${NC}"
sustained_start=$(date +%s)
sustained_success=0
sustained_total=0
sustained_max_time=0
sustained_min_time=999

while [[ $(($(date +%s) - sustained_start)) -lt 120 ]]; do  # Run for 2 minutes
    response_time=$(measure_response_time "$HEALTH_ENDPOINT" 5)
    sustained_total=$((sustained_total + 1))
    
    if [[ "$response_time" != "-1" ]]; then
        sustained_success=$((sustained_success + 1))
        
        # Track min/max response times
        if (( $(echo "$response_time > $sustained_max_time" | bc -l 2>/dev/null || echo "0") )); then
            sustained_max_time=$response_time
        fi
        if (( $(echo "$response_time < $sustained_min_time" | bc -l 2>/dev/null || echo "0") )); then
            sustained_min_time=$response_time
        fi
    fi
    
    sleep 1
done

sustained_success_rate=$(echo "scale=2; $sustained_success * 100 / $sustained_total" | bc -l 2>/dev/null || echo "0")
echo -e "${GREEN}✅ Sustained load test: $sustained_success_rate% success rate over 2 minutes${NC}"
echo -e "${GREEN}📊 Response time range: ${sustained_min_time}s - ${sustained_max_time}s${NC}"

# Update results
jq --arg success_rate "$sustained_success_rate" --arg min_time "$sustained_min_time" --arg max_time "$sustained_max_time" --arg total "$sustained_total" \
   '.sustained_load_test = {
     success_rate: ($success_rate | tonumber),
     min_response_time: ($min_time | tonumber),
     max_response_time: ($max_time | tonumber),
     total_requests: ($total | tonumber)
   }' "$RESULTS_FILE" > "${RESULTS_FILE}.tmp" && mv "${RESULTS_FILE}.tmp" "$RESULTS_FILE"

# Recovery test - simulate brief downtime then measure recovery
echo -e "${YELLOW}🔄 Testing recovery capabilities${NC}"
recovery_start=$(date +%s)

# Simulate trying to access during potential downtime
recovery_attempts=0
recovery_success=0
recovery_first_success_time=0

for ((i=1; i<=30; i++)); do  # Try for 30 seconds
    response_time=$(measure_response_time "$HEALTH_ENDPOINT" 3)
    recovery_attempts=$((recovery_attempts + 1))
    
    if [[ "$response_time" != "-1" ]]; then
        recovery_success=$((recovery_success + 1))
        if [[ $recovery_first_success_time -eq 0 ]]; then
            recovery_first_success_time=$(($(date +%s) - recovery_start))
        fi
    fi
    
    sleep 1
done

recovery_success_rate=$(echo "scale=2; $recovery_success * 100 / $recovery_attempts" | bc -l 2>/dev/null || echo "0")
echo -e "${GREEN}✅ Recovery test: $recovery_success_rate% success rate, first success at ${recovery_first_success_time}s${NC}"

# Update results
jq --arg success_rate "$recovery_success_rate" --arg first_success "$recovery_first_success_time" \
   '.recovery_test = {
     success_rate: ($success_rate | tonumber),
     first_success_time: ($first_success | tonumber)
   }' "$RESULTS_FILE" > "${RESULTS_FILE}.tmp" && mv "${RESULTS_FILE}.tmp" "$RESULTS_FILE"

# Final status check
echo -e "${YELLOW}🔍 Final system status check${NC}"
final_healthy=$(check_health "$HEALTH_ENDPOINT")
final_response_time=$(measure_response_time "$HEALTH_ENDPOINT")

if [[ "$final_healthy" == "true" ]]; then
    echo -e "${GREEN}✅ Final health check passed (${final_response_time}s)${NC}"
else
    echo -e "${RED}❌ Final health check failed${NC}"
fi

# Update final results
jq --arg healthy "$final_healthy" --arg response_time "$final_response_time" \
   '.final_status = {healthy: ($healthy == "true"), response_time: ($response_time | tonumber)}' \
   "$RESULTS_FILE" > "${RESULTS_FILE}.tmp" && mv "${RESULTS_FILE}.tmp" "$RESULTS_FILE"

echo -e "${BLUE}📋 Test Results Summary:${NC}"
cat "$RESULTS_FILE" | jq '.'

echo -e "${GREEN}🎉 Chaos engineering stress tests completed!${NC}"
echo -e "${BLUE}Results saved to: $RESULTS_FILE${NC}"