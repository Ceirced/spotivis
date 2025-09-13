.PHONY: help dev local prod stop clean setup-dirs

# Default target - show help
help:
	@echo "Flask Application Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  make dev    - Run everything in Docker (development mode)"
	@echo "  make local  - Run only Redis and Celery in Docker (for local Flask development)"
	@echo "  make prod   - Run in production mode"
	@echo "  make stop   - Stop all containers"
	@echo "  make clean  - Stop containers and remove volumes"
	@echo "  make help   - Show this help message"

# Setup required directories
setup-dirs:
	@mkdir -p ./logs/app ./instance

# Development mode - run everything in Docker
dev: setup-dirs
	@echo "Starting Flask server in DEV..."
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build

# Local development - only Redis and Celery in Docker
local: setup-dirs
	@echo "Starting Redis and Celery only for local development..."
	@echo "Redis will be available on localhost:6379"
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build redis celery
	@echo ""
	@echo "Redis and Celery are running. Now start Flask with:"
	@echo "  flask run"

# Production mode
prod: setup-dirs
	@echo "Starting Flask server in PROD..."
	docker compose up -d --build

# Stop all containers
stop:
	@echo "Stopping Flask server..."
	docker compose down

# Clean everything including volumes
clean:
	@echo "Stopping containers and removing volumes..."
	docker compose down -v