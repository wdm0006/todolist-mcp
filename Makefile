.PHONY: install lint lint-check format format-check test test-cov mutate clean

VENV_DIR = .venv
UV = uv

install:
	$(UV) venv $(VENV_DIR) --seed
	$(UV) pip install -e ".[dev,web]"

lint: install
	$(UV) run ruff check --fix .

lint-check: install
	$(UV) run ruff check .

format: install
	$(UV) run ruff format .

format-check: install
	$(UV) run ruff format --check .

test: install
	$(UV) run pytest tests/

test-cov: install
	$(UV) run pytest tests/ --cov --cov-fail-under=89 --cov-report=term-missing

# Full mutation campaign over todo_mcp.py (see docs/mutation-waivers.md for
# scope, waiver classifications, and how to read the results). Takes ~40 min.
mutate: install
	$(UV) run mutmut run

clean:
	rm -rf $(VENV_DIR)
	find . -type f -name '*.py[co]' -delete
	find . -type d -name '__pycache__' -exec rm -rf {} +
