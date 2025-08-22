#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

TOXIPROXY_HOST="${TOXIPROXY_HOST:-toxiproxy:8474}"
RESULTS_FILE="/tmp/network_chaos_results.json"

echo -e "${BLUE}🌐 Starting Network Chaos Engineering Tests${NC}"

# Function to configure toxiproxy
configure_toxiproxy() {
    local proxy_name=$1
    local listen_port=$2
    local upstream_host=$3
    local upstream_port=$4
    
    echo -e "${YELLOW}⚙️ Configuring toxiproxy: $proxy_name${NC}"
    
    # Create proxy
    curl -sf -X POST "$TOXIPROXY_HOST/proxies" \
        -H "Content-Type: application/json" \
        -d "{
            \"name\": \"$proxy_name\",
            \"listen\": \"0.0.0.0:$listen_port\",
            \"upstream\": \"$upstream_host:$upstream_port\"
        }" || echo "Proxy might already exist"
}

# Function to add toxicity
add_toxicity() {
    local proxy_name=$1
    local toxicity_type=$2
    local toxicity_name=$3
    local toxicity_level=$4
    local attributes=$5
    
    echo -e "${YELLOW}☢️ Adding toxicity: $toxicity_name to $proxy_name${NC}"
    
    curl -sf -X POST "$TOXIPROXY_HOST/proxies/$proxy_name/toxics" \
        -H "Content-Type: application/json" \
        -d "{
            \"name\": \"$toxicity_name\",
            \"type\": \"$toxicity_type\",
            \"toxicity\": $toxicity_level,
            \"attributes\": $attributes
        }" || echo "Failed to add toxicity"
}

# Function to remove toxicity
remove_toxicity() {
    local proxy_name=$1
    local toxicity_name=$2
    
    echo -e "${GREEN}🧹 Removing toxicity: $toxicity_name from $proxy_name${NC}"
    
    curl -sf -X DELETE "$TOXIPROXY_HOST/proxies/$proxy_name/toxics/$toxicity_name" \
        || echo "Failed to remove toxicity"
}

# Function to test endpoint through proxy
test_through_proxy() {
    local proxy_host="toxiproxy"
    local proxy_port=$1
    local endpoint=$2
    local timeout=${3:-10}
    
    local start_time=$(date +%s.%N)
    if curl -sf --max-time $timeout "http://$proxy_host:$proxy_port$endpoint" >/dev/null 2>&1; then
        local end_time=$(date +%s.%N)
        local response_time=$(echo "$end_time - $start_time" | bc -l 2>/dev/null || echo "0")
        echo "success:$response_time"
    else
        echo "failure:-1"
    fi
}

