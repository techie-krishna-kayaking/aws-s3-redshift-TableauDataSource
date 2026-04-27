#!/bin/bash
# Quick start script for BI Universal QA Tool

echo "========================================="
echo "BI Universal QA Tool"
echo "Quick Start Setup"
echo "========================================="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Install Playwright browsers (needed for regression testing)
echo "Installing Playwright browsers..."
python -m playwright install chromium 2>/dev/null || echo "  (Playwright browser install skipped — install manually if needed)"

echo ""
echo "✅ Setup complete!"
echo ""
echo "========================================="
echo "Next Steps:"
echo "========================================="
echo ""
echo "--- Data Validation ---"
echo "  python cli.py validate --config config/example_validations.yaml"
echo ""
echo "--- Tableau Regression Testing ---"
echo "  python cli.py regression --config bi_regression/configs/config.yaml"
echo ""
echo "--- Or use the original entry points directly ---"
echo "  python main.py --config config/my_validation.yaml"
echo "  python -m bi_regression.run --config bi_regression/configs/config.yaml"
echo ""
echo "========================================="
