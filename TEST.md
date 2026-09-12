# Testes Manuais com Thunder Client

Este arquivo contém requisições prontas para copiar no Thunder Client. O backend precisa estar ativo em `http://localhost:8000`.

## Preparação

No Thunder Client, abra **Env** e crie um ambiente local:

| Variable | Value |
|---|---|
| `baseUrl` | `http://localhost:8000` |
| `analysisId` | deixe vazio até criar uma análise |
| `uploadedPath` | copie `path` da resposta do upload |
| `processNumber` | `1764352-89.2025.8.06.1818` |

Selecione esse ambiente antes de executar as requisições. Para bodies JSON:

1. abra a aba **Body**;
2. selecione **JSON**;
3. cole somente o conteúdo do bloco JSON;
4. confirme o header `Content-Type: application/json`.

## Ordem recomendada

1. Readiness.
2. Listar documentos.
3. Enviar um PDF ou CSV.
4. Criar uma análise usando o caminho retornado pelo upload.
5. Consultar a análise persistida e os `model_inputs` extraídos.
6. Consultar a linha de um processo quando houver correspondência na base histórica.
7. Revisar usando os documentos enviados e, opcionalmente, a linha referenciada.
8. Executar revisão judicial do caso 01 ou 02.

---

## 1. Readiness

**Method**

```text
GET
```

**URL**

```text
{{baseUrl}}/ready
```

**Body:** nenhum.

**Esperado:** `200 OK`.

---

## 2. Criar análise de risco — caso 01

**Method**

```text
POST
```

**URL**

```text
{{baseUrl}}/v1/analyses
```

**Headers**

| Header | Value |
|---|---|
| `Content-Type` | `application/json` |

**Body → JSON**

```json
{
  "case_number": "0801234-56.2024.8.10.0001",
  "state": "AM",
  "sub_subject": "fraud",
  "claim_amount": 10000,
  "evidence": {
    "contract": false,
    "bank_statement": false,
    "credit_proof": true,
    "dossier": false,
    "debt_evolution": true,
    "referenced_report": true
  }
}
```

**Esperado:** `201 Created`.

Copie o campo `id` da resposta para `analysisId` no ambiente do Thunder Client.

Atenção: existem duas chaves `}` no final. A primeira fecha `evidence`; a segunda fecha o objeto principal. A ausência da última chave produz `422 Unprocessable Entity` com erro de JSON.

---

## 3. Consultar análise persistida

**Method**

```text
GET
```

**URL**

```text
{{baseUrl}}/v1/analyses/{{analysisId}}
```

**Body:** nenhum.

**Esperado:** `200 OK`.

Se `analysisId` não for um UUID válido, a API retorna `422`. Se o UUID não existir, retorna `404`.

---

## 4. Listar documentos disponíveis

**Method**

```text
GET
```

**URL**

```text
{{baseUrl}}/v1/documents
```

**Body:** nenhum.

**Esperado:** `200 OK` e uma lista de PDFs, CSVs e planilhas abaixo de `DOCUMENT_ROOT`.

Use exatamente os valores de `documents[].path` na análise ou revisão judicial.

---
## 5. Enviar um PDF ou CSV

**Method:** `POST`

**URL**

```text
{{baseUrl}}/v1/documents/uploads
```

Em **Body**, selecione **Form** e adicione:

| Campo | Tipo | Exemplo |
|---|---|---|
| `document_type` | Text | `contract` |
| `file` | File | escolha um PDF ou CSV |

Tipos: `case_record`, `contract`, `bank_statement`, `credit_proof`, `dossier`,
`debt_evolution`, `referenced_report` ou `other`. Não envie JSON nessa requisição.

**Esperado:** `201 Created` com:

```json
{
  "upload_id": "...",
  "path": "uploads/<upload-id>/documento.pdf",
  "kind": "pdf",
  "document_type": "contract",
  "size_bytes": 12345,
  "sha256": "..."
}
```

Copie `path` para `uploadedPath`. O limite é 20 MiB. PDFs devem ter estrutura válida,
não podem estar vazios ou criptografados; CSVs devem conter dados textuais válidos.

