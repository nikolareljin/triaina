# triaina developer shortcuts. `make help` lists targets.
VENV   ?= .venv
PY     := $(VENV)/bin/python
SRC    := scripts tests
TAG    ?= $(shell git describe --tags --always 2>/dev/null || echo dev)
DIST   := dist/triaina-$(TAG)

.PHONY: help install test lint format clean dist docs docs-serve

help: ## list targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-11s %s\n", $$1, $$2}'

$(PY):
	python3 -m venv $(VENV)

install: $(PY) ## create .venv and install requirements
	$(PY) -m pip install --quiet --upgrade pip
	$(PY) -m pip install --quiet -r requirements.txt

test: ## run pytest
	$(PY) -m pytest

lint: ## black --check, flake8, bash -n
	$(PY) -m black --check $(SRC)
	$(PY) -m flake8 $(SRC)
	bash -n scripts/setup_pi.sh

format: ## apply black
	$(PY) -m black $(SRC)

docs: ## build the docs site into site/
	$(PY) -m pip install --quiet -r requirements-docs.txt
	$(PY) -m mkdocs build --strict

docs-serve: ## preview docs on http://127.0.0.1:8000
	$(PY) -m pip install --quiet -r requirements-docs.txt
	$(PY) -m mkdocs serve

dist: ## build dist/triaina-<tag>.tar.gz
	rm -rf $(DIST) $(DIST).tar.gz
	mkdir -p $(DIST)/scripts
	cp -r config assets README.md LICENSE CHANGELOG.md requirements.txt $(DIST)/
	cp scripts/*.py scripts/*.sh $(DIST)/scripts/
	@if [ -f scripts/script-helpers/helpers.sh ]; then \
		mkdir -p $(DIST)/scripts/script-helpers && \
		cp -r scripts/script-helpers/helpers.sh scripts/script-helpers/lib scripts/script-helpers/LICENSE \
			$(DIST)/scripts/script-helpers/; \
	fi
	tar -C dist -czf $(DIST).tar.gz triaina-$(TAG)
	@echo "built $(DIST).tar.gz"

clean: ## remove build, cache and venv
	rm -rf dist site .pytest_cache $(VENV)
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
