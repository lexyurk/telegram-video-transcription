# Diagram Generation Troubleshooting Guide

## 🔧 Issue Resolution

The Chrome/Puppeteer issue you encountered has been fixed with the following changes:

### ✅ What Was Fixed:

1. **Chrome Installation**: Changed from Playwright to Puppeteer's Chrome headless shell
2. **User Permissions**: Configured proper file permissions for the app user
3. **Environment Variables**: Set correct paths for Chrome executable
4. **Browser Configuration**: Added Docker-specific Chrome flags for headless operation
5. **Fallback Logic**: Added retry mechanism with simpler commands
6. **Better Logging**: Enhanced error messages and debugging output

### 🏗️ Updated Dockerfile:

```dockerfile
# Install Puppeteer and Chrome browser
RUN npm install -g puppeteer
RUN mkdir -p /opt/puppeteer-cache
RUN npx puppeteer browsers install chrome-headless-shell

# Find and set Chrome executable path
RUN CHROME_PATH=$(find /opt/puppeteer-cache -name "chrome-headless-shell" -type f -executable | head -1) && \
    echo "Found Chrome at: $CHROME_PATH" && \
    ln -sf "$CHROME_PATH" /usr/local/bin/chrome-headless-shell && \
    echo "export PUPPETEER_EXECUTABLE_PATH=$CHROME_PATH" >> /etc/environment && \
    echo "export CHROME_BIN=$CHROME_PATH" >> /etc/environment

# Set runtime environment variables for Chrome
ENV CHROME_BIN=/usr/local/bin/chrome-headless-shell
ENV PUPPETEER_EXECUTABLE_PATH=/usr/local/bin/chrome-headless-shell
```

### 🔄 Enhanced DiagramService:

- Added Chrome-specific flags: `--no-sandbox`, `--disable-setuid-sandbox`, `--disable-dev-shm-usage`
- Implemented fallback command execution if the main command fails
- Enhanced logging for better debugging

## 🐛 Common Issues & Solutions:

### Issue 1: Chrome Not Found
**Error**: `Could not find Chrome (ver. X.X.X)`

**Solution**:
```bash
# Rebuild Docker image with latest fixes
docker build -t telegram-transcription-bot .

# Or run Chrome setup manually
./scripts/setup_chrome.sh
```

### Issue 2: Permission Denied
**Error**: Permission issues accessing Chrome or temporary files

**Solution**:
```bash
# Check permissions in Docker container
docker exec -it <container> ls -la /usr/local/bin/chrome-headless-shell
docker exec -it <container> ls -la /opt/puppeteer-cache/

# Or rebuild with proper permissions
docker-compose down
docker-compose up --build
```

### Issue 3: Puppeteer Cache Issues
**Error**: Puppeteer cache-related errors

**Solution**:
```bash
# Clear Docker volumes and rebuild
docker-compose down -v
docker system prune -f
docker-compose up --build
```

### Issue 4: mermaid-cli Syntax Error
**Error**: Diagram generation fails due to invalid mermaid syntax

**Check**: The AI-generated mermaid code in logs and verify syntax
**Solution**: The service now includes better error handling and retry logic

## 🧪 Testing Setup:

### 1. Test mermaid-cli Installation:
```bash
python3 scripts/test_mermaid.py
```

### 2. Test Complete Pipeline:
```bash
python3 scripts/test_diagram_integration.py
```

### 3. Manual Chrome Test:
```bash
# Test Chrome directly
/usr/local/bin/chrome-headless-shell --version

# Test mmdc with simple diagram
echo "graph TD; A-->B" | mmdc -o /tmp/test.png
```

## 📊 Monitoring Logs:

### Docker Logs:
```bash
docker-compose logs -f telegram-transcription-bot
```

### Key Log Messages to Look For:
- ✅ `Successfully generated mermaid code: X characters`
- ✅ `Successfully converted mermaid to image: /tmp/diagram_X.png`
- ❌ `Failed to convert mermaid to image. Return code: 1`
- ❌ `Could not find Chrome`

## 🔄 If Issues Persist:

### Option 1: Alternative Diagram Service
If Chrome/Puppeteer continues to cause issues, consider implementing an alternative using:
- Online mermaid rendering services
- Different diagram libraries (matplotlib, graphviz)
- Server-side rendering services

### Option 2: Disable Diagram Feature Temporarily
Comment out the diagram command in `bot.py`:
```python
# application.add_handler(CommandHandler("diagram", self.diagram_command))
```

### Option 3: Manual Installation
```bash
# Install Chrome manually in container
apt-get update && apt-get install -y google-chrome-stable

# Set environment variable
export PUPPETEER_EXECUTABLE_PATH=/usr/bin/google-chrome
```

## 📞 Support Commands:

### Check Environment:
```bash
docker exec -it <container> env | grep -E "(CHROME|PUPPETEER)"
```

### Check Chrome Path:
```bash
docker exec -it <container> find / -name "*chrome*" -type f 2>/dev/null
```

### Test Permissions:
```bash
docker exec -it <container> whoami
docker exec -it <container> groups
```

## 🚀 Next Steps:

1. **Rebuild** your Docker container with the updated Dockerfile
2. **Test** the diagram generation with a sample transcript
3. **Monitor** logs for any remaining issues
4. **Report** any new errors with full log context

The diagram feature should now work correctly! 🎉