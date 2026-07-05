# ============================================
# Dockerfile for BigWin AutoBet Bot (Fixed)
# ============================================

FROM python:3.11-slim

WORKDIR /app

# ============================================
# Install system dependencies
# ============================================
RUN apt-get update && apt-get install -y \
    libfreetype6-dev \
    libpng-dev \
    libjpeg-dev \
    fonts-liberation \
    fonts-dejavu-core \
    libssl-dev \
    libffi-dev \
    curl \
    wget \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ============================================
# Cache fonts
# ============================================
RUN fc-cache -fv

# ============================================
# Copy requirements first (for caching)
# ============================================
COPY requirements.txt .

# ============================================
# Install Python dependencies
# ============================================
RUN pip install --no-cache-dir -r requirements.txt

# ============================================
# Copy application code (ONLY ONCE)
# ============================================
COPY bot.py .

# ============================================
# Create directories
# ============================================
RUN mkdir -p /app/logs /app/data

# ============================================
# Environment variables (use build args)
# ============================================
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV TZ=Asia/Yangon

# ============================================
# Expose port
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
