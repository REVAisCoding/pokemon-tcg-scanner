# Pokémon App

App mobile em **Expo (React Native)** para escanear cartas Pokémon, montar coleção e sincronizar na nuvem via **Supabase**. O scan usa **OpenAI Vision** no backend — a chave da OpenAI fica **somente no servidor**, nunca no app.

Este repositório tem duas partes:

| Pasta | O que é |
|-------|---------|
| `pokemon-app/` | App Expo (frontend) |
| `backend/` | API FastAPI de scan de cartas |

---

## Pré-requisitos

Instale antes de começar:

- **Node.js** 18+ e **npm** (ou yarn)
- **Python** 3.11+
- **Git**
- **Expo Go** no celular ([iOS](https://apps.apple.com/app/expo-go/id982107779) · [Android](https://play.google.com/store/apps/details?id=host.exp.exponent))
- Celular e computador na **mesma rede Wi‑Fi** (para rodar com Expo Go)

Contas que você vai precisar criar (com suas próprias credenciais):

| Serviço | Para quê | Onde criar |
|---------|----------|------------|
| **Supabase** | Login e coleção na nuvem | [supabase.com](https://supabase.com) |
| **OpenAI** | Leitura da carta por foto (scan) | [platform.openai.com](https://platform.openai.com) |
| **Pokémon TCG API** *(opcional)* | Mais limite de requisições no fallback de busca | [pokemontcg.io](https://pokemontcg.io/) |

---

## 1. Clonar o repositório

```bash
git clone https://github.com/SEU_USUARIO/PokemonApp.git
cd PokemonApp
```

---

## 2. Configurar o Supabase

O app usa Supabase para autenticação (e-mail) e salvar a coleção.

### 2.1 Criar o projeto

1. Acesse [supabase.com/dashboard](https://supabase.com/dashboard) e crie um projeto.
2. Em **Project Settings → API**, copie:
   - **Project URL** (ex.: `https://abcdefgh.supabase.co`)
   - **anon public** key

### 2.2 Criar a tabela no banco

1. No dashboard: **SQL → New query**
2. Cole e execute o conteúdo de `pokemon-app/supabase/migrations/001_user_cards.sql`

### 2.3 Habilitar login por e-mail

1. **Authentication → Providers → Email**
2. Ative **Enable Email provider**
3. Para testes locais, desative **Confirm email** (opcional, facilita o cadastro)

---

## 3. Configurar o backend

A chave da OpenAI **nunca** vai no app — só em `backend/.env`.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edite `backend/.env` com **suas** credenciais:

```env
# Obrigatório — obtenha em https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-sua-chave-aqui

# Opcional — obtenha em https://pokemontcg.io/
POKEMON_TCG_API_KEY=
```

> A OpenAI exige saldo/créditos na conta. Sem isso, o scan retorna erro de quota.

Suba o servidor (deixe este terminal aberto):

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Confirme que está no ar:

```bash
curl http://localhost:8000/health
```

Resposta esperada:

```json
{"status":"ok","openai_configured":true}
```

Se `openai_configured` for `false`, revise a chave em `.env` e reinicie o uvicorn.

---

## 4. Configurar o app Expo

Volte à pasta raiz e configure o frontend:

```bash
cd ../pokemon-app
npm install
cp .env.example .env
```

Edite `pokemon-app/.env` com **suas** credenciais:

```env
# URL do projeto Supabase (SEM /rest/v1 no final)
EXPO_PUBLIC_SUPABASE_URL=https://seu-projeto.supabase.co
EXPO_PUBLIC_SUPABASE_ANON_KEY=sua-anon-key-aqui

# URL do backend de scan
EXPO_PUBLIC_SCAN_API_URL=http://localhost:8000
```

### URL do backend por ambiente

| Onde roda o app | Valor de `EXPO_PUBLIC_SCAN_API_URL` |
|-----------------|-------------------------------------|
| **Expo Go no celular físico** | `http://localhost:8000` *(recomendado)* — o app detecta o IP da sua máquina automaticamente |
| **Simulador iOS (Mac)** | `http://localhost:8000` |
| **Emulador Android** | `http://10.0.2.2:8000` |
| **IP manual** (se a detecção automática falhar) | `http://192.168.x.x:8000` *(IP local da máquina)* |

Para descobrir seu IP local:

```bash
# macOS
ipconfig getifaddr en0

# Linux
hostname -I | awk '{print $1}'
```

> O backend precisa estar com `--host 0.0.0.0` para aceitar conexões da rede local.

---

## 5. Rodar o app com Expo Go

Com o backend já rodando e o `.env` configurado:

```bash
cd pokemon-app
npx expo start
```

No terminal do Expo:

1. Abra o **Expo Go** no celular.
2. **Android:** toque em **Scan QR code** e leia o QR do terminal.
3. **iOS:** abra a **Câmera**, aponte para o QR e toque no banner do Expo Go.

O app carrega no celular. Na primeira vez, crie uma conta (e-mail + senha) na tela de login.

### Checklist se algo não funcionar

- [ ] Backend rodando (`curl http://localhost:8000/health`)
- [ ] Celular e PC na mesma Wi‑Fi
- [ ] `OPENAI_API_KEY` válida em `backend/.env`
- [ ] `EXPO_PUBLIC_SUPABASE_*` preenchidos em `pokemon-app/.env` (não deixe os placeholders)
- [ ] Migration SQL executada no Supabase
- [ ] Após mudar `.env`, pare o Expo (`Ctrl+C`) e rode `npx expo start` de novo

---

## Estrutura de configuração

```
PokemonApp/
├── backend/
│   ├── .env              ← suas chaves OpenAI (não commitar)
│   ├── .env.example      ← template
│   └── main.py
└── pokemon-app/
    ├── .env              ← Supabase + URL do backend (não commitar)
    ├── .env.example      ← template
    └── supabase/migrations/001_user_cards.sql
```

Os arquivos `.env` estão no `.gitignore`. **Nunca** commite chaves reais.

---

## Variáveis de ambiente

### Backend (`backend/.env`)

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `OPENAI_API_KEY` | Sim | Chave da OpenAI — usada só no servidor |
| `POKEMON_TCG_API_KEY` | Não | Chave opcional da Pokémon TCG API |

### App (`pokemon-app/.env`)

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `EXPO_PUBLIC_SUPABASE_URL` | Sim | URL do projeto Supabase |
| `EXPO_PUBLIC_SUPABASE_ANON_KEY` | Sim | Chave anon pública do Supabase |
| `EXPO_PUBLIC_SCAN_API_URL` | Sim | URL base do backend de scan |

---

## API do backend

Documentação detalhada em [`backend/README.md`](backend/README.md).

| Endpoint | Descrição |
|----------|-----------|
| `GET /health` | Verifica se a API está no ar e se a OpenAI está configurada |
| `POST /scan-card` | Recebe foto da carta (multipart, campo `image`) e retorna candidatos |

Com o backend rodando: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Problemas comuns

**"Supabase não configurado"**  
Você ainda está com os valores de exemplo em `pokemon-app/.env`. Substitua pela URL e anon key do seu projeto.

**Scan falha / "Network request failed"**  
Backend parado, firewall bloqueando a porta 8000, ou celular em outra rede. Teste `curl http://SEU_IP:8000/health` ou use o IP manual no `.env`.

**"OPENAI_API_KEY não configurada"**  
Edite `backend/.env`, coloque uma chave que comece com `sk-` e reinicie o uvicorn.

**"Créditos da OpenAI esgotados"**  
Adicione saldo em [platform.openai.com/settings/organization/billing](https://platform.openai.com/settings/organization/billing).

**Mudou o `.env` e o app não refletiu**  
Pare o Metro (`Ctrl+C`) e rode `npx expo start` novamente. Variáveis `EXPO_PUBLIC_*` são lidas na inicialização.
