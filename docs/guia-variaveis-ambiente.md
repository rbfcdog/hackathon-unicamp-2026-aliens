# Guia de variáveis de ambiente do EnterOS

Este documento explica as variáveis disponíveis em `backend/.env.example`, seus efeitos no ambiente local e as substituições aplicadas pelo Docker Compose.

## O agente LLM é obrigatório

O EnterOS não possui uma opção para desabilitar o agente. Toda análise combina os modelos de
machine learning com uma etapa executada pela OpenAI:

- `POST /v1/analyses` calcula risco, valor e política, depois exige uma explicação do LLM;
- `POST /v1/judge/reviews` exige o agente para ler, confrontar e fundamentar os documentos;
- falhas de autenticação, provedor ou saída estruturada são retornadas como erro; não existe
  texto determinístico substituto.

A credencial é obrigatória:

```env
OPENAI_API_KEY=sua-chave
OPENAI_MODEL=gpt-5.4-mini
```

Sem uma chave não vazia, a aplicação não inicia. No Docker Compose, a ausência da variável
também interrompe a resolução da configuração antes de criar os containers.

## Variáveis da aplicação

### `APP_NAME`

```env
APP_NAME=EnterOS
```

Nome exibido pelo FastAPI no OpenAPI e no Swagger disponível em `http://localhost:8000/docs`. Não altera o nome do container ou do banco.

### `ENVIRONMENT`

```env
ENVIRONMENT=development
```

Identifica o ambiente e é usado como tag nos traces da revisão judicial. Valores típicos: `development`, `staging` e `production`.

### `API_PREFIX`

```env
API_PREFIX=/v1
```

Prefixo das rotas da aplicação, incluindo:

```text
/v1/analyses
/v1/documents
/v1/process-data
/v1/judge/reviews
```

As rotas de saúde ficam fora desse prefixo.

### `DATABASE_URL`

```env
DATABASE_URL=postgresql+asyncpg://enter-os:enter-os@localhost:5432/EnterOS
```

Conexão assíncrona do SQLAlchemy com PostgreSQL. Formato:

```text
postgresql+asyncpg://USUARIO:SENHA@HOST:PORTA/BANCO
```

Quando o backend roda diretamente na máquina, o host é `localhost`. No Docker Compose, a variável é substituída internamente por:

```text
postgresql+asyncpg://enter-os:enter-os@postgres:5432/EnterOS
```

`postgres` é o nome do serviço Docker.

### `CORS_ORIGINS`

```env
CORS_ORIGINS=http://localhost:5173
```

Lista de frontends autorizados a chamar a API pelo navegador. Múltiplas origens são separadas por vírgula:

```env
CORS_ORIGINS=http://localhost:5173,https://app.enter-os.com
```

## PostgreSQL e Docker

### `POSTGRES_DB`

```env
POSTGRES_DB=EnterOS
```

Banco criado na primeira inicialização do volume PostgreSQL. Alterar essa variável não renomeia automaticamente um banco dentro de um volume já inicializado.

### `POSTGRES_USER`

```env
POSTGRES_USER=enter-os
```

Usuário administrativo criado pelo container PostgreSQL.

### `POSTGRES_PASSWORD`

```env
POSTGRES_PASSWORD=enter-os
```

Senha do usuário PostgreSQL. O valor atual serve somente para desenvolvimento. Em produção, use uma credencial forte armazenada em um secret manager.

### `POSTGRES_PORT`

```env
POSTGRES_PORT=5432
```

Porta publicada na máquina:

```text
localhost:5432 → container:5432
```

Pode ser alterada quando já existir outro PostgreSQL local, por exemplo:

```env
POSTGRES_PORT=5433
```

### `BACKEND_PORT`

```env
BACKEND_PORT=8000
```

Porta pública da API:

```text
localhost:8000 → container:8000
```

### `APP_UID`

```env
APP_UID=1000
```

UID usado para executar o backend dentro do container.

### `APP_GID`

```env
APP_GID=1000
```

GID usado pelo container. UID e GID fazem os arquivos em `data/uploads/` pertencerem ao usuário local, evitando PDFs criados como `root`.

## OpenAI e LLM


