ARGS ?=

.PHONY: setup cewl fab test build clean

setup:
	uv sync

cewl:
	uv run pycewl $(ARGS)

fab:
	uv run fab $(ARGS)

test:
	uv run pytest

build:
	uv build

clean:
	rm -rf .pytest_cache build dist src/pycewl.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f -name '*.py[co]' -delete
