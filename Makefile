# Developer entry points. `make check` is the verification gate (definition of done).
.PHONY: install check lint fmt test run-server run-agent

install:        ## Create the venv and install all deps (incl. dev)
	uv sync --extra dev

check: lint test  ## Lint + tests — must pass before any commit/PR

lint:           ## Static checks (ruff)
	uv run ruff check src tests

fmt:            ## Auto-format
	uv run ruff format src tests
	uv run ruff check --fix src tests

test:           ## Run the test suite
	uv run pytest

run-server:     ## Run the MCP weather server over stdio (normally launched by the agent)
	uv run weather-server

run-agent:      ## Run the chat agent (spawns the server as an MCP client)
	uv run weather-agent
