#!/bin/bash

# ============================================
# Startup Script for Docker
# ============================================

echo "🚀 Starting BigWin AutoBet Bot..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "Please create .env file with required variables."
    exit 1
fi

# Check if MongoDB is running (if using local)
if [ -n "$(docker ps -q -f name=mongodb)" ]; then
    echo "✅ MongoDB is running"
else
    echo "⚠️ MongoDB is not running. Starting MongoDB..."
    docker-compose up -d mongodb
    sleep 5
fi

# Build and run the bot
echo "📦 Building Docker image..."
docker-compose build

echo "🚀 Starting bot..."
docker-compose up -d

echo "✅ Bot started successfully!"
echo "📊 Check logs: docker-compose logs -f"
echo "📝 Status: docker-compose ps"