### 5.1. Analisar o processo a partir do documento enviado

**Method:** `POST`

**URL**

```text
{{baseUrl}}/v1/analyses
```

**Body → JSON**

```json
{
  "case_number": "{{processNumber}}",
  "documents": [
    {
      "path": "{{uploadedPath}}",
      "document_type": "other"
    }
  ]
}
```

O primeiro nó do grafo lê o PDF ou CSV e usa o LLM para extrair `state`, `sub_subject`,
`claim_amount` e os seis indicadores de evidência. Somente depois o ensemble recebe esses
campos. A resposta expõe os valores efetivamente usados em `result.model_inputs`, além de
`consulted_documents` e `unreadable_documents`.

Se o documento não trouxer UF ou valor da causa, esses campos podem ser enviados junto com
`documents` como fallback. Sem documentos, `state`, `claim_amount` e `evidence` continuam
obrigatórios.

---

## 6. Consultar os dados de um processo

**Method:** `GET`

**URL**

```text
{{baseUrl}}/v1/process-data/{{processNumber}}
```

O workbook padrão é `datasets/Hackaton_Enter_Base_Candidatos.xlsx`. Para escolher outro:

```text
{{baseUrl}}/v1/process-data/{{processNumber}}?workbook_path=datasets/outro.xlsx
```

**Esperado:** `200 OK`. Verifique `state`, `subject`, `sub_subject`, `claim_amount`,
`evidence` e `source_rows`. A resposta lista em `excluded_post_outcome_columns` os campos
removidos deterministicamente.

---

## 7. Revisar com PDF enviado e linha referenciada

O PDF enviado deve pertencer ao mesmo processo informado em `processNumber`.

**Method:** `POST`

**URL**

```text
{{baseUrl}}/v1/judge/reviews
```

**Body → JSON**

```json
{
  "case_number": "{{processNumber}}",
  "question": "Analise o documento usando somente os dados pré-processuais autorizados.",
  "documents": [
    {
      "path": "{{uploadedPath}}",
      "document_type": "contract"
    }
  ],
  "process_data_reference": {
    "workbook_path": "datasets/Hackaton_Enter_Base_Candidatos.xlsx",
    "process_number": "{{processNumber}}"
  }
}
```

**Esperado:** `200 OK`. `consulted_documents` deve conter `uploadedPath` e `process_data`
deve mostrar a linha resolvida. Se o processo da referência divergir de `case_number`, a API
retorna `422`.

---


## 8. Revisão judicial — caso 01

Requer uma credencial OpenAI válida no `.env`:

```env
OPENAI_API_KEY=sua_chave_openai
```

**Method**

```text
POST
```

**URL**

```text
{{baseUrl}}/v1/judge/reviews
```

**Headers**

| Header | Value |
|---|---|
| `Content-Type` | `application/json` |

**Body → JSON**

```json
{
  "case_number": "0801234-56.2024.8.10.0001",
  "question": "Analise a existência da contratação, do crédito e da dívida e apresente uma decisão fundamentada.",
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
    },
    {
      "path": "cases/Caso_01_0801234-56-2024-8-10-0001/04_Comprovante_de_Credito_BACEN.pdf",
      "document_type": "credit_proof"
    },
    {
      "path": "cases/Caso_01_0801234-56-2024-8-10-0001/05_Dossie_Veritas.pdf",
      "document_type": "dossier"
    },
    {
      "path": "cases/Caso_01_0801234-56-2024-8-10-0001/06_Demonstrativo_Evolucao_Divida.pdf",
      "document_type": "debt_evolution"
    },
    {
      "path": "cases/Caso_01_0801234-56-2024-8-10-0001/07_Laudo_Referenciado.pdf",
      "document_type": "referenced_report"
    }
  ],
  "new_case_data": {
    "state": "MA",
    "sub_subject": "generic",
    "claim_amount": 20000
  }
}
```

**Esperado:** `200 OK`.

Conferir na resposta:

