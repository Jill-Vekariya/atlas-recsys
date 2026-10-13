CONFIG ?= configs/smoke.yaml

.PHONY: install smoke prepare train evaluate tradeoffs ablations serve demo test lint docker canary load-test
install:
	uv sync --extra dev
smoke:
	uv run atlas smoke --config $(CONFIG)
prepare:
	uv run atlas prepare --config $(CONFIG)
train:
	uv run atlas train --config $(CONFIG)
evaluate:
	uv run atlas evaluate --config $(CONFIG) --split test
tradeoffs:
	uv run atlas tradeoffs --config $(CONFIG)
ablations:
	uv run atlas ablations --config $(CONFIG)
serve:
	uv run atlas serve
demo:
	uv run streamlit run src/atlas/ui.py --browser.gatherUsageStats=false
test:
	uv run pytest -q
lint:
	uv run ruff check src tests scripts
	uv run ruff format --check src tests scripts
docker:
	docker compose up --build -d
canary:
	uv run atlas canary-demo --config $(CONFIG)
load-test:
	uv run atlas load-test --config $(CONFIG) --rate 50 --duration 30
