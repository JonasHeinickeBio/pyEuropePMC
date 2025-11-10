#!/bin/bash

# CodeScene analysis script for pyEuropePMC project
# This script runs CodeScene CLI analysis on the entire Python codebase

set -e

# Load environment variables from .env file if it exists
if [ -f ".env" ]; then
    echo "🔧 Loading environment variables from .env file..."
    set -a
    source .env
    set +a
    echo "✅ Environment variables loaded"
fi

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
    echo "Installation: curl -s https://downloads.codescene.io/enterprise/cli/install-cs-tool.sh | bash -s -- -y"
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

# Function to run check analysis on all files
run_check_analysis() {
    echo -e "${BLUE}� Running CodeScene check analysis on all Python files...${NC}"
    echo

    local total_files=$(find src/ -name "*.py" -type f | wc -l)
    local processed=0

    find src/ -name "*.py" -type f | while read -r file; do
        processed=$((processed + 1))
        local relative_path=${file#./}
        echo -e "${BLUE}📄 [$processed/$total_files] Checking: $relative_path${NC}"

        # Run CodeScene check and capture output
        if cs check "$file" 2>/dev/null; then
            echo -e "${GREEN}✅ Check completed${NC}"
        else
            echo -e "${YELLOW}⚠️  Issues found${NC}"
        fi
        echo
    done

    echo -e "${GREEN}✅ CodeScene check analysis completed! ($total_files files processed)${NC}"
    echo
}

# Function to run review analysis on key files
run_review_analysis() {
    echo -e "${BLUE}🔬 Running CodeScene review analysis on key Python files...${NC}"
    echo

    # Create reviews directory
    mkdir -p reviews_output

    # Get top 10 files by size (likely most complex)
    echo "Selecting top files for detailed review..."
    local files_to_review=$(find src/ -name "*.py" -type f -exec wc -l {} \; | sort -nr | head -10 | awk '{print $2}')

    local processed=0
    echo "$files_to_review" | while read -r file; do
        if [ -n "$file" ] && [ -f "$file" ]; then
            processed=$((processed + 1))
            local relative_path=${file#./}
            local filename=$(basename "$file" .py)

            echo -e "${BLUE}📋 [$processed/10] Reviewing: $relative_path${NC}"

            # Run CodeScene review and save output
            if cs review "$file" --output-format json > "reviews_output/${filename}_review.json" 2>/dev/null; then
                echo -e "${GREEN}✅ Review completed and saved${NC}"
            else
                echo -e "${YELLOW}⚠️  Review failed or found issues${NC}"
                echo '{"error": "Review failed"}' > "reviews_output/${filename}_review.json"
            fi
        fi
    done

    echo -e "${GREEN}✅ CodeScene review analysis completed!${NC}"
    echo -e "${BLUE}💡 Review results saved in: reviews_output/${NC}"
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
    echo "   • Use '$0 check' for lint-like analysis"
    echo "   • Use '$0 review' for detailed file reviews"
    echo "   • Use '$0 delta' for change analysis"
    echo "   • Use '$0 all' for complete analysis suite"
}

# Run with command line arguments
case "${1:-}" in
    "delta")
        run_delta_analysis
        ;;
    "check")
        run_check_analysis
        ;;
    "review")
        run_review_analysis
        ;;
    "all")
        echo -e "${BLUE}🚀 Running complete CodeScene analysis suite...${NC}"
        echo
        run_check_analysis
        run_review_analysis
        run_delta_analysis
        ;;
    "help"|"-h"|"--help")
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  delta    Run only delta analysis (compares changes)"
        echo "  check    Run check analysis on all Python files"
        echo "  review   Run detailed review analysis on key files"
        echo "  all      Run complete analysis suite (check + review + delta)"
        echo "  help     Show this help message"
        echo "  (none)   Run full analysis (legacy mode)"
        ;;
    *)
        main
        ;;
esac