- `consulted_documents` contém os sete PDFs;
- `findings[].citations` aponta apenas para documentos consultados;
- `document_node_reads.load_case_context` contém o PDF `01`;
- `document_node_reads.assess_contract_evidence` contém os PDFs `02` e `05`;
- `document_node_reads.assess_credit_evidence` contém os PDFs `03` e `04`;
- `document_node_reads.assess_debt_economics` contém os PDFs `06` e `07`;
- `ml_analysis` mostra os inputs enviados ao modelo e
  `ml_analysis.inputs.claim_amount_usage` vale `severity_only`;
- `ml_analysis.inputs.input_source` vale `submitted_documents`;
- `ml_analysis.inputs.evidence` possui os seis indicadores `true`;
- `ml_analysis.component_probabilities` mostra logistic regression e XGBoost;
- `ml_analysis.ensemble_weights` vale `{"logistic_regression": 0.7, "xgboost": 0.3}`;
- `strategy.risk_band` e `strategy.recommendation` refletem a árvore determinística;
- `model_card_consulted` indica se as limitações foram verificadas;
- `trace_id` correlaciona a resposta com o LangSmith e os logs locais.

Sem inferência ML válida, `strategy` deve ser `null`; a API não inventa uma recomendação.
Com inferência válida, os ramos são `< 0.40` defesa, `0.40–0.60` revisão humana e `> 0.60`
comparação econômica entre acordo e defesa.

---

## 9. Revisão judicial — caso 02

**Method**

```text
POST
```

**URL**

```text
{{baseUrl}}/v1/judge/reviews
```

**Headers**

| Header | Value |
|---|---|
| `Content-Type` | `application/json` |

**Body → JSON**

```json
{
  "case_number": "0654321-09.2024.8.04.0001",
  "question": "Compare as alegações processuais com as provas de crédito, evolução da dívida e laudo e indique contradições ou provas ausentes.",
  "documents": [
    {
      "path": "cases/Caso_02_0654321-09-2024-8-04-0001/01_Autos_Processo_0654321-09-2024-8-04-0001.pdf",
      "document_type": "case_record"
    },
    {
      "path": "cases/Caso_02_0654321-09-2024-8-04-0001/02_Comprovante_de_Credito_BACEN.pdf",
      "document_type": "credit_proof"
    },
    {
      "path": "cases/Caso_02_0654321-09-2024-8-04-0001/03_Demonstrativo_Evolucao_Divida.pdf",
      "document_type": "debt_evolution"
    },
    {
      "path": "cases/Caso_02_0654321-09-2024-8-04-0001/04_Laudo_Referenciado.pdf",
      "document_type": "referenced_report"
    }
  ],
  "new_case_data": {
    "state": "AM",
    "sub_subject": "fraud",
    "claim_amount": 25000
  }
}
```

**Esperado:** `200 OK`.

---

## Erros comuns

### `422 Unprocessable Entity` ao criar análise

Confirme:

- o JSON termina com duas chaves `}`;
- `Content-Type` é `application/json`;
- `new_case_data.state` possui exatamente duas letras;
- `new_case_data.sub_subject` é `fraud` ou `generic`;
- `new_case_data.claim_amount` é número positivo, sem aspas;
- cada item de `documents` contém `path` e um `document_type` aceito;
- existe exatamente uma origem: `new_case_data` ou `process_data_reference`;
- não existem vírgulas depois do último campo de um objeto.

O body da imagem estava sem a última chave `}` do objeto principal.

### Aplicação não inicia sem credencial OpenAI

O agente é obrigatório. Confirme em `backend/.env`:

```env
OPENAI_API_KEY=sua_chave_openai
```

Reinicie o backend depois de alterar `.env`. Erros do provedor durante uma análise retornam
`502`; não existe fallback textual sem LLM.

### `422` informando caminho inválido

Execute `GET {{baseUrl}}/v1/documents` e copie o campo `path` exatamente. Caminhos absolutos, `..`, extensões não permitidas e documentos fora do catálogo são rejeitados.

### `502` na revisão judicial

A execução do provedor LLM ou a validação da resposta falhou. Use o `trace_id` quando disponível e consulte os logs do backend e o projeto LangSmith.
