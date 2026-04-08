#!/bin/bash
# Quick start script for Universal Data Validation Framework

echo "========================================="
echo "Universal Data Validation Framework"
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

echo ""
echo "✅ Setup complete!"
echo ""
echo "========================================="
echo "Next Steps:"
echo "========================================="
echo ""
echo "1. Configure Redshift credentials (if using table adapter):"
echo "   cp .env.example .env"
echo "   # Edit .env with your credentials"
echo ""
echo "2. Run test validation:"
echo "   python main.py --config config/test_validation.yaml"
echo ""
echo "3. View results:"
echo "   open results/sample_csv_validation_test.html"
echo ""
echo "4. Create your own validation:"
echo "   # Edit config/example_validations.yaml"
echo "   python main.py --config config/your_config.yaml"
echo ""
echo "========================================="