### `OPENAI_API_KEY`

```env
OPENAI_API_KEY=
```

Credencial usada para chamar a API da OpenAI. Nunca deve ser versionada ou colocada em `.env.example`.

### `OPENAI_MODEL`

```env
OPENAI_MODEL=gpt-5.4-mini
```

Modelo utilizado para:

- comparar documentos;
- organizar fundamentos jurídicos;
- produzir a decisão estruturada;
- redigir explicações.

Esse modelo não calcula as probabilidades do ensemble. O cálculo 70/30 permanece determinístico no backend.

## Machine learning

### `MODEL_ARTIFACT_PATH`

```env
MODEL_ARTIFACT_PATH=artifacts/judicial-risk-v5.joblib
```

Caminho do artefato treinado que contém:

- regressão logística;
- XGBoost;
- ensemble fixo de 70% regressão logística e 30% XGBoost;
- modelos `HistGradientBoostingRegressor` para valor médio e quantis.

A versão correta é `v5`. A versão `v4` não contém o ensemble fixo solicitado.

### `DOCUMENT_ROOT`

```env
DOCUMENT_ROOT=../data
```

Diretório autorizado para documentos e planilhas quando o backend roda localmente. Dentro do Docker Compose ele é substituído por:

```env
DOCUMENT_ROOT=/data
```

O diretório local `data/` é montado como `/data` no container. Essa raiz controla:

- PDFs dos casos;
- planilha histórica;
- PDFs recebidos por upload;
- proteção contra leitura de arquivos externos.

## LangSmith

### `LANGSMITH_TRACING`

```env
LANGSMITH_TRACING=false
```

Ativa o envio dos traces do LangGraph para o LangSmith. O padrão é `false` porque os traces podem conter prompts, conteúdo extraído dos PDFs, respostas de ferramentas e fundamentos jurídicos.

Para ativar o tracing, também é necessária uma chave LangSmith.

### `LANGSMITH_API_KEY`

```env
LANGSMITH_API_KEY=
```

Credencial do LangSmith. Sem ela, o tracing permanece desabilitado mesmo que `LANGSMITH_TRACING=true`.

### `LANGSMITH_PROJECT`

```env
LANGSMITH_PROJECT=enter-os
```

Projeto em que os traces são agrupados. Sugestão por ambiente:

```env
LANGSMITH_PROJECT=enter-os-dev
LANGSMITH_PROJECT=enter-os-staging
LANGSMITH_PROJECT=enter-os-prod
```

### `LANGSMITH_ENDPOINT`

```env
LANGSMITH_ENDPOINT=
```

Endpoint alternativo do LangSmith. Vazio significa usar o endpoint padrão. Organizações hospedadas na região europeia podem definir:

```env
LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com
```

### `LANGSMITH_WORKSPACE_ID`

```env
LANGSMITH_WORKSPACE_ID=
```

Workspace específico do LangSmith. É necessário quando a chave pode acessar mais de um workspace.

## Configuração recomendada para desenvolvimento completo

```env
APP_NAME=EnterOS
ENVIRONMENT=development
API_PREFIX=/v1
DATABASE_URL=postgresql+asyncpg://enter-os:enter-os@localhost:5432/EnterOS
CORS_ORIGINS=http://localhost:5173

POSTGRES_DB=EnterOS
POSTGRES_USER=enter-os
POSTGRES_PASSWORD=enter-os
POSTGRES_PORT=5432
BACKEND_PORT=8000
APP_UID=1000
APP_GID=1000

OPENAI_API_KEY=sua-chave
OPENAI_MODEL=gpt-5.4-mini
MODEL_ARTIFACT_PATH=artifacts/judicial-risk-v5.joblib
DOCUMENT_ROOT=../data

LANGSMITH_TRACING=true
LANGSMITH_API_KEY=sua-chave-langsmith
LANGSMITH_PROJECT=enter-os-dev
LANGSMITH_ENDPOINT=
LANGSMITH_WORKSPACE_ID=
```

Ativar LangSmith e OpenAI implica enviar conteúdo a serviços externos. Para documentos reais, habilite somente depois de definir anonimização, retenção e controle de acesso.
