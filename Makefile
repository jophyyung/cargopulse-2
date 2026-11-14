PYTHONPATH := packages/contracts/python:services/api:services/worker:.
export PYTHONPATH
UV ?= uv

.PHONY: install contracts test api worker web migrate
install:
	$(UV) sync --frozen
	npm ci
contracts:
	$(UV) run python scripts/export_contracts.py --runtime
	npm run contracts
test:
	$(UV) run pytest
api:
	$(UV) run uvicorn cargopulse_api.main:app --host 127.0.0.1 --port 8000
worker:
	$(UV) run python -m cargopulse_api.worker
web:
	npm run dev
migrate:
	$(UV) run alembic -c services/api/alembic.ini upgrade head
