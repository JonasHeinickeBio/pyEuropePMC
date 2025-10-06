#!/bin/bash

# CodeScene analysis script for pyEuropePMC project
# This script runs CodeScene CLI analysis on the entire Python codebase

set -e

echo "🔍 CodeScene Code Health Analysis"
echo "================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if CodeScene CLI is installed
if ! command -v cs &> /dev/null; then
    echo -e "${RED}❌ CodeScene CLI not found. Please install it first.${NC}"
    echo "Installation: curl https://downloads.codescene.io/enterprise/cli/install-cs-tool.sh | sh"
    exit 1
fi

# Check if access token is set
if [ -z "$CS_ACCESS_TOKEN" ]; then
    echo -e "${RED}❌ CS_ACCESS_TOKEN environment variable not set.${NC}"
    echo "Please set your CodeScene access token: export CS_ACCESS_TOKEN=your_token"
    exit 1
fi

echo -e "${GREEN}✅ CodeScene CLI is ready${NC}"
echo

# Function to analyze a single file
analyze_file() {
    local file=$1
    local relative_path=${file#./}

    echo -e "${BLUE}📄 Analyzing: $relative_path${NC}"

    # Run CodeScene check and capture output
    if cs check "$file" 2>/dev/null; then
        echo -e "${GREEN}✅ Analysis completed${NC}"
    else
        echo -e "${YELLOW}⚠️  Issues found or analysis failed${NC}"
    fi
    echo
}

# Function to run delta analysis
run_delta_analysis() {
    echo -e "${BLUE}🔄 Running delta analysis against main branch...${NC}"

    if git rev-parse --verify main >/dev/null 2>&1; then
        echo "Comparing current changes against main branch:"
        cs delta main || echo -e "${YELLOW}⚠️  Delta analysis completed with findings${NC}"
    else
        echo -e "${YELLOW}⚠️  Main branch not found, analyzing staged changes instead:${NC}"
        cs delta --staged || echo -e "${YELLOW}⚠️  Delta analysis completed with findings${NC}"
    fi
    echo
}

# Main analysis function
main() {
    echo -e "${BLUE}📊 Analyzing Python source files...${NC}"
    echo

    # Find and analyze all Python files in src/
    find src/ -name "*.py" -type f | while read -r file; do
        analyze_file "$file"
    done

    # Run delta analysis if we're in a git repository
    if git rev-parse --git-dir >/dev/null 2>&1; then
        run_delta_analysis
    else
        echo -e "${YELLOW}⚠️  Not in a git repository, skipping delta analysis${NC}"
    fi

    echo -e "${GREEN}✅ CodeScene analysis completed!${NC}"
    echo
    echo -e "${BLUE}💡 Tips:${NC}"
    echo "   • Focus on files with complex methods (cc > 10)"
    echo "   • Reduce function arguments (keep ≤ 4 parameters)"
    echo "   • Break down complex conditionals"
    echo "   • Eliminate code duplication"
    echo "   • Use 'cs review <file>' for detailed analysis"
}

# Run with command line arguments
case "${1:-}" in
    "delta")
        run_delta_analysis
        ;;
    "help"|"-h"|"--help")
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  delta    Run only delta analysis"
        echo "  help     Show this help message"
        echo "  (none)   Run full analysis"
        ;;
    *)
        main
        ;;
esac
