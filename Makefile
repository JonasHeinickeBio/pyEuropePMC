#################################################################################
# GLOBALS                                                                       #
#################################################################################

PROJECT_NAME = pyEuropePMC
PYTHON_VERSION = 3.10
PYTHON_INTERPRETER = python

#################################################################################
# COMMANDS                                                                      #
#################################################################################


## Install Python Dependencies
.PHONY: requirements
requirements:
	$(PYTHON_INTERPRETER) -m pip install -U pip
	$(PYTHON_INTERPRETER) -m pip install -r requirements.txt




## Delete all compiled Python files
.PHONY: clean
clean:
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "__pycache__" -delete

## Lint using ruff
.PHONY: lint
lint:
	ruff check .

## Format source code with ruff
.PHONY: format
format:
	ruff format .

## Lint and format with ruff
.PHONY: ruff
ruff:
	ruff check --fix .
	ruff format .

## Run all quality checks
.PHONY: quality
quality:
	ruff check .
	ruff format --check .
	mypy .
	bandit -r ./src --exclude "tests,.venv,.git,.mypy_cache,.pytest_cache" --skip "B101,B303"

## Run tests
.PHONY: test
test:
	pytest

## Run tests with coverage
.PHONY: test-coverage
test-coverage:
	coverage run -m pytest
	coverage report
	coverage html




## Install pipx
.PHONY: pipx
pipx:
	$(PYTHON_INTERPRETER) -m pip install --user pipx
	$(PYTHON_INTERPRETER) -m pipx ensurepath

## Set up python interpreter environment
.PHONY: create_environment
create_environment: pipx
	pipx install poetry || true
	poetry env use $(PYTHON_INTERPRETER)
	poetry install
	@echo ">>> Poetry virtual environment created. Activate with:\nsource $$(poetry env info --path)/bin/activate"




#################################################################################
# PROJECT RULES                                                                 #
#################################################################################



#################################################################################
# Self Documenting Commands                                                     #
#################################################################################

.DEFAULT_GOAL := help

define PRINT_HELP_PYSCRIPT
import re, sys; \
lines = '\n'.join([line for line in sys.stdin]); \
matches = re.findall(r'\n## (.*)\n[\s\S]+?\n([a-zA-Z_-]+):', lines); \
print('Available rules:\n'); \
print('\n'.join(['{:25}{}'.format(*reversed(match)) for match in matches]))
endef
export PRINT_HELP_PYSCRIPT

help:
	@$(PYTHON_INTERPRETER) -c "${PRINT_HELP_PYSCRIPT}" < $(MAKEFILE_LIST)
