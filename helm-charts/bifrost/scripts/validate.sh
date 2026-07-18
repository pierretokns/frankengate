#!/bin/bash
# Bifrost Helm Chart Validation Script
# This script validates the Helm chart before installation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${BLUE}ℹ ${NC}$1"
}

print_success() {
    echo -e "${GREEN}✓ ${NC}$1"
}

print_error() {
    echo -e "${RED}✗ ${NC}$1"
}

print_banner() {
    echo ""
    echo -e "${BLUE}╔═══════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                                           ║${NC}"
    echo -e "${BLUE}║      Bifrost Chart Validator             ║${NC}"
    echo -e "${BLUE}║                                           ║${NC}"
    echo -e "${BLUE}╚═══════════════════════════════════════════╝${NC}"
    echo ""
}

# Set explicit chart directory (parent of scripts directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHART_DIR="$SCRIPT_DIR/.."

print_banner

# Check if Helm is installed
print_info "Checking Helm installation..."
if ! command -v helm &> /dev/null; then
    print_error "Helm is not installed"
    exit 1
fi
print_success "Helm is installed"

# Lint the chart
print_info "Linting Helm chart..."
if helm lint "$CHART_DIR"; then
    print_success "Chart linting passed"
else
    print_error "Chart linting failed"
    exit 1
fi

# Template the chart with default values
print_info "Templating chart with default values..."
if helm template test-release "$CHART_DIR" > /dev/null; then
    print_success "Default values template successful"
else
    print_error "Default values template failed"
    exit 1
fi

# Test all example configurations
print_info "Testing example configurations..."
for config in "$CHART_DIR"/values-examples/*.yaml; do
    config_name=$(basename "$config")
    print_info "  Testing $config_name..."
    if helm template test-release "$CHART_DIR" -f "$config" > /dev/null; then
        print_success "  $config_name: OK"
    else
        print_error "  $config_name: FAILED"
        exit 1
    fi
done

# Validate the fork's governance virtual-key schema/render contract without a
# Kubernetes cluster. Keep this before the optional helm install dry-run so a
# missing local cluster does not hide chart contract regressions.
print_info "Validating governance virtual-key schema and render..."
if "$SCRIPT_DIR/validate-governance-values.sh"; then
    print_success "Governance virtual-key validation passed"
else
    print_error "Governance virtual-key validation failed"
    exit 1
fi

print_info "Validating external PostgreSQL and Redis values/render..."
if "$SCRIPT_DIR/validate-external-dependencies.sh"; then
    print_success "External dependency validation passed"
else
    print_error "External dependency validation failed"
    exit 1
fi

print_info "Validating capacity-safe rollout strategy..."
if "$SCRIPT_DIR/validate-rollout-strategy.sh"; then
    print_success "Capacity-safe rollout validation passed"
else
    print_error "Capacity-safe rollout validation failed"
    exit 1
fi

print_info "Validating Prometheus Operator monitoring resources..."
if "$SCRIPT_DIR/validate-monitoring.sh"; then
    print_success "Prometheus Operator monitoring validation passed"
else
    print_error "Prometheus Operator monitoring validation failed"
    exit 1
fi

# Client-side install render (does not require a live Kubernetes API)
print_info "Performing client-side install render..."
if helm template test-release "$CHART_DIR" > /dev/null 2>&1; then
    print_success "Client-side install render successful"
else
    print_error "Dry-run installation failed"
    exit 1
fi

echo ""
print_success "All validation checks passed!"
echo ""
print_info "Chart is ready for installation"
