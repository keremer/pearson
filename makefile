.PHONY: test test-unit test-integration test-functional coverage clean help

# Development
install:
	pip install -r requirements.txt
	pip install -r requirements-test.txt

# Testing
test: ## Run all tests
	pytest -v

test-unit: ## Run only unit tests
	pytest tests/unit/ -v

test-integration: ## Run only integration tests
	pytest tests/integration/ -v

test-functional: ## Run only functional tests
	pytest tests/functional/ -v

coverage: ## Run tests with coverage report
	pytest --cov=./ --cov-report=html --cov-report=term-missing
	@echo "Coverage report generated at htmlcov/index.html"

# Code Quality
lint: ## Run code linters
	flake8 .
	black --check .
	isort --check-only .

format: ## Format code automatically
	black .
	isort .

# Database
db-migrate: ## Create database migration
	alembic revision --autogenerate -m "$(message)"

db-upgrade: ## Apply database migrations
	alembic upgrade head

db-downgrade: ## Rollback database migrations
	alembic downgrade -1

# Cleanup
clean: ## Clean up temporary files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .coverage coverage.xml htmlcov/ .pytest_cache/
	rm -rf instance/

# Help
help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'