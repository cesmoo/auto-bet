# ============================================
# Makefile for Docker Management
# ============================================

.PHONY: help build run stop logs clean shell restart

help:
	@echo "Available commands:"
	@echo "  make build    - Build Docker image"
	@echo "  make run      - Run container in background"
	@echo "  make stop     - Stop container"
	@echo "  make restart  - Restart container"
	@echo "  make logs     - View logs"
	@echo "  make shell    - Enter container shell"
	@echo "  make clean    - Remove containers and images"

build:
	docker build -t bigwin-bot .

run:
	docker-compose up -d

stop:
	docker-compose down

restart:
	docker-compose restart

logs:
	docker-compose logs -f

shell:
	docker exec -it bigwin-auto-bet-bot /bin/bash

clean:
	docker-compose down -v
	docker rmi bigwin-bot || true
	rm -rf logs/ data/ mongo_data/

# ============================================
# Development Commands
# ============================================

dev:
	docker-compose up

test:
	docker-compose run --rm bigwin-bot python -c "import sys; print('Python version:', sys.version)"

rebuild:
	docker-compose down -v
	docker-compose build --no-cache
	docker-compose up -d
