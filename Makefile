.PHONY: install lint format test evals demo gate

install:
	pip install -r requirements.txt
	pip install -e ".[dev]"

lint:
	python -m ruff check .
	python -m ruff format --check .

format:
	python -m ruff format .

test:
	python -m pytest

evals:
	python -m evals.run_evals
	python -m evals.conversation_evals

demo:
	python -m sim.run_demo

# The full quality gate: style + tests + policy evals + a clean demo run.
# Runs with no API keys (uses the deterministic fallback paths).
gate: lint test evals demo
	@echo "\n✓ quality gate passed"
