#!/bin/bash
# Script to configure Chrome properly for mermaid-cli

echo "🔧 Configuring Chrome for mermaid-cli..."

# Find the Chrome executable
CHROME_PATH=""
POSSIBLE_PATHS=(
    "/opt/puppeteer-cache/chrome-headless-shell/linux-*/chrome-headless-shell"
    "/root/.cache/puppeteer/chrome-headless-shell/linux-*/chrome-headless-shell"
    "/home/app/.cache/puppeteer/chrome-headless-shell/linux-*/chrome-headless-shell"
    "/usr/bin/google-chrome"
    "/usr/bin/chromium-browser"
    "/usr/bin/chrome"
)

for path_pattern in "${POSSIBLE_PATHS[@]}"; do
    # Use ls to expand wildcards
    for path in $path_pattern; do
        if [ -f "$path" ] && [ -x "$path" ]; then
            CHROME_PATH="$path"
            echo "✅ Found Chrome at: $CHROME_PATH"
            break 2
        fi
    done
done

if [ -z "$CHROME_PATH" ]; then
    echo "❌ Chrome executable not found. Installing..."
    
    # Try to install Chrome headless shell
    if command -v npx >/dev/null 2>&1; then
        echo "📦 Installing Chrome headless shell..."
        npx puppeteer browsers install chrome-headless-shell
        
        # Try to find it again
        for path_pattern in "${POSSIBLE_PATHS[@]}"; do
            for path in $path_pattern; do
                if [ -f "$path" ] && [ -x "$path" ]; then
                    CHROME_PATH="$path"
                    echo "✅ Found Chrome after installation at: $CHROME_PATH"
                    break 2
                fi
            done
        done
    fi
    
    if [ -z "$CHROME_PATH" ]; then
        echo "❌ Still could not find Chrome. Please install Chrome or Chromium manually."
        exit 1
    fi
fi

# Create a symbolic link to a standard location
echo "🔗 Creating symbolic link..."
sudo mkdir -p /usr/local/bin
sudo ln -sf "$CHROME_PATH" /usr/local/bin/chrome-headless-shell

# Set environment variables
echo "🌍 Setting environment variables..."
cat >> ~/.bashrc << EOF

# Chrome configuration for mermaid-cli
export PUPPETEER_EXECUTABLE_PATH="$CHROME_PATH"
export CHROME_BIN="$CHROME_PATH"
EOF

# Export for current session
export PUPPETEER_EXECUTABLE_PATH="$CHROME_PATH"
export CHROME_BIN="$CHROME_PATH"

echo "✅ Chrome configuration complete!"
echo "Chrome path: $CHROME_PATH"
echo "Environment variables set."

# Test mermaid-cli
echo "🧪 Testing mermaid-cli with Chrome..."
if command -v mmdc >/dev/null 2>&1; then
    echo "Testing mmdc command..."
    echo "graph TD; A-->B" | mmdc -o /tmp/test.png 2>&1 && echo "✅ mermaid-cli test successful!" || echo "❌ mermaid-cli test failed"
else
    echo "❌ mmdc command not found. Please install @mermaid-js/mermaid-cli"
fi