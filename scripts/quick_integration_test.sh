#!/bin/bash
# Quick Integration Test Runner
# Runs Phase 2 integration tests with simple output

set -e

echo "================================"
echo "Phase 2 Integration Test Suite"
echo "================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}❌ Error: .env file not found${NC}"
    echo "Please create .env with Alpaca credentials"
    exit 1
fi

echo -e "${YELLOW}Testing Module 1: Alpaca Integration${NC}"
pytest tests/integration/test_phase2_integration.py::TestModule1_AlpacaIntegration -v -m integration || {
    echo -e "${RED}❌ Module 1 FAILED${NC}"
    exit 1
}
echo -e "${GREEN}✅ Module 1 PASSED${NC}\n"

echo -e "${YELLOW}Testing Module 2: Scheduler & Workflows${NC}"
pytest tests/integration/test_phase2_integration.py::TestModule2_SchedulerIntegration -v || {
    echo -e "${RED}❌ Module 2 FAILED${NC}"
    exit 1
}
echo -e "${GREEN}✅ Module 2 PASSED${NC}\n"

echo -e "${YELLOW}Testing Module 3: Dynamic Risk Management${NC}"
pytest tests/integration/test_phase2_integration.py::TestModule3_RiskManagement -v || {
    echo -e "${RED}❌ Module 3 FAILED${NC}"
    exit 1
}
echo -e "${GREEN}✅ Module 3 PASSED${NC}\n"

echo -e "${YELLOW}Testing Module 4: Monitoring & CLI Tools${NC}"
pytest tests/integration/test_phase2_integration.py::TestModule4_Monitoring -v || {
    echo -e "${RED}❌ Module 4 FAILED${NC}"
    exit 1
}
echo -e "${GREEN}✅ Module 4 PASSED${NC}\n"

echo -e "${YELLOW}Testing Interface Compatibility${NC}"
pytest tests/integration/test_phase2_integration.py::TestInterfaceCompatibility -v || {
    echo -e "${RED}❌ Interface Tests FAILED${NC}"
    exit 1
}
echo -e "${GREEN}✅ Interface Tests PASSED${NC}\n"

echo -e "${YELLOW}Testing End-to-End Integration${NC}"
pytest tests/integration/test_phase2_integration.py::TestEndToEndIntegration -v -m integration || {
    echo -e "${RED}❌ E2E Tests FAILED${NC}"
    exit 1
}
echo -e "${GREEN}✅ E2E Tests PASSED${NC}\n"

echo "================================"
echo -e "${GREEN}🎉 ALL INTEGRATION TESTS PASSED${NC}"
echo "================================"
echo ""
echo "Phase 2 is ready for paper trading validation!"
echo ""