# Function to run network test scenario
run_network_scenario() {
    local scenario_name=$1
    local proxy_name=$2
    local proxy_port=$3
    local toxicity_type=$4
    local toxicity_level=$5
    local toxicity_attributes=$6
    local test_duration=${7:-30}
    
    echo -e "${BLUE}🧪 Running scenario: $scenario_name${NC}"
    
    local success_count=0
    local total_requests=0
    local total_response_time=0
    local max_response_time=0
    local min_response_time=999
    
    # Add toxicity
    add_toxicity "$proxy_name" "$toxicity_type" "${scenario_name}_toxic" "$toxicity_level" "$toxicity_attributes"
    
    # Test for specified duration
    local end_time=$(($(date +%s) + test_duration))
    while [[ $(date +%s) -lt $end_time ]]; do
        local result=$(test_through_proxy "$proxy_port" "/civicpulse/health/" 15)
        total_requests=$((total_requests + 1))
        
        if [[ "$result" == success:* ]]; then
            success_count=$((success_count + 1))
            local response_time=${result#success:}
            total_response_time=$(echo "$total_response_time + $response_time" | bc -l 2>/dev/null || echo "$total_response_time")
            
            # Track min/max
            if (( $(echo "$response_time > $max_response_time" | bc -l 2>/dev/null || echo "0") )); then
                max_response_time=$response_time
            fi
            if (( $(echo "$response_time < $min_response_time" | bc -l 2>/dev/null || echo "1") )); then
                min_response_time=$response_time
            fi
        fi
        
        sleep 2
    done
    
    # Remove toxicity
    remove_toxicity "$proxy_name" "${scenario_name}_toxic"
    
    # Calculate metrics
    local success_rate=$(echo "scale=2; $success_count * 100 / $total_requests" | bc -l 2>/dev/null || echo "0")
    local avg_response_time=0
    if [[ $success_count -gt 0 ]]; then
        avg_response_time=$(echo "scale=3; $total_response_time / $success_count" | bc -l 2>/dev/null || echo "0")
    fi
    
    echo -e "${GREEN}📊 Scenario results: $success_rate% success, avg ${avg_response_time}s, range ${min_response_time}s-${max_response_time}s${NC}"
    
    # Store results globally
    SCENARIO_SUCCESS_RATE=$success_rate
    SCENARIO_AVG_RESPONSE_TIME=$avg_response_time
    SCENARIO_MIN_RESPONSE_TIME=$min_response_time
    SCENARIO_MAX_RESPONSE_TIME=$max_response_time
}

# Initialize results
cat > "$RESULTS_FILE" << EOF
{
  "test_timestamp": "$(date -Iseconds)",
  "network_scenarios": [],
  "recovery_tests": []
}
EOF

# Wait for toxiproxy to be ready
echo -e "${YELLOW}⏳ Waiting for toxiproxy to be ready...${NC}"
for i in {1..30}; do
    if curl -sf "$TOXIPROXY_HOST/proxies" >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Toxiproxy is ready${NC}"
        break
    fi
    sleep 2
done

# Configure proxies for different services
configure_toxiproxy "web_proxy" 8080 "web" 8000
configure_toxiproxy "db_proxy" 5433 "db" 5432
configure_toxiproxy "redis_proxy" 6380 "redis" 6379

# Network latency scenarios
echo -e "${BLUE}🌐 Testing Network Latency Scenarios${NC}"

latency_scenarios=(
    "low_latency:latency:0.5:{\"latency\":100}"
    "medium_latency:latency:0.8:{\"latency\":500}"
    "high_latency:latency:1.0:{\"latency\":2000}"
)

for scenario in "${latency_scenarios[@]}"; do
    IFS=':' read -r name type toxicity attributes <<< "$scenario"
    run_network_scenario "$name" "web_proxy" 8080 "$type" "$toxicity" "$attributes" 60
    
    # Add to results
    jq --arg name "$name" --arg success_rate "$SCENARIO_SUCCESS_RATE" \
       --arg avg_time "$SCENARIO_AVG_RESPONSE_TIME" --arg min_time "$SCENARIO_MIN_RESPONSE_TIME" \
       --arg max_time "$SCENARIO_MAX_RESPONSE_TIME" \
       '.network_scenarios += [{
         name: $name,
         success_rate: ($success_rate | tonumber),
         avg_response_time: ($avg_time | tonumber),
         min_response_time: ($min_time | tonumber),
         max_response_time: ($max_time | tonumber)
       }]' "$RESULTS_FILE" > "${RESULTS_FILE}.tmp" && mv "${RESULTS_FILE}.tmp" "$RESULTS_FILE"
done

# Packet loss scenarios
echo -e "${BLUE}📡 Testing Packet Loss Scenarios${NC}"

packet_loss_scenarios=(
    "light_packet_loss:bandwidth:0.3:{\"rate\":0}"
    "moderate_packet_loss:bandwidth:0.5:{\"rate\":0}"
    "heavy_packet_loss:bandwidth:0.8:{\"rate\":0}"
)

