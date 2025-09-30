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
    graphviz \
    graphviz-dev \
    fonts-dejavu-core \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies for visualization (matplotlib, networkx, etc.)
# No Node.js, Chrome, or Puppeteer needed - pure Python approach

# Install uv
RUN pip install uv

# Copy all project files (needed for building the package)
COPY pyproject.toml ./
COPY README.md ./
COPY analytics.py ./
COPY telegram_bot/ ./telegram_bot/
COPY zoom_backend/ ./zoom_backend/
COPY main.py ./

# Install Python dependencies (generate lock file for linux/amd64)
# Note: We don't copy uv.lock as it was generated on macOS and may have incompatible versions
RUN uv sync

# Create temp directory
RUN mkdir -p ./temp

# Create non-root user
RUN useradd --create-home --shell /bin/bash app

# Give app user ownership of the app directory
RUN chown -R app:app /app

# Switch to app user
USER app

# Expose common ports (bot doesn't need exposure; backend uses 8080 behind proxy)
EXPOSE 8080

# Run the bot
CMD ["uv", "run", "python", "main.py"] 