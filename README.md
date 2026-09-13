# EnterOS

Plataforma de apoio à decisão para processos bancários de não reconhecimento de empréstimo.

O EnterOS organiza os autos e subsídios de cada processo, consulta os documentos com IA, estima o risco jurídico, recomenda acordo ou defesa e acompanha o resultado financeiro das decisões encaminhadas ao banco.

## O que o projeto entrega

### Área do advogado

- processos e documentos organizados em um único workspace;
- upload e análise de PDFs;
- chat documental com resposta transmitida por SSE;
- ferramentas e fontes exibidas durante a resposta;
- citações clicáveis que abrem o PDF na página consultada;
- estimativa de risco, condenação e força documental;
- recomendação de acordo, defesa ou revisão humana;
- faixa de negociação com abertura, alvo e teto;
- registro definitivo da decisão do advogado.

### Área do banco

- decisões recebidas dos advogados;
- revisão independente automática;
- acompanhamento de aderência à política;
- registro do resultado de cada causa;
- indicadores de êxito, economia e custo;
- consolidação financeira das decisões concluídas.

## Arquitetura

- **Frontend:** Next.js e React.
- **Backend:** FastAPI e LangGraph.
- **Banco de dados:** PostgreSQL com migrations Alembic.
- **IA documental:** OpenAI com ferramentas de leitura de documentos.
- **Machine learning:** ensemble de regressão logística e XGBoost.
- **Streaming:** Server-Sent Events para ferramentas e tokens do chat.
- **Observabilidade:** integração opcional com LangSmith.

O diagrama completo está em [`docs/architecture.svg`](docs/architecture.svg).

## Pré-requisitos

- Docker com Docker Compose;
- Node.js 20 ou superior;
- npm;
- chave da API da OpenAI.

Para executar o backend sem Docker também são necessários Python 3.12 e [`uv`](https://docs.astral.sh/uv/).

## Como iniciar

### 1. Configure o backend

Na raiz do repositório:

```bash
cp backend/.env.example backend/.env
```

Preencha obrigatoriamente a chave:

```env
OPENAI_API_KEY=sua_chave_openai
```

As demais configurações já possuem valores adequados para desenvolvimento local. O LangSmith é opcional.

### 2. Configure o frontend

```bash
cp frontend/.env.example frontend/.env
```

O valor padrão conecta o frontend à API local:

```env
BACKEND_URL=http://localhost:8000
```

### 3. Inicie banco e backend

Em um terminal:

```bash
cd backend
docker compose up --build
```

O Compose:

1. inicia o PostgreSQL;
2. aguarda o banco ficar saudável;
3. aplica as migrations;
4. inicia a API FastAPI.

### 4. Inicie o frontend

Em outro terminal:

```bash
cd frontend
npm install
npm run dev
```

### 5. Acesse

| Serviço | Endereço |
|---|---|
| Área do advogado | <http://localhost:3000> |
| Área do banco | <http://localhost:3000/admin> |
| API | <http://localhost:8000> |
| Swagger | <http://localhost:8000/docs> |
| Readiness | <http://localhost:8000/ready> |

Para encerrar o backend e o banco:

```bash
cd backend
docker compose down
```

Os dados do PostgreSQL permanecem no volume Docker. Use `docker compose down -v` somente quando quiser apagá-los.

## Execução local do backend

Para desenvolver o backend fora do container, mantenha apenas o PostgreSQL no Docker:

```bash
cd backend
docker compose up -d postgres
uv sync --locked
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

## Dados

Os dados fornecidos para o projeto estão em:

```text
data/
├── datasets/
│   └── Hackaton_Enter_Base_Candidatos.xlsx
└── cases/
    ├── Caso_01_0801234-56-2024-8-10-0001/
    └── Caso_02_0654321-09-2024-8-04-0001/
```

A planilha histórica alimenta os modelos de risco e severidade. As pastas de casos contêm os autos e subsídios usados na demonstração documental.

## Estrutura do repositório

```text
backend/   API, agentes, política, ML, persistência e migrations
frontend/  workspace do advogado e painel do banco
data/      planilha histórica e processos de demonstração
docs/      apresentação, vídeo e diagrama de arquitetura
```

## Entregáveis

- [`docs/presentation.md`](docs/presentation.md)
- [`docs/demo_video.md`](docs/demo_video.md)
- [`docs/architecture.svg`](docs/architecture.svg)
