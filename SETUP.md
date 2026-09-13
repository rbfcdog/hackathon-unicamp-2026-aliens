# Setup e Execução

## Pré-requisitos

- Docker com Compose v2
- [`uv`](https://docs.astral.sh/uv/) 0.12 ou superior
- Python 3.12 apenas para execução local

## Configuração

O backend está em `backend/`. Copie o arquivo de ambiente antes de iniciar:

```bash
cp backend/.env.example backend/.env
```

O agente LLM é obrigatório em toda análise. Configure a OpenAI antes de iniciar. O tracing no
LangSmith continua opcional:

```env
OPENAI_API_KEY=sua_chave_aqui
OPENAI_MODEL=gpt-5.4-mini
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=sua_chave_langsmith
LANGSMITH_PROJECT=enter-os
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_WORKSPACE_ID=
```

Sem `OPENAI_API_KEY`, a aplicação não inicia. Falhas do provedor ou da saída estruturada são
retornadas explicitamente; não existe explicação textual determinística substituta.

Nunca versione `backend/.env`.

## Execução conjunta

Prepare também o ambiente do frontend e inicie banco, API e interface com um único comando:

```bash
cp frontend/.env.example frontend/.env
./start.sh
```

O script instala as dependências do frontend quando necessário, executa o Compose do backend
e inicia o Next.js em modo de desenvolvimento. `Ctrl+C` encerra os dois processos.

Para validar os arquivos de ambiente e os pré-requisitos sem iniciar os serviços:

```bash
./start.sh --check
```

## Execução com Docker

O Compose inicia PostgreSQL, executa as migrations do Alembic e sobe a API:

```bash
cd backend
docker compose up --build
```

Serviços:

- API: <http://localhost:8000>
- Swagger: <http://localhost:8000/docs>
- PostgreSQL: `localhost:5432`
- Readiness: <http://localhost:8000/ready>

Para encerrar:

```bash
cd backend
docker compose down
```

Use `docker compose down -v` apenas quando quiser apagar também os dados locais do PostgreSQL.

## Execução local com uv

Suba apenas o banco:

```bash
cd backend
docker compose up -d postgres
```

Instale as dependências bloqueadas, aplique as migrations e inicie a API:

```bash
cd backend
uv sync --locked
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

## Frontend

Com a API ativa em `http://localhost:8000`, instale e inicie o workspace Next.js:

```bash
cd frontend
npm install
npm run dev
```

A interface fica em <http://localhost:3000>. O Next.js encaminha chamadas de
`/api/backend/*` para a API; defina `BACKEND_URL` apenas quando o backend estiver em outro host:

```bash
cd frontend
BACKEND_URL=http://localhost:8000 npm run dev
```

Para validar e executar o build de produção:

```bash
cd frontend
npm run lint
npm run build
npm run start
```

## Treinamento dos modelos

A base histórica local está em `data/datasets/Hackaton_Enter_Base_Candidatos.xlsx`. Execute o pipeline:

```bash
cd backend
uv sync --locked
uv run python -m scripts.train_models
```

O comando treina e calibra os dois classificadores, fixa a saída final em 70% regressão
logística e 30% XGBoost, avalia uma única vez no holdout e treina os modelos de valor médio e
quantis. As saídas são:
```text
backend/artifacts/judicial-risk-v5.joblib
backend/artifacts/judicial-risk-v5.metrics.json
```

O `.joblib` é um artefato versionado e precisa acompanhar a aplicação. O JSON registra hash
da base, componentes, pesos fixos, métricas segmentadas, importância por permutação, predições
de exemplo e verificação de reload.

A versão v5 usa dois schemas independentes:

- risco: UF, sub-assunto e seis indicadores documentais;
- severidade: as mesmas features mais `Valor da causa`, conhecido no início do processo;
- target da severidade: `Valor da condenação/indenização`, observado depois do resultado;
- algoritmo de severidade: quatro `HistGradientBoostingRegressor`, com perda
  `squared_error` para a média e perdas `quantile` para q10, q50 e q90;

O classificador de risco nunca recebe `Valor da causa`. O modelo de severidade recebe somente
o valor inicial da causa, não o valor pago. Resultado, condenação, acordo e pagamento observado
nunca entram como features. O campo `claim_amount` da API alimenta a severidade e a política
determinística de negociação.

No holdout, a v5 obteve:

- ensemble 70/30: ROC-AUC `0,9253`, Brier `0,0910`, precisão `82,11%` e recall `75,56%`;
- severidade: MAE `R$ 2.305,37`, `R² = 0,6214` e cobertura q10–q90 de `78,27%`.

## Thunder Client

Crie um ambiente no Thunder Client com:

| Variable | Value |
|---|---|
| `baseUrl` | `http://localhost:8000` |
| `analysisId` | deixe vazio até criar uma análise |

O fluxo principal começa pelo upload dos documentos:

1. use `POST /v1/documents/uploads` com `multipart/form-data`;
2. envie `document_type` e um arquivo PDF ou CSV;
3. copie o `path` retornado;
4. envie esse caminho em `documents` no `POST /v1/analyses`.

Exemplo de análise orientada por documento:

```json
{
  "case_number": "0801234-56.2024.8.10.0001",
  "documents": [
    {
      "path": "uploads/<upload-id>/processo.pdf",
      "document_type": "case_record"
    },
    {
      "path": "uploads/<upload-id>/dados.csv",
      "document_type": "other"
    }
  ]
}
```

O primeiro nó LLM lê os documentos e extrai os campos pré-processuais aceitos pelo ML:
UF, sub-assunto, valor inicial da causa e os seis indicadores binários de evidência. O
ensemble roda somente após essa extração. A explicação final recebe o resumo documental
validado e o resultado do ML.

Quando UF ou valor da causa não constarem nos documentos, envie `state` e `claim_amount`
junto com `documents` como fallback. Sem documentos, a API exige `state`, `claim_amount`
e `evidence`, preservando o fluxo de entrada estruturada.

As requisições completas para readiness, upload, análise, consulta persistida, catálogo e
revisão dos casos 01 e 02 estão em [`TEST.md`](TEST.md), prontas para copiar no Thunder Client.

## API de análise

Envie um PDF ou CSV:

```bash
curl -X POST http://localhost:8000/v1/documents/uploads \
  -F 'document_type=case_record' \
  -F 'file=@/caminho/para/processo.pdf'
```

Use o `path` retornado para criar a análise:

```bash
curl -X POST http://localhost:8000/v1/analyses \
  -H 'Content-Type: application/json' \
  -d '{
    "case_number": "0801234-56.2024.8.10.0001",
    "documents": [
      {
        "path": "uploads/<upload-id>/processo.pdf",
        "document_type": "case_record"
      }
    ]
  }'
```

Consulte o resultado persistido:

```bash
curl http://localhost:8000/v1/analyses/<analysis_id>
```

O grafo executa as etapas:

```text
extract_model_inputs (LLM lê PDF/CSV)
  -> assess_evidence
  -> estimate_risk (ensemble ML)
  -> apply_policy
  -> request_human_review | price_agreement | prepare_defense
  -> explain_recommendation (LLM)
```

A resposta registra os dados efetivamente passados ao modelo em `result.model_inputs`.
O LLM final explica uma decisão já calculada; ele não altera probabilidade, recomendação
ou faixa de negociação.
### Árvore determinística de decisão

A política `decision-tree-2026-09-12` implementa os limiares do fluxo:

| Probabilidade de perda | Decisão |
|---|---|
| `< 40%` | preparar defesa |
| `40%` a `60%`, inclusive | bloquear automação e solicitar revisão humana |
| `> 60%` | comparar o custo-alvo do acordo com o custo esperado da defesa |

O custo esperado da defesa é `P(perda) × condenação esperada + R$ 1.500`. No risco alto,
a política limita abertura, alvo e teto do acordo entre percentuais do valor inicial da causa.
Só recomenda acordo quando o alvo calculado é estritamente menor que o custo esperado da
defesa; caso contrário, prepara defesa. Se a oferta recomendada for rejeitada, o próximo passo
registrado pela revisão documental é `counterproposal`. O LLM não altera limiares, fórmulas,
probabilidades ou valores.


## API de revisão judicial por documentos

Liste os documentos que o agente pode consultar:

```bash
curl http://localhost:8000/v1/documents
```

Envie um PDF ou CSV e guarde o caminho e o tipo retornados:

```bash
curl -X POST http://localhost:8000/v1/documents/uploads \
  -F 'document_type=contract' \
  -F 'file=@/caminho/para/contrato.pdf'
```

Tipos aceitos: `case_record`, `contract`, `bank_statement`, `credit_proof`, `dossier`,
`debt_evolution`, `referenced_report` e `other`. O upload aceita PDF ou CSV válido de até
20 MiB e devolve caminho imutável, SHA-256, `kind` e `document_type`.

Consulte os dados pré-processuais de uma linha da base:

```bash
curl 'http://localhost:8000/v1/process-data/1764352-89.2025.8.06.1818'
```

O lookup une as abas `Resultados dos processos` e `Subsídios disponibilizados`. A resposta
contém UF, sub-assunto, valor da causa, seis indicadores binários e as linhas de origem.
`Resultado macro`, `Resultado micro` e `Valor da condenação/indenização` são excluídos.

Um processo novo, sem linha na planilha, fornece os três campos pré-processuais não derivados
dos documentos e referencia cada PDF com seu tipo:

```json
{
  "case_number": "0801234-56.2024.8.10.0001",
  "question": "Analise a existência da contratação, do crédito e da dívida.",
  "documents": [
    {
      "path": "cases/Caso_01_0801234-56-2024-8-10-0001/01_Autos_Processo_0801234-56-2024-8-10-0001.pdf",
      "document_type": "case_record"
    },
    {
      "path": "cases/Caso_01_0801234-56-2024-8-10-0001/02_Contrato_502348719.pdf",
      "document_type": "contract"
    },
    {
      "path": "cases/Caso_01_0801234-56-2024-8-10-0001/03_Extrato_Bancario.pdf",
      "document_type": "bank_statement"
    }
  ],
  "new_case_data": {
    "state": "MA",
    "sub_subject": "generic",
    "claim_amount": 20000
  }
}
```

Uma revisão baseada em upload e linha da planilha usa:

```json
{
  "case_number": "1764352-89.2025.8.06.1818",
  "question": "Analise o documento usando somente os dados pré-processuais autorizados.",
  "documents": [
    {
      "path": "uploads/<upload-id>/documento.pdf",
      "document_type": "contract"
    }
  ],
  "process_data_reference": {
    "workbook_path": "datasets/Hackaton_Enter_Base_Candidatos.xlsx",
    "process_number": "1764352-89.2025.8.06.1818"
  }
}
```

Forneça exatamente uma origem: `new_case_data` ou `process_data_reference`. No primeiro caso,
os seis indicadores são derivados dos tipos dos PDFs submetidos. No segundo, o backend lê as
duas abas e combina os indicadores da linha com novos documentos submetidos. O mesmo vetor
binário alimenta logistic regression e XGBoost; a resposta expõe as probabilidades dos dois
componentes e a divergência do ensemble.

O grafo calcula essa inferência deterministicamente antes do LLM. O agente pode consultar
`inspect_risk_model_card`, mas não pode alterar os inputs, as probabilidades ou a política. Os
documentos permanecem dados não confiáveis e todos precisam ser lidos antes da finalização.
Antes do agente LLM, quatro nós determinísticos consultam os PDFs reconhecidos do caso 01:

| Nó LangGraph | PDFs consultados | Evidência examinada |
|---|---|---|
| `load_case_context` | `01_Autos_Processo_...pdf` | alegações, pedidos, controvérsia e valor da causa |
| `assess_contract_evidence` | `02_Contrato_502348719.pdf`; `05_Dossie_Veritas.pdf` | termos contratuais, assinatura e biometria |
| `assess_credit_evidence` | `03_Extrato_Bancario.pdf`; `04_Comprovante_de_Credito_BACEN.pdf` | crédito, conta, data e movimentação do valor |
| `assess_debt_economics` | `06_Demonstrativo_Evolucao_Divida.pdf`; `07_Laudo_Referenciado.pdf` | parcelas, saldo, mora e consolidação das provas |

Os nós registram os caminhos efetivamente atribuídos em `document_node_reads`. O roteamento
usa `document_type`, não o nome do arquivo. Documentos do tipo `other` ainda precisam ser
consultados pelo agente antes da finalização.


A resposta contém disposição sugerida, confiança, fundamentos, citações, documentos
consultados, falhas de leitura, `trace_id` e:

- `ml_analysis`: inputs usados, probabilidades de logistic regression e XGBoost, probabilidade
  selecionada, divergência, condenação esperada, quantis e versão;
- `strategy`: ramo determinístico, custos comparados, faixa de acordo, próxima ação e motivo
  de revisão humana; fica `null` quando não existe inferência ML válida;
- `document_node_reads`: matriz auditável de nó para documentos pré-consultados;
- `model_card_consulted`: confirma se o agente verificou as métricas e limitações;
- `ml_tool_errors`: falhas explícitas de inferência, sem fallback inventado;
- `process_data`: linha pré-processual resolvida, workbook e localizadores das duas abas.

Fluxo recomendado para o advogado:

1. confirmar que a lista de documentos está completa;
2. verificar os fatos extraídos nas citações de página ou linha;
3. conferir os inputs estruturados enviados ao ML;
4. tratar divergência dos modelos, documento ilegível ou prova ausente como revisão obrigatória;
5. registrar decisão humana e justificativa antes de usar o resultado em negociação ou peça.

Com `LANGSMITH_TRACING=true`, cada execução aparece no projeto configurado em
`LANGSMITH_PROJECT`, com tags de ambiente e metadados sem o número bruto do processo.

O trace automático pode conter prompts, respostas de ferramentas e texto extraído. Use apenas
casos sintéticos até implementar redaction de inputs/outputs e aprovar região, acesso e retenção
para dados reais. O passo a passo completo de visualização em tempo real está em
[`docs/guia-visualizacao-fluxos.md`](docs/guia-visualizacao-fluxos.md). Configuração avançada
de região, workspace e o roadmap da experiência do advogado estão em
[`docs/roadmap-experiencia-advogado-e-langsmith.md`](docs/roadmap-experiencia-advogado-e-langsmith.md).

## Chat documental por processo

O chat é um módulo separado do analyzer. Ele não executa o ensemble, não altera a recomendação
de acordo/defesa e não reutiliza documentos de outro processo. O backend resolve a lista
autorizada pelo `case_number` antes de iniciar o grafo e as ferramentas rejeitam qualquer
caminho fora dessa lista.

Fluxo pela interface:

1. selecione um processo;
2. abra **Área de trabalho**;
3. selecione a aba **Assistente**;
4. anexe PDFs ou CSVs em **Documentos do processo**;
5. envie a pergunta. A trilha abaixo da conversa mostra conexão, leituras e falhas, sem expor
   cadeia de pensamento.

Endpoints:

| Método | Caminho | Função |
|---|---|---|
| `GET` | `/v1/processes/{case_number}/documents` | lista documentos vinculados e arquivos do acervo do caso |
| `POST` | `/v1/processes/{case_number}/documents` | anexa PDF/CSV com `multipart/form-data` |
| `DELETE` | `/v1/processes/{case_number}/documents/{document_id}` | remove somente upload gerenciado |
| `POST` | `/v1/processes/{case_number}/chats` | cria uma conversa persistente |
| `GET` | `/v1/processes/{case_number}/chats` | lista conversas do processo |
| `GET` | `/v1/processes/{case_number}/chats/{chat_id}` | recupera histórico persistido |
| `POST` | `/v1/processes/{case_number}/chats/{chat_id}/messages/stream` | envia mensagem e recebe SSE |

Exemplo completo:

```bash
CASE='0801234-56.2024.8.10.0001'

curl -X POST "http://localhost:8000/v1/processes/$CASE/documents" \
  -F 'document_type=contract' \
  -F 'file=@/caminho/para/contrato.pdf'

CHAT_ID="$(
  curl -s -X POST "http://localhost:8000/v1/processes/$CASE/chats" |
  python -c 'import json,sys; print(json.load(sys.stdin)["id"])'
)"

curl -N -X POST \
  "http://localhost:8000/v1/processes/$CASE/chats/$CHAT_ID/messages/stream" \
  -H 'Accept: text/event-stream' \
  -H 'Content-Type: application/json' \
  -d '{"message":"Qual é o valor da causa e onde ele aparece?"}'
```

O stream emite:

- `ready`: conversa, trace e quantidade de documentos no escopo;
- `tool_start` / `tool_end`: ferramenta, caminho consultado e status;
- `token`: fragmento incremental da resposta final;
- `complete`: mensagem persistida, fontes consultadas e documentos ilegíveis;
- `error`: falha sanitizada e `trace_id` para correlação.

O harness limita o loop a 12 turnos de agente, exige ao menos uma leitura documental antes da
resposta, envia heartbeat SSE durante períodos ociosos e cancela o produtor quando o cliente
desconecta. Uploads são validados, limitados a 20 MiB, deduplicados por SHA-256 por processo e
limitados a 50 arquivos. PDFs criptografados, CSVs vazios, travessia de diretório e leitura
cruzada entre processos são rejeitados.

Com tracing ativo, o LangSmith registra a execução com `run_name=process-document-chat`, tag
`process-chat` e o mesmo `trace_id` retornado no evento `ready`. O número bruto do processo não
é enviado nos metadados; é usado um hash curto.

## Verificação

Com o PostgreSQL ativo:

```bash
cd backend
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

Para testes manuais no Thunder Client, siga [`TEST.md`](TEST.md).

## Estrutura do backend

```text
backend/
├── app/
│   ├── api/          # rotas FastAPI
│   ├── db/           # SQLAlchemy assíncrono
│   ├── domain/       # política determinística
│   ├── graph/        # aplicação LangGraph
│   ├── ml/           # interface de inferência de risco
│   ├── schemas/      # contratos Pydantic
│   └── services/     # casos de uso
├── migrations/       # Alembic
├── tests/
├── compose.yaml
├── Dockerfile
├── pyproject.toml
└── uv.lock
```
