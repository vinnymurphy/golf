# JobSearch Project Automation
VENV = venv
BIN = $(VENV)/bin
PYTHON = $(BIN)/python3
MANAGE = $(PYTHON) manage.py
BACKUP_DIR = backups
TIMESTAMP = $(shell date +%F_%H%M%S)


.PHONY: help setup install migrate run test shell clean

help:
	@echo "Available commands:"
	@echo "  make setup    - Create venv and install dependencies"
	@echo "  make migrate  - Generate and apply database migrations"
	@echo "  make run      - Start the Django development server"
	@echo "  make test     - Run the test suite (Performance & Logic)"
	@echo "  make shell    - Open the Django interactive shell"
	@echo "  make backup   - Export database to timestamped JSON"
	@echo "  make restore  - Load data from the most recent backup file"
	@echo "  make format   - run ruff check --fix on the code base
	@echo "  make lint     - run ruff check on the code base
	@echo "  make check    - Safety Suite where we run format, test, backup
	@echo "  make clean    - Remove __pycache__ and build artifacts"

setup:
	@echo "[INFO] Initializing Virtual Environment..."
	python3 -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements.txt
	@echo "[SUCCESS] Environment ready. Run 'make migrate' next."

migrate:
	$(MANAGE) makemigrations
	$(MANAGE) migrate

run:
	$(MANAGE) runserver

test:
	$(MANAGE) test -v 2 jobs

shell:
	$(MANAGE) shell

clean:
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -delete

backup:
	@mkdir -p $(BACKUP_DIR)
	@echo "----------------------------------------------------------------"
	@echo "BUILD STATUS: Exporting JobSearch data..."
	@echo "TARGET: $(BACKUP_DIR)/db_backup_$(TIMESTAMP).json"
	@$(MANAGE) dumpdata --indent 2 --exclude auth.permission --exclude contenttypes > $(BACKUP_DIR)/db_backup_$(TIMESTAMP).json
	@echo "RESULT: Backup completed successfully at $(shell date)."
	@echo "----------------------------------------------------------------"

restore:
	@echo "----------------------------------------------------------------"
	@echo "BUILD STATUS: Restoring latest data state..."
	@$(MANAGE) loaddata $(shell ls -t $(BACKUP_DIR)/*.json | head -1)
	@echo "RESULT: Database synchronized with $(shell ls -t $(BACKUP_DIR)/*.json | head -1)"
	@echo "----------------------------------------------------------------"

.PHONY: help install migrate run test shell clean backup restore format lint

# ... (keep existing targets) ...

format:
	@echo "----------------------------------------------------------------"
	@echo "BUILD STATUS: Formatting with Ruff..."
	@ruff format .
	@ruff check --fix .
	@echo "RESULT: Codebase formatted and auto-fixed."
	@echo "----------------------------------------------------------------"

lint:
	@echo "----------------------------------------------------------------"
	@echo "BUILD STATUS: Linting with Ruff..."
	@ruff check .
	@echo "RESULT: Linting complete."
	@echo "----------------------------------------------------------------"

# The "Safety Suite" - Run everything in one go
check: format test backup
	@echo "----------------------------------------------------------------"
	@echo "PIPELINE STATUS: ALL CHECKS PASSED"
	@echo "----------------------------------------------------------------"
