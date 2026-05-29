# Single image that runs the Chainlit web UI; the agent spawns the MCP server
# in-process as a subprocess, so one container runs the whole stack.
FROM python:3.12-slim

# uv for fast, reproducible installs from the committed lock file.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# Install dependencies first (cached layer), then the project.
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

EXPOSE 8000

# Headless so it doesn't try to open a browser inside the container.
CMD ["uv", "run", "--no-dev", "chainlit", "run", "src/weather_agent/ui/web.py", \
     "--host", "0.0.0.0", "--port", "8000", "--headless"]
