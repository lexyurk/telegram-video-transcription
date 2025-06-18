FROM python:3.11-slim

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

# Expose port (if needed for health checks)
EXPOSE 8000

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
RUN chown -R app:app /app
USER app

# Run the bot
CMD ["uv", "run", "python", "main.py"] 