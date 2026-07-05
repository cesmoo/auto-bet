# ============================================
# Dockerfile - Multi-stage Build
# ============================================

# Stage 1: Build
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    libfreetype6-dev \
    libpng-dev \
    libjpeg-dev \
    fontconfig \
    fonts-liberation \
    fonts-dejavu-core \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Update font cache
RUN fc-cache -fv

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Run
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libfreetype6 \
    libpng16-16 \
    libjpeg62-turbo \
    fontconfig \
    fonts-liberation \
    fonts-dejavu-core \
    libssl3 \
    libffi8 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -fv || true

# Copy from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application
COPY bot.py .

# Create directories
RUN mkdir -p /app/logs /app/data

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV TZ=Asia/Yangon

# Expose port
EXPOSE 3000

# Run
CMD ["python", "bot.py"]
