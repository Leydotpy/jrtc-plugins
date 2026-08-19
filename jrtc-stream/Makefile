PYTHON ?= python

.PHONY: verify lint format format-check boundaries test typecheck compile build artifacts clean

verify: lint boundaries test typecheck compile artifacts

lint:
	ruff check .

format:
	ruff format .

format-check:
	ruff format --check .

boundaries:
	$(PYTHON) scripts/check_boundaries.py

test:
	$(PYTHON) scripts/run_tests.py

typecheck:
	mypy projects/stream-orchestrator/src \
		projects/stream-orchestrator-process/src \
		projects/stream-orchestrator-ffmpeg/src \
		projects/stream-orchestrator-gstreamer/src \
		projects/stream-orchestrator-srs/src \
		projects/stream-orchestrator-qt/src

compile:
	$(PYTHON) -m compileall -q projects scripts examples

build:
	$(PYTHON) scripts/build_all.py

artifacts: build
	$(PYTHON) scripts/verify_artifacts.py
	$(PYTHON) scripts/generate_release_metadata.py

clean:
	rm -rf dist build .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name '*.egg-info' -prune -exec rm -rf {} +
