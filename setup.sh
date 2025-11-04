#!/bin/bash

# Pump.fun Trading Bot Setup Script
# Automated setup for macOS and Linux

set -e  # Exit on error

echo "=================================="
echo "🚀 Pump.fun Trading Bot Setup"
echo "=================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python version
echo "📋 Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    
    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 9 ]; then
        echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION found"
    else
        echo -e "${RED}✗${NC} Python 3.9+ required (found $PYTHON_VERSION)"
        exit 1
    fi
else
    echo -e "${RED}✗${NC} Python 3 not found. Please install Python 3.9 or higher."
    exit 1
fi

# Create virtual environment
echo ""
echo "📦 Creating virtual environment..."
if [ -d "venv" ]; then
    echo -e "${YELLOW}⚠${NC}  Virtual environment already exists. Skipping..."
else
    python3 -m venv venv
    echo -e "${GREEN}✓${NC} Virtual environment created"
fi

# Activate virtual environment
echo ""
echo "🔧 Activating virtual environment..."
source venv/bin/activate
echo -e "${GREEN}✓${NC} Virtual environment activated"

# Upgrade pip
echo ""
echo "⬆️  Upgrading pip..."
pip install --upgrade pip --quiet
echo -e "${GREEN}✓${NC} pip upgraded"

# Install dependencies
echo ""
echo "📥 Installing dependencies..."
pip install -r requirements.txt --quiet
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Dependencies installed"
else
    echo -e "${RED}✗${NC} Failed to install dependencies"
    exit 1
fi

# Create necessary directories
echo ""
echo "📁 Creating directories..."
mkdir -p logs data docs
echo -e "${GREEN}✓${NC} Directories created"

# Copy environment file if doesn't exist
echo ""
echo "⚙️  Setting up environment..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}✓${NC} .env file created from template"
        echo -e "${YELLOW}⚠${NC}  Please edit .env with your settings"
    else
        echo -e "${YELLOW}⚠${NC}  .env.example not found, skipping"
    fi
else
    echo -e "${YELLOW}⚠${NC}  .env already exists, skipping"
fi

# Check if config.yaml exists
echo ""
echo "📄 Checking configuration..."
if [ -f "config.yaml" ]; then
    echo -e "${GREEN}✓${NC} config.yaml found"
else
    echo -e "${YELLOW}⚠${NC}  config.yaml not found. Please create one."
fi

# Summary
echo ""
echo "=================================="
echo "✅ Setup Complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Activate virtual environment:"
echo "   ${GREEN}source venv/bin/activate${NC}"
echo ""
echo "2. Edit configuration:"
echo "   ${GREEN}nano config.yaml${NC}"
echo ""
echo "3. (Optional) Create a wallet:"
echo "   ${GREEN}python bot.py --create-keypair wallet.json${NC}"
echo ""
echo "4. Run in dry-run mode:"
echo "   ${GREEN}python bot.py${NC}"
echo ""
echo "5. When ready, run live:"
echo "   ${GREEN}python bot.py --mode live${NC}"
echo ""
echo "For more help, see:"
echo "   - README.md"
echo "   - docs/SETUP_GUIDE.md"
echo "   - docs/STRATEGY_GUIDE.md"
echo ""
echo "Happy trading! 🚀"
echo ""

