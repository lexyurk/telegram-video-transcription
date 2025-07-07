#!/bin/bash
# Setup script for mermaid-cli installation

echo "🚀 Setting up mermaid-cli for diagram generation..."

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js first:"
    echo "   - Ubuntu/Debian: sudo apt-get install nodejs npm"
    echo "   - macOS: brew install node"
    echo "   - Or download from: https://nodejs.org/"
    exit 1
fi

echo "✅ Node.js found: $(node --version)"

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo "❌ npm not found. Please install npm:"
    echo "   - Ubuntu/Debian: sudo apt-get install npm"
    echo "   - macOS: brew install npm"
    exit 1
fi

echo "✅ npm found: $(npm --version)"

# Install mermaid-cli globally
echo "📦 Installing @mermaid-js/mermaid-cli..."
npm install -g @mermaid-js/mermaid-cli

# Check if installation was successful
if ! command -v mmdc &> /dev/null; then
    echo "❌ mermaid-cli installation failed. Please check your npm configuration."
    exit 1
fi

echo "✅ mermaid-cli installed: $(mmdc --version)"

# Install Chrome headless shell for Puppeteer (needed for rendering)
echo "🎭 Installing Chrome headless shell for Puppeteer..."
npm install -g puppeteer
npx puppeteer browsers install chrome-headless-shell

# Configure Chrome properly
echo "🔧 Configuring Chrome..."
./scripts/setup_chrome.sh

echo "✅ Setup complete! Testing installation..."

# Test the installation
python3 scripts/test_mermaid.py

echo "🎉 mermaid-cli setup complete! Your bot is ready to generate diagrams."