.PHONY: install run test lint clean

install:
	pip install -r requirements-dev.txt && pip install -e .

run:
	python -m menuiq.pipeline

test:
	pytest --cov=src --cov-report=term-missing

lint:
	ruff check src tests

clean:
	rm -rf data/menuiq.db .pytest_cache .coverage
