# Madara — Ad Video Pipeline

<img width="1672" height="941" alt="Madara-Video-Agent" src="https://github.com/user-attachments/assets/128eb43e-61b2-4eda-9712-0e3644088e2a" />

Pipeline de automação que transforma URLs de anúncios em vídeos publicitários gerados por IA, com entrega via Telegram.

O usuário envia uma URL de produto → o sistema faz scraping → extrai dados semânticos → gera um roteiro → monta um comercial de 30 segundos em formato vertical (9:16).

---

## Como funciona

```
Você envia uma URL via Telegram
       │
       ▼
┌──────────────────┐
│ Scraping Layer   │  Chromium stealth — extrai texto, título e imagens
└────────┬─────────┘
         ▼
┌──────────────────────────┐
│ Semantic Processing      │  LLM (OpenRouter/Gemini) — dados estruturados
│ (extração de produto)    │  nome, preço, specs, USP, público-alvo, tom
└────────┬─────────────────┘
         ▼
┌───────────────────────┐
│ Prompt Generation     │  LLM (OpenRouter/Claude) — roteiro com 6 cenas
│ (roteiro publicitário)│  cada cena: locução, prompt visual, overlay
└────────┬──────────────┘
         ▼
┌─────────────────────┐
│ Aprovação do usuário │  Roteiro enviado ao Telegram com botões
│ (pausa no pipeline)  │  ✅ Aprovar  ✏️ Ajustar
└────────┬─────────────┘
         ▼
┌──────────────────────────────────────────────┐
│ Video Generation Layer (Muapi.ai)            │  Gera até 9 clipes de 5s
│ + OpenGenerativeAI (bypass HiggsField)        │  usando imagens do produto
└────────┬─────────────────────────────────────┘
         ▼
┌─────────────────────┐
│ Montagem (FFmpeg)   │  Concatenação das cenas → .mp4 final
└────────┬────────────┘
         ▼
   Vídeo enviado ao Telegram
```

---

## Arquitetura do código

```
projeto/
├── .env.example              ← template de variáveis (nunca commitar .env real)
├── .gitignore
├── requirements.txt
├── madara_bot.service        ← systemd unit para deploy em VPS
│
├── core/
│   └── orchestrator.py      ← controlador central do pipeline
│
├── services/
│   ├── gateway/
│   │   └── telegram_bot.py  ← gateway Telegram (recebe URLs, envia vídeos)
│   ├── scraper/
│   │   └── engine.py         ← scraping via Chromium stealth (scrapling)
│   ├── semantic/
│   │   └── processor.py      ← extração de dados estruturados via LLM
│   ├── marketing/
│   │   └── organizer.py      ← geração e refinamento de roteiros
│   └── video/
│       └── generator.py      ← geração de clipes via Muapi + stitching FFmpeg
│
└── shared/
    ├── database/
    │   ├── client.py         ← client Supabase
    │   ├── schema.sql       ← schema do banco
    │   └── migrations/      ← migrations incrementais
    └── models/
        └── schemas.py       ← modelos Pydantic e enums de status
```

---

## Pré-requisitos

- Python 3.10+
- Ubuntu 22.04 (VPS)
- Chromium (para Playwright)
- FFmpeg
- Conta Supabase (PostgreSQL + Storage)
- Bot Telegram (via @BotFather)
- Chave OpenRouter
- Chave Muapi.ai

---

## Instalação

### 1. Clonar e criar ambiente

```bash
git clone <repo-url> projeto-itamar
cd projeto-itamar
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Instalar browsers do Playwright

```bash
playwright install chromium
```

### 3. Configurar variáveis de ambiente

```bash
cp .env.example .env
# edite o .env com suas chaves reais
```

### 4. Preparar o banco de dados

```bash
# Execute o schema no Supabase (Project > SQL Editor)
psql "$SUPABASE_DATABASE_URL" -f shared/database/schema.sql
```

### 5. Iniciar o bot

```bash
# Modo manual:
source .venv/bin/activate
python services/gateway/telegram_bot.py

# Modo systemd (VPS):
sudo cp madara_bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable madara_bot
sudo systemctl start madara_bot
```

---

## Variáveis de ambiente

| Variável | Descrição |
|---|---|
| `SUPABASE_URL` | URL do projeto Supabase |
| `SUPABASE_KEY` | Chave anon ou service role do Supabase |
| `TELEGRAM_BOT_TOKEN` | Token do bot (via @BotFather) |
| `AUTHORIZED_USER_ID` | Seu ID do Telegram (para restringir acesso) |
| `OPENROUTER_API_KEY` | Chave OpenRouter |
| `OPENROUTER_MODEL` | Modelo para extração semântica (padrão: `google/gemini-2.0-flash-lite-001`) |
| `MUAPI_KEY` | Chave Muapi.ai |

---

## Ferramentas externas

### OpenGenerativeAI

Para contornar as limitações de assinatura da plataforma de geração de vídeo（como HiggsField）， o pipeline pode se integrar ao [OpenGenerativeAI](https://github.com/your-user/OpenGenerativeAI) — uma ferramenta de código aberto que oferece funcionalidades equivalentes sem dependence de assinaturas proprietárias.

Consulte o repositório do OpenGenerativeAI para instruções de configuração e uso.

---

## Seleção de modelos por estágio

| Estágio | Modelo usado | Justificativa |
|---|---|---|
| Scraping | scrapling (Chromium) | Renderização JS, anti-detecção |
| Extração semântica | Gemini Flash lite | Baixo custo, tarefa estruturada |
| Geração de roteiro | Claude Sonnet 4 | Raciocínio criativo, estrutura JSON |
| Feedback/refino | Claude Sonnet 4 | Consistência com geração |

---

## Fluxo de aprovação

O pipeline para após gerar o roteiro para que o usuário possa aprovar ou ajustar antes da geração de vídeo.

- **Aprovar**: o vídeo é gerado automaticamente
- **Ajustar**: o usuário envia feedback textual e o roteiro é refinado com base nele

---

## Regeneração parcial

Se o usuário pedir ajuste após o vídeo estar pronto, o sistema reutiliza:

- ✅ dados de scraping
- ✅ imagens filtradas
- ✅ contexto semântico

E refaz apenas:

- ❌ roteiro
- ❌ geração de clipes
- ❌ montagem final

---

## Resultados

<img width="1177" height="926" alt="print-ad-video" src="https://github.com/user-attachments/assets/08e038cc-b45a-49be-92b8-db71d5473980" />


## Segurança

- O bot Telegram responde **exclusivamente** ao `AUTHORIZED_USER_ID` configurado
- Todos os callbacks inline são revalidados contra o mesmo ID
- Credentials via `.env` — nunca em código
- `.env` está no `.gitignore`

---

## License

MIT
