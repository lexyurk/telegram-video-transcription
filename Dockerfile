FROM --platform=linux/amd64 python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js and npm
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs

# Install additional dependencies for Chrome/Puppeteer
RUN apt-get update && apt-get install -y \
    libgconf-2-4 \
    libgtk-3-0 \
    libxss1 \
    libasound2 \
    libxtst6 \
    libatspi2.0-0 \
    libdrm2 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libxkbcommon0 \
    libpango-1.0-0 \
    libcairo2 \
    libnspr4 \
    libnss3 \
    libxcursor1 \
    libxi6 \
    libxrender1 \
    libxft2 \
    libxinerama1 \
    fonts-liberation \
    libu2f-udev \
    libvulkan1 \
    && rm -rf /var/lib/apt/lists/*

# Install mermaid-cli globally  
RUN npm install -g @mermaid-js/mermaid-cli

# Set environment variables for Puppeteer and Chrome
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=false
ENV PUPPETEER_CACHE_DIR=/opt/puppeteer-cache

# Install Puppeteer globally and Chrome browser (x86-64)
RUN npm install -g puppeteer
RUN mkdir -p /opt/puppeteer-cache
RUN npx puppeteer browsers install chrome-headless-shell

# Find and set Chrome executable path
RUN CHROME_PATH=$(find /opt/puppeteer-cache -name "chrome-headless-shell" -type f -executable | head -1) && \
    echo "Found Chrome at: $CHROME_PATH" && \
    ln -sf "$CHROME_PATH" /usr/local/bin/chrome-headless-shell && \
    echo "export PUPPETEER_EXECUTABLE_PATH=$CHROME_PATH" >> /etc/environment && \
    echo "export CHROME_BIN=$CHROME_PATH" >> /etc/environment

# Install uv
RUN pip install uv

# Copy all project files (needed for building the package)
COPY pyproject.toml ./
COPY uv.lock ./
COPY README.md ./
COPY telegram_bot/ ./telegram_bot/
COPY main.py ./

# Install Python dependencies
RUN uv sync --frozen

# Create temp directory
RUN mkdir -p ./temp

# Create non-root user
RUN useradd --create-home --shell /bin/bash app

# Give app user access to puppeteer cache and make it owner of the app directory
RUN chown -R app:app /app /opt/puppeteer-cache

# Set runtime environment variables for Chrome
ENV CHROME_BIN=/usr/local/bin/chrome-headless-shell
ENV PUPPETEER_EXECUTABLE_PATH=/usr/local/bin/chrome-headless-shell

# Switch to app user
USER app

# Expose port (if needed for health checks)
EXPOSE 8000

# Run the bot
CMD ["uv", "run", "python", "main.py"] 