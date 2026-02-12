#!/bin/bash
# Unix/Linux/Mac shell script to run the Agentic Document Processor

echo ""
echo "========================================"
echo " Agentic Document Processor"
echo "========================================"
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "ERROR: Virtual environment not found"
    echo "Please create one with: python -m venv .venv"
    exit 1
fi

# Activate virtual environment
source .venv/bin/activate

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "WARNING: .env file not found"
    echo "Copy .env.example to .env and configure your API keys"
    read -p "Press enter to continue..."
fi

# Run the Python script
python run.py
