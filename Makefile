# Comandos rápidos — Pokémon App
# Uso: make help

BACKEND_DIR := backend
APP_DIR     := pokemon-app
VENV        := $(BACKEND_DIR)/.venv
PIP         := $(VENV)/bin/pip
UVICORN     := $(VENV)/bin/uvicorn
PORT        := 8000

.PHONY: help init init-backend init-web backend web dev health install

.DEFAULT_GOAL := help

help: ## Lista comandos disponíveis
	@echo "Pokémon App — comandos:"
	@echo ""
	@grep -E '^[a-zA-Z0-9_-]+:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Fluxo típico:"
	@echo "  make init          # primeira vez (deps + .env)"
	@echo "  make backend       # terminal 1 — API FastAPI"
	@echo "  make web           # terminal 2 — Expo no navegador"

# --- Setup ---

init: init-backend init-web ## Instala dependências do backend e do app (web)

init-backend: ## venv Python, pip install e .env do backend
	@echo "→ Backend: criando venv e instalando deps..."
	@test -d $(VENV) || python3 -m venv $(VENV)
	$(PIP) install -q -r $(BACKEND_DIR)/requirements.txt
	@if [ ! -f $(BACKEND_DIR)/.env ]; then \
		cp $(BACKEND_DIR)/.env.example $(BACKEND_DIR)/.env; \
		echo "  Criado $(BACKEND_DIR)/.env — edite OPENAI_API_KEY e TCGAPI_DEV_KEY (preços Riftbound)"; \
	else \
		echo "  $(BACKEND_DIR)/.env já existe"; \
	fi
	@echo "✓ Backend pronto"

init-web: ## npm install e .env do app Expo
	@echo "→ App: instalando dependências..."
	cd $(APP_DIR) && npm install
	@if [ ! -f $(APP_DIR)/.env ]; then \
		cp $(APP_DIR)/.env.example $(APP_DIR)/.env; \
		echo "  Criado $(APP_DIR)/.env — edite Supabase e SCAN_API_URL"; \
	else \
		echo "  $(APP_DIR)/.env já existe"; \
	fi
	@echo "✓ App pronto"

install: init ## Alias para make init

# --- Run ---

backend: ## Sobe API (uvicorn :8000, reload, 0.0.0.0)
	@test -d $(VENV) || (echo "Rode primeiro: make init-backend" && exit 1)
	cd $(BACKEND_DIR) && $(if $(wildcard $(UVICORN)),$(UVICORN),python3 -m uvicorn) main:app --reload --host 0.0.0.0 --port $(PORT)

web: ## Sobe Expo no navegador (expo start --web)
	@test -d $(APP_DIR)/node_modules || (echo "Rode primeiro: make init-web" && exit 1)
	cd $(APP_DIR) && npm run web

dev: ## Sobe backend em background e web no foreground
	@test -d $(VENV) || (echo "Rode primeiro: make init" && exit 1)
	@test -d $(APP_DIR)/node_modules || (echo "Rode primeiro: make init" && exit 1)
	@echo "→ Backend em http://localhost:$(PORT) (background)"
	@cd $(BACKEND_DIR) && $(if $(wildcard $(UVICORN)),$(UVICORN),python3 -m uvicorn) main:app --reload --host 0.0.0.0 --port $(PORT) & \
	BACKEND_PID=$$!; \
	trap 'kill $$BACKEND_PID 2>/dev/null' EXIT INT TERM; \
	echo "→ App web (Ctrl+C encerra backend e Expo)"; \
	cd $(APP_DIR) && npm run web

health: ## Testa GET /health do backend
	@curl -sf http://localhost:$(PORT)/health | python3 -m json.tool || \
		(echo "Backend não responde em :$(PORT) — rode: make backend" && exit 1)
