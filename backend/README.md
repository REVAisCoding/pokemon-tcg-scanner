# Backend de scan de cartas Pokémon

API FastAPI que recebe a foto da carta, usa OpenAI Vision para extrair dados e busca candidatos na Pokémon TCG API.

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edite .env e adicione OPENAI_API_KEY
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Endpoint

### `POST /scan-card`

Multipart form com campo `image`.

Resposta:

```json
{
  "confidence": "high",
  "extracted": {
    "name": "Pikachu",
    "number": "58",
    "set": "Base Set",
    "language": "English"
  },
  "candidates": [
    {
      "id": "base1-58",
      "name": "Pikachu",
      "setName": "Base",
      "number": "#58/102",
      "type": "Lightning",
      "imageUrl": "https://...",
      "accentColor": "#F7D046"
    }
  ]
}
```

## Variáveis de ambiente

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `OPENAI_API_KEY` | Sim | Chave da OpenAI (somente no servidor) |
| `POKEMON_TCG_API_KEY` | Não | Chave opcional da Pokémon TCG API |

## Conectar o app Expo

No `.env` do app:

```
EXPO_PUBLIC_SCAN_API_URL=http://SEU_IP:8000
```

- **Simulador iOS**: `http://localhost:8000`
- **Emulador Android**: `http://10.0.2.2:8000`
- **Dispositivo físico**: use o IP da máquina na rede local (ex.: `http://192.168.1.10:8000`)
