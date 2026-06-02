# Deploy do backend no Railway (via GitHub)

API FastAPI para scan de cartas Pokémon/Riftbound. Este guia cobre deploy contínuo a partir do repositório GitHub.

## Pré-requisitos

- Conta no [Railway](https://railway.com)
- Repositório GitHub com este projeto (branch `main` ou outra de produção)
- Chave OpenAI (`OPENAI_API_KEY`) — **obrigatória** para `POST /scan-card`

## Estrutura de deploy

Arquivos na pasta `backend/`:

| Arquivo | Função |
|---------|--------|
| `requirements.txt` | Dependências Python |
| `Procfile` | Comando de start (`uvicorn`) |
| `railway.json` | Healthcheck em `/health` e política de restart |
| `.env.example` | Referência das variáveis de ambiente |

## Passo a passo: deploy pelo GitHub

### 1. Enviar o código para o GitHub

Certifique-se de que a pasta `backend/` está commitada e enviada (`git push`) para o repositório remoto.

### 2. Criar projeto no Railway

1. Acesse [railway.com](https://railway.com) e faça login.
2. Clique em **New Project**.
3. Escolha **Deploy from GitHub repo**.
4. Autorize o Railway a acessar sua conta GitHub (se ainda não fez).
5. Selecione o repositório **PokemonApp** (ou o nome do seu repo).

### 3. Configurar o diretório raiz (`backend`)

O monorepo contém app Expo + backend. O Railway precisa buildar só o backend:

1. Abra o **service** criado no Railway.
2. Vá em **Settings**.
3. Em **Root Directory**, defina: `backend`
4. Salve — o Railway fará um novo deploy automaticamente.

### 4. Variáveis de ambiente

No painel do service, abra **Variables** e adicione:

| Variável | Obrigatória | Exemplo / descrição |
|----------|-------------|---------------------|
| `OPENAI_API_KEY` | **Sim** | `sk-proj-...` — [OpenAI API Keys](https://platform.openai.com/api-keys) |
| `POKEMON_TCG_API_KEY` | Não | Chave da [Pokémon TCG API](https://dev.pokemontcg.io/) (aumenta rate limit) |
| `TCGAPI_DEV_KEY` | Não | Chave do [tcgapi.dev](https://tcgapi.dev) — preços Riftbound |
| `CORS_ORIGINS` | Não | Origens permitidas, separadas por vírgula. Padrão: `*` (dev). Em produção web: `https://seu-dominio.com` |

O Railway injeta automaticamente:

| Variável | Descrição |
|----------|-----------|
| `PORT` | Porta HTTP — **não defina manualmente**; o `uvicorn` já usa `$PORT` |

> **Nunca** commite `.env` com chaves reais. Use apenas **Variables** no Railway.

### 5. Gerar URL pública

1. No service, abra **Settings** → **Networking**.
2. Clique em **Generate Domain**.
3. Anote a URL, por exemplo: `https://pokemon-scan-api-production.up.railway.app`

### 6. Verificar o deploy

```bash
# Healthcheck
curl https://SUA-URL.up.railway.app/health

# Resposta esperada:
# {"status":"ok","openai_configured":true,"tcgapi_dev_configured":false}
```

Se `openai_configured` for `false`, confira `OPENAI_API_KEY` nas Variables.

### 7. Conectar o app Expo

No `.env` do app (`pokemon-app/.env`):

```env
EXPO_PUBLIC_SCAN_API_URL=https://SUA-URL.up.railway.app
```

Reinicie o bundler Expo (`npx expo start -c`) após alterar o `.env`.

---

## Endpoints

### `GET /health`

Healthcheck usado pelo Railway. Retorna status da API e se as chaves opcionais estão configuradas.

```bash
curl https://SUA-URL.up.railway.app/health
```

### `POST /scan-card`

Recebe `multipart/form-data`:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `image` | arquivo | Foto da carta (JPEG/PNG/WebP, máx. 10 MB) |
| `game_type` | string | `pokemon` (padrão) ou `riftbound` |

```bash
curl -X POST https://SUA-URL.up.railway.app/scan-card \
  -F "image=@/caminho/para/carta.jpg" \
  -F "game_type=pokemon"
```

Resposta (exemplo):

```json
{
  "confidence": "high",
  "extracted": {
    "name": "Pikachu",
    "nameEnglish": "Pikachu",
    "number": "58",
    "set": "Base Set",
    "language": "English"
  },
  "candidates": [...]
}
```

### `GET /riftbound/price/{tcgplayer_id}`

Consulta preço Riftbound via tcgapi.dev (requer `TCGAPI_DEV_KEY`).

Query params opcionais: `name`, `set_id` — usados como fallback se o ID do TCGPlayer não retornar preço.

### `GET /riftbound/price/by-id/{riftbound_id}`

Resolve o `tcgplayer_id` via Riftcodex e consulta preço no tcgapi.dev. Query params opcionais: `tcgplayer_id`, `name`, `set_id`.

---

## Deploy automático (CI/CD)

Após a configuração inicial, cada **push** na branch conectada dispara um novo deploy no Railway.

Fluxo:

```
git push origin main  →  Railway detecta push  →  pip install  →  uvicorn  →  GET /health OK
```

Para pausar deploys automáticos: **Settings** → desative **Auto Deploy**.

---

## Desenvolvimento local

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edite .env com OPENAI_API_KEY
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Teste local:

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/scan-card -F "image=@carta.jpg"
```

---

## Solução de problemas

| Sintoma | Causa provável | Solução |
|---------|----------------|---------|
| Build falha | Root Directory errado | Defina `backend` em Settings |
| `502` / service unhealthy | App não sobe na `$PORT` | Confirme `startCommand` com `--port $PORT` |
| Health OK mas scan falha | `OPENAI_API_KEY` ausente/inválida | Verifique Variables; `/health` → `openai_configured: true` |
| App não conecta | URL errada no Expo | Use HTTPS da Railway em `EXPO_PUBLIC_SCAN_API_URL` |
| CORS no Expo Web | Origem não listada | Defina `CORS_ORIGINS` com a URL do app web |

Logs em tempo real: aba **Deployments** → deployment ativo → **View Logs**.
