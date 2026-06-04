.PHONY: up down logs ps reset tools test verify

# One-command startup
up:
	docker compose up --build -d
	@echo ""
	@echo "  Frontend  →  http://localhost:3000"
	@echo "  API       →  http://localhost:8000/docs"
	@echo "  Postgres  →  localhost:5432"
	@echo "  Redis     →  localhost:6379"

# Graceful stop (keep volumes)
down:
	docker compose down

# Tail all logs
logs:
	docker compose logs -f

# Container status
ps:
	docker compose ps

# Nuclear reset — destroys all data volumes
reset:
	docker compose down -v --remove-orphans
	docker compose up --build -d

# Start with dev tools (pgAdmin + Redis Commander)
tools:
	docker compose --profile tools up --build -d
	@echo ""
	@echo "  pgAdmin          →  http://localhost:5050"
	@echo "  Redis Commander  →  http://localhost:8081"

# Run API unit tests (outside Docker)
test:
	cd services/api && pytest

# Seed store layout (cameras + zones) directly into running postgres
seed-layout:
	python scripts/parse_layout.py --db-url postgresql+asyncpg://postgres:postgres@localhost:5432/store_intelligence

# Seed POS CSV transaction data as events
seed-csv:
	python scripts/seed_from_csv.py --db-url postgresql+asyncpg://postgres:postgres@localhost:5432/store_intelligence

# Seed synthetic demo data (fast — no CV required)
seed-demo:
	python scripts/seed_demo.py --db-url postgresql+asyncpg://postgres:postgres@localhost:5432/store_intelligence

# Acceptance gate self-check — mirrors reviewer validation steps
verify:
	@echo "── Health ──────────────────────────────────────────────────"
	curl -sf http://localhost:8000/health | python -m json.tool
	@echo "── Metrics (Prometheus) ────────────────────────────────────"
	curl -sf http://localhost:8000/metrics | head -20
	@echo "── Events (must return items[]) ────────────────────────────"
	curl -sf "http://localhost:8000/api/v1/events?limit=5" | python -m json.tool
	@echo "── Funnel (must show drop-off) ─────────────────────────────"
	curl -sf http://localhost:8000/api/v1/funnel | python -m json.tool
	@echo "── Anomalies ───────────────────────────────────────────────"
	curl -sf http://localhost:8000/api/v1/anomalies | python -m json.tool
	@echo "── Store Metrics Summary ───────────────────────────────────"
	curl -sf http://localhost:8000/api/v1/store-metrics/summary | python -m json.tool

# Full demo: bring up stack + seed demo data
demo: up
	@echo "Waiting for API to be healthy..."
	@sleep 15
	$(MAKE) seed-layout
	$(MAKE) seed-demo
	@echo "Demo ready → http://localhost:3000"
