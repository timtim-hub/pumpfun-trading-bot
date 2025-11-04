#!/bin/bash

# Script to push the project to GitHub
# Run this after the repository is created on GitHub

echo "🚀 Pushing to GitHub..."
echo ""

# Check if repository exists on GitHub
REPO_URL="https://github.com/timtim-hub/pumpfun-trading-bot.git"

echo "This script will push the code to:"
echo "  $REPO_URL"
echo ""
echo "Please ensure you have:"
echo "  1. Created the repository on GitHub (github.com/new)"
echo "  2. Set up authentication (SSH key or Personal Access Token)"
echo ""

read -p "Press Enter to continue or Ctrl+C to cancel..."

# Configure Git credentials if needed
echo ""
echo "Configuring Git..."
git config credential.helper store

# Try to push
echo ""
echo "Pushing to GitHub..."
git push -u origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Successfully pushed to GitHub!"
    echo ""
    echo "View your repository at:"
    echo "  https://github.com/timtim-hub/pumpfun-trading-bot"
else
    echo ""
    echo "❌ Push failed. You may need to:"
    echo ""
    echo "1. Create the repository on GitHub first:"
    echo "   https://github.com/new"
    echo "   Repository name: pumpfun-trading-bot"
    echo ""
    echo "2. Set up authentication:"
    echo "   - Personal Access Token: https://github.com/settings/tokens"
    echo "   - Or SSH Key: https://github.com/settings/keys"
    echo ""
    echo "3. Then run this script again"
fi

