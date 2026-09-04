.PHONY: install db migrate run test
install:
	python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
db:
	docker compose up -d db
migrate:
	.venv/bin/alembic upgrade head
run:
	.venv/bin/uvicorn app.main:app --reload
test:
	.venv/bin/pytest
