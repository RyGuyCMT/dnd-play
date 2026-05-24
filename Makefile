.PHONY: help build up down logs shell

help:
	@echo "D&D Play — Makefile"
	@echo "  make build   — build Docker image"
	@echo "  make up      — start server (background)"
	@echo "  make down    — stop server"
	@echo "  make logs    — tail logs"
	@echo "  make shell   — shell into running container"

build:
	docker compose build

up:
	docker compose up -d
	@echo "Server running at http://localhost:8000"

down:
	docker compose down

logs:
	docker compose logs -f

shell:
	docker compose exec dnd-server /bin/bash