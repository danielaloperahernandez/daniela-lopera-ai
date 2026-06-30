# Project 5 — Ecommerce Swarm (LangGraph + WhatsApp)

> Multi-agent customer service for a Shopify store over WhatsApp Business.
> LangGraph orchestrates specialized agents with Gemini 1.5 Pro, ChromaDB RAG,
> and production-grade security (signature validation, rate limits, idempotency).

## The problem it solves

E-commerce support mixes repetitive questions (shipping policy, product search) with
sensitive operations (order lookup, refunds) that must verify customer identity.
A single prompt can't handle all of this safely. This system routes each message to a
specialized agent with the right Shopify tools, validates the answer, and escalates
to a human when confidence drops.

## Architecture

```mermaid
flowchart TD
  wa[WhatsApp Cloud API] -->|webhook POST| api[FastAPI main.py]
  api --> redis[(Redis sessions)]
  api --> graph[LangGraph StateGraph]
  graph --> cls[classify_intent]
  cls -->|rag| rag[rag_node + ChromaDB]
  cls -->|ventas| sales[sales_node + Shopify products]
  cls -->|pedidos| orders[orders_node + Shopify orders]
  cls -->|clientes| cust[customers_node]
  cls -->|saludo| hi[saludo_directo]
  cls -->|escalada| esc[escalation_node]
  orders -->|devolución| ref[refunds_node]
  rag --> val[response_validator]
  sales --> val
  orders --> val
  ref --> val
  cust --> val
  val -->|OK| fmt[format_response]
  val -->|retry| cls
  val -->|attempts >= 2| esc
  hi --> fmt
  esc --> fmt
  fmt --> wa
```

## Why Admin API REST (not Storefront)

| API | Access | Use case |
|-----|--------|----------|
| **Admin API REST** | Private token, read + write | Orders, customers, refunds — **this project** |
| Storefront API | Public/read-only | Catalog browsing, headless storefront |

We need order data and refund creation, so **Admin API REST with a Custom App** is the
only viable choice. See [`config.py`](config.py) for the inline explanation and scopes.

## Configure Shopify Admin API token (step by step)

1. Log in to your **Shopify development store** admin panel.
2. Go to **Settings → Apps and sales channels → Develop apps**.
   - If prompted, click **Allow custom app development**.
3. Click **Create an app** → name it e.g. `WhatsApp Support Bot`.
4. Open **Configuration → Admin API integration → Configure**.
5. Enable these scopes:
   - `read_products`
   - `read_orders`
   - `read_customers`
   - `write_orders` (required for refunds)
6. Click **Save**, then **Install app**.
7. Copy the **Admin API access token** (`shpat_...`) — shown only once.
8. Add to `.env`:
   ```env
   SHOPIFY_STORE_URL=your-dev-store.myshopify.com
   SHOPIFY_ACCESS_TOKEN=shpat_xxxxxxxxxxxxxxxx
   ```

## Run locally

```bash
cd projects/05-ecommerce-swarm

# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Fill in GEMINI_API_KEY, Shopify, WhatsApp, Redis credentials

# 3. Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# 4. Ingest knowledge base into ChromaDB
python -m ingest.load_docs

# 5. Start the API
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### WhatsApp webhook setup

1. Create a Meta app with **WhatsApp Business** product.
2. Get `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`, and `WHATSAPP_APP_SECRET`.
3. Set webhook URL: `https://your-domain/webhook`
4. Set verify token to match `WHATSAPP_VERIFY_TOKEN` in `.env`.
5. Subscribe to `messages` field.

For local dev, use [ngrok](https://ngrok.com): `ngrok http 8000`.

### Test the graph locally (no WhatsApp)

```bash
python test_graph.py
```

Runs 6 scripted conversations with mocked Redis, Shopify, ChromaDB and a deterministic LLM.
Use `USE_REAL_LLM=1` to test with real Gemini (requires `GEMINI_API_KEY` and aligned package versions).

### Evaluation harness (routing, tools, LLM-as-judge)

```bash
pip install -r requirements.txt
python eval/run_eval.py --report          # 30 casos + reporte HTML
python eval/run_eval.py --quick             # 10 casos (CI rápido)
python eval/run_eval.py --category rag      # filtrar por categoría
python eval/run_eval.py --quick --report --ci   # gates CI en local
```

Métricas: routing accuracy, tool precision, judge score (Gemini), hallucination rate, latency P95.
Trazas offline en `eval/traces/`; LangSmith opcional con `LANGSMITH_API_KEY`.

## Evaluación

Sistema de evaluación automatizada en `eval/` con mejora continua: dataset curado + casos auto-generados desde producción, historial de runs y CI en cada PR.

### Ejecutar evaluación

| Comando | Descripción |
|---------|-------------|
| `python eval/run_eval.py --report` | 30 casos curados + reporte HTML |
| `python eval/run_eval.py --quick` | 10 casos representativos (~2 min) |
| `python eval/run_eval.py --category rag` | Solo una categoría |
| `python eval/run_eval.py --quick --report --ci` | Modo CI con umbrales estrictos |

### Interpretar el reporte HTML

El reporte se genera en `eval/reports/eval_report_<timestamp>.html` e incluye:

1. **Resumen de métricas** — tarjetas con semáforo verde/amarillo/rojo según umbral.
2. **Gráfico de barras** — routing accuracy por categoría (rag, ventas, pedidos…).
3. **Radar** — vista holística de las 6 dimensiones (routing, tools, judge, resolution, alucinación, latencia).
4. **Tabla de casos** — cada fila muestra pass/fail de routing, score de tools, judge score, tasa de alucinación y latencia.
5. **Fallos destacados** — casos donde el judge LLM puntúa bajo 7/10 con criterio y respuesta generada.

Abre el HTML en el navegador tras `--report`. En CI el artifact `eval-report` contiene la última versión.

### Umbrales de aprobación

| Métrica | Umbral PASS | Umbral CI (PR) |
|---------|-------------|----------------|
| Routing accuracy | ≥ 85% | ≥ 85% (bloquea merge) |
| Tool precision | ≥ 80% | informativo |
| Avg judge score | ≥ 7.0 / 10 | ≥ 7.0 (bloquea merge) |
| Hallucination rate | ≤ 5% | informativo |
| Resolution rate | ≥ 85% | informativo |
| Latency P95 | — | informativo |

El workflow `.github/workflows/eval.yml` ejecuta `--quick --report --ci` en cada PR que toque `projects/05-ecommerce-swarm/` y falla si routing o judge quedan bajo umbral.

### Agregar casos manualmente al dataset

1. Edita `eval/dataset.jsonl` — un objeto JSON por línea.
2. Usa IDs únicos (`tc_031`, `tc_032`…). No reutilices IDs existentes.
3. Estructura mínima:

```json
{
  "id": "tc_031",
  "description": "Resumen del escenario",
  "conversation": [{"role": "user", "content": "Mensaje del usuario"}],
  "expected": {
    "node": "rag_node",
    "tools_called": ["search_knowledge_base"],
    "tool_params": {"query": "envío"},
    "response_must_contain": ["Pasto"],
    "response_must_not_contain": [],
    "judge_criteria": "Qué debe cumplir la respuesta"
  },
  "category": "rag",
  "difficulty": "medium"
}
```

4. Para incluir un caso en el smoke test rápido, añade su ID a `QUICK_IDS` en `eval/dataset_builder.py`.
5. Regenerar solo los 30 casos curados (sin borrar auto-generados): `python -m eval.dataset_builder --seed`.

### Mejora continua — casos desde producción

El script `eval/dataset_builder.py` amplía el dataset con conversaciones reales de Redis:

```bash
# Requiere REDIS_URL y GEMINI_API_KEY
python -m eval.dataset_builder --from-redis
```

- Lee sesiones `session:*` de Redis.
- Por cada **50 conversaciones nuevas** genera **5 casos** con Gemini.
- Los appendea a `dataset.jsonl` con `"auto_generated": true` para revisión humana antes de confiar en ellos en CI.
- Estado de progreso en `eval/.generation_state.json`.

### Regression tracker

Cada run guarda un snapshot en `eval/history/`. `eval/regression_tracker.py` compara contra el run anterior:

- Alerta si alguna métrica **cae más de 5 pp** (o 5 puntos en judge /10).
- Muestra diff de casos que **pasaban y ahora fallan** (routing + tools + judge).

```bash
python eval/run_eval.py --quick --report   # imprime bloque REGRESSION TRACKER al final
```

### Debug cuando falla un caso (LangSmith)

1. Configura en `.env`:
   ```env
   LANGSMITH_API_KEY=lsv2_...
   LANGSMITH_PROJECT=ecommerce-eval
   ```
2. Re-ejecuta el caso fallido con trazas activas:
   ```bash
   python eval/run_eval.py --category pedidos --report
   ```
3. Abre [smith.langchain.com](https://smith.langchain.com) → proyecto `ecommerce-eval`.
4. Filtra por run reciente y localiza el `case_id` (p. ej. `tc_016`) en metadata.
5. Inspecciona la cadena: `classify_intent` → nodo enrutado → tools invocadas → respuesta del agente → validator.
6. Corrige prompts en `agents/prompts.py`, routing en `graph/nodes.py`, o el expected del caso si el criterio era incorrecto.
7. Vuelve a correr eval y verifica que `eval/history/` no reporte regresión.

Sin LangSmith, las trazas offline quedan en `eval/traces/` como JSON por caso.

## Security & production features

- **X-Hub-Signature-256** validated on every POST webhook
- **Idempotency**: duplicate `message_id` ignored for 60s (Redis)
- **Rate limit**: max 10 messages/minute per phone (sliding window Redis)
- **Order privacy**: phone number must match Shopify customer before showing order data
- **Validation loop**: response checked by Gemini; after 2 failed attempts → human escalation

## Project structure

```text
05-ecommerce-swarm/
├── main.py                  # FastAPI webhook + graph orchestration
├── config.py                # Settings + Admin API vs Storefront explanation
├── graph/
│   ├── state.py             # ConversationState TypedDict
│   ├── nodes.py             # classify, rag, sales, orders, refunds, validator…
│   ├── edges.py             # Conditional routing functions
│   └── builder.py           # StateGraph assembly + compile
├── agents/
│   ├── base.py              # create_agent() with Gemini ReAct
│   └── prompts.py           # Spanish system prompts per node
├── tools/
│   ├── shopify.py           # Admin API REST @tool functions
│   ├── knowledge_base.py    # ChromaDB RAG search
│   └── whatsapp.py          # Send messages, signature verify
├── memory/
│   └── session.py           # Redis session + rate limit + idempotency
├── models/
│   └── schemas.py           # Pydantic webhook + Shopify models
├── ingest/
│   └── load_docs.py         # Load sample_docs → ChromaDB
├── data/sample_docs/        # FAQ, shipping, returns policies
├── test_graph.py            # Prueba local del grafo (sin WhatsApp/APIs)
├── eval/                    # Harness de evaluación + mejora continua
│   ├── dataset.jsonl        # Casos curados + auto_generated
│   ├── dataset_builder.py   # Seed + generación Gemini desde Redis
│   ├── regression_tracker.py
│   ├── run_eval.py
│   ├── history/             # Snapshots por run
│   └── reports/             # HTML + last_metrics.json
├── requirements.txt
└── .env.example
```

## Environment variables

| Variable | Purpose |
|----------|---------|
| `GEMINI_API_KEY` | Google AI Studio API key |
| `SHOPIFY_STORE_URL` | Store domain (no https) |
| `SHOPIFY_ACCESS_TOKEN` | Admin API private token |
| `WHATSAPP_TOKEN` | Meta Graph API bearer token |
| `WHATSAPP_PHONE_ID` | Phone number ID from Meta |
| `WHATSAPP_VERIFY_TOKEN` | Custom string for webhook verification |
| `WHATSAPP_APP_SECRET` | App secret for signature validation |
| `REDIS_URL` | Session, rate limit, idempotency |
| `CHROMA_PATH` | Persistent ChromaDB directory |
| `ESCALATION_WEBHOOK_URL` | Optional Slack/n8n webhook for escalations |

## Example conversations

| User message | Route | Action |
|--------------|-------|--------|
| "Hola" | saludo_directo | Warm greeting + offer help |
| "¿Cuánto tarda el envío?" | rag_node | ChromaDB policy lookup |
| "Busco zapatillas under $80" | sales_node | Shopify product search |
| "Estado del pedido #1001" | orders_node | Order lookup + phone validation |
| "Quiero devolver el pedido #1001" | orders → refunds | Refund flow |
| "Quiero hablar con una persona" | escalation_node | Ticket + human handoff |
