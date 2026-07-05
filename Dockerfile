# ============================================
# Dockerfile for BigWin AutoBet Bot
# ============================================

# Base image with Python 3.11
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# ============================================
# Install system dependencies for matplotlib & aiohttp
# ============================================
RUN apt-get update && apt-get install -y \
    # For matplotlib
    libfreetype6-dev \
    libpng-dev \
    libjpeg-dev \
    # For fonts
    fonts-liberation \
    fonts-dejavu-core \
    # For aiohttp
    libssl-dev \
    libffi-dev \
    # General utilities
    curl \
    wget \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ============================================
# Install matplotlib fonts
# ============================================
RUN fc-cache -fv

# ============================================
# Copy requirements first (for better caching)
# ============================================
COPY requirements.txt .

# ============================================
# Install Python dependencies
# ============================================
RUN pip install --no-cache-dir -r requirements.txt

# ============================================
# Copy application code
# ============================================
COPY bot.py .

# ============================================
# Copy .env file (if exists)
# ============================================
COPY .env .env

# ============================================
# Create directories for logs and data
# ============================================
RUN mkdir -p /app/logs /app/data

# ============================================
# Environment variables
# ============================================
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV TZ=Asia/Yangon

# ============================================
# Expose port (if needed for health check)
# ============================================
EXPOSE 3000

# ============================================
# Health check
# ============================================
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# ============================================
# Run the bot
# ============================================
CMD ["python", "bot.py"]
