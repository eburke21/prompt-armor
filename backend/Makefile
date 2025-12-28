.PHONY: lint format typecheck test dev

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy promptarmor

test:
	uv run pytest

dev:
	uv run uvicorn promptarmor.main:app --reload --port 8000