for scenario in "${packet_loss_scenarios[@]}"; do
    IFS=':' read -r name type toxicity attributes <<< "$scenario"
    run_network_scenario "$name" "web_proxy" 8080 "$type" "$toxicity" "$attributes" 45
    
    # Add to results
    jq --arg name "$name" --arg success_rate "$SCENARIO_SUCCESS_RATE" \
       --arg avg_time "$SCENARIO_AVG_RESPONSE_TIME" --arg min_time "$SCENARIO_MIN_RESPONSE_TIME" \
       --arg max_time "$SCENARIO_MAX_RESPONSE_TIME" \
       '.network_scenarios += [{
         name: $name,
         success_rate: ($success_rate | tonumber),
         avg_response_time: ($avg_time | tonumber),
         min_response_time: ($min_time | tonumber),
         max_response_time: ($max_time | tonumber)
       }]' "$RESULTS_FILE" > "${RESULTS_FILE}.tmp" && mv "${RESULTS_FILE}.tmp" "$RESULTS_FILE"
done

# Connection timeout scenarios
echo -e "${BLUE}⏱️ Testing Connection Timeout Scenarios${NC}"

timeout_scenarios=(
    "short_timeout:timeout:1.0:{\"timeout\":5000}"
    "medium_timeout:timeout:1.0:{\"timeout\":15000}"
)

for scenario in "${timeout_scenarios[@]}"; do
    IFS=':' read -r name type toxicity attributes <<< "$scenario"
    run_network_scenario "$name" "web_proxy" 8080 "$type" "$toxicity" "$attributes" 30
    
    # Add to results
    jq --arg name "$name" --arg success_rate "$SCENARIO_SUCCESS_RATE" \
       --arg avg_time "$SCENARIO_AVG_RESPONSE_TIME" --arg min_time "$SCENARIO_MIN_RESPONSE_TIME" \
       --arg max_time "$SCENARIO_MAX_RESPONSE_TIME" \
       '.network_scenarios += [{
         name: $name,
         success_rate: ($success_rate | tonumber),
         avg_response_time: ($avg_time | tonumber),
         min_response_time: ($min_time | tonumber),
         max_response_time: ($max_time | tonumber)
       }]' "$RESULTS_FILE" > "${RESULTS_FILE}.tmp" && mv "${RESULTS_FILE}.tmp" "$RESULTS_FILE"
done

# Recovery testing
echo -e "${BLUE}🔄 Testing Network Recovery${NC}"

# Test recovery after severe network issues
add_toxicity "web_proxy" "latency" "recovery_test" 1.0 '{"latency": 10000}'
sleep 5  # Let the toxicity take effect

# Remove toxicity and measure recovery
remove_toxicity "web_proxy" "recovery_test"

recovery_start=$(date +%s)
recovery_success=0
recovery_attempts=0
first_success_time=0

for ((i=1; i<=60; i++)); do
    local result=$(test_through_proxy 8080 "/civicpulse/health/" 5)
    recovery_attempts=$((recovery_attempts + 1))
    
    if [[ "$result" == success:* ]]; then
        recovery_success=$((recovery_success + 1))
        if [[ $first_success_time -eq 0 ]]; then
            first_success_time=$(($(date +%s) - recovery_start))
        fi
    fi
    
    sleep 1
done

recovery_success_rate=$(echo "scale=2; $recovery_success * 100 / $recovery_attempts" | bc -l 2>/dev/null || echo "0")

# Add recovery results
jq --arg success_rate "$recovery_success_rate" --arg first_success "$first_success_time" \
   '.recovery_tests += [{
     test: "network_recovery",
     success_rate: ($success_rate | tonumber),
     first_success_time: ($first_success | tonumber),
     total_attempts: 60
   }]' "$RESULTS_FILE" > "${RESULTS_FILE}.tmp" && mv "${RESULTS_FILE}.tmp" "$RESULTS_FILE"

echo -e "${GREEN}🎉 Network chaos tests completed!${NC}"
echo -e "${BLUE}📋 Final Results:${NC}"
cat "$RESULTS_FILE" | jq '.'

echo -e "${BLUE}Results saved to: $RESULTS_FILE${NC}"