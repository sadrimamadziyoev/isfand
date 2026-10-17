.PHONY: install build test up down backup
install:
	python3.12 -m venv .venv
	.venv/bin/pip install --require-hashes -r backend/requirements.lock
	npm ci --prefix frontend
build:
	npm run build --prefix frontend
test:
	./ops/test.sh
up:
	docker compose up -d --build
down:
	docker compose down
backup:
	./ops/backup.sh
