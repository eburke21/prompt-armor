FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first for better layer caching
COPY pyproject.toml ./

# Install dependencies (no dev deps in production)
RUN uv sync --no-dev --no-install-project

# Copy application code
COPY promptarmor/ promptarmor/

# Create data directory
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "promptarmor.main:app", "--host", "0.0.0.0", "--port", "8000"]
