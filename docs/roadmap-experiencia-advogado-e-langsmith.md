# Roadmap da Experiência do Advogado e Configuração do LangSmith

## Objetivo

Evoluir a revisão atual de documentos para um workspace jurídico verificável. O LLM organiza, compara e redige; as fontes continuam sendo a autoridade factual, o ML continua sendo apoio estatístico e a decisão continua humana.

## Estado atual

O backend já oferece:

- catálogo controlado e upload tipado de PDF;
- leitura confinada a `DOCUMENT_ROOT` e à lista de documentos da revisão;
- consulta pré-processual às duas abas do workbook por número de processo;
- grafo LangGraph com orçamento limitado de chamadas;
- citações restritas aos documentos efetivamente lidos;
- inferência determinística do ensemble e ferramenta `inspect_risk_model_card`;
- resposta estruturada com análise jurídica, inputs e componentes do ML, erros e `trace_id`;
- tracing opcional no LangSmith.

## Princípios obrigatórios

1. Nenhuma afirmação material sem documento e localização verificável.
2. Presença de arquivo não prova autenticidade nem o conteúdo alegado.
3. Probabilidade do ML não é prova, causalidade ou decisão jurídica.
4. Contradição, documento ilegível, baixa confiança ou divergência dos modelos exige revisão humana.
5. O PostgreSQL é a fonte de verdade; LangSmith é telemetria e não pode ser a única cópia de uma decisão.
6. Dados de processos não podem cruzar usuários, escritórios ou sessões.

## Melhorias priorizadas

| Prioridade | Melhoria | Valor para o advogado | Resultado mínimo verificável |
|---|---|---|---|
| P0 | Matriz fato–prova–fonte | Mostra rapidamente por que cada conclusão existe | Todo fato material contém documento, página/linha, trecho e estado de verificação |
| P0 | Crítico de contradições | Evita decidir com versões incompatíveis ou provas incompletas | Contradições entre inicial, contestação, contrato, extrato e laudos aparecem antes da recomendação |
| P0 | Workspace persistente por processo | Preserva contexto, histórico e responsabilidade | Conversas, documentos, revisões e decisões humanas ficam isolados e versionados por processo |
| P0 | Minuta com `citation gate` | Acelera a redação sem esconder falta de suporte | Minuta só é liberada quando cada afirmação material possui citação válida |
| P1 | Revisão humana estruturada | Transforma correções em dado operacional | Advogado aceita, ajusta ou rejeita e registra motivo obrigatório |
| P1 | Conectores jurídicos oficiais | Permite pesquisa externa com proveniência | Resultado informa tribunal/fonte, URL, data, identificador e trecho recuperado |
| P1 | Avaliação por afirmação | Mede a confiabilidade real do RAG | Dashboard separa retrieval, suporte, correção da citação e qualidade da resposta |

## 1. Matriz fato–prova–fonte

### Fluxo

```text
extrair alegações
  -> localizar evidências
  -> classificar suporte ou conflito
  -> validar citações
  -> apresentar matriz ao advogado
```

Cada registro deve conter:

```text
claim_id
case_id
claim_text
claim_type
asserted_by
status: supported | contradicted | unsupported | unreadable
source_document_id
page_or_range
source_excerpt
extractor_version
reviewed_by
reviewed_at
```

### Critérios de aceite

- fatos sem fonte aparecem como `unsupported`, nunca como confirmados;
- uma citação aponta apenas para documento lido com sucesso;
- o advogado abre a fonte a partir da matriz;
- alteração do documento invalida citações derivadas da versão anterior.

## 2. Crítico de contradições

Executar depois da extração e antes do ML ou da minuta. Comparações prioritárias:

- existência e data da contratação;
- identidade da parte e titularidade da conta;
- valor contratado, creditado, cobrado e atualizado;
- datas de crédito, parcelas, mora e ajuizamento;
- divergência entre narrativa processual, contrato, extrato, BACEN e laudos;
- ausência de documento indispensável declarado como existente.

A saída deve indicar os dois lados do conflito, suas fontes e a ação exigida. O crítico não escolhe silenciosamente qual versão é verdadeira.

## 3. Workspace persistente por processo

Entidades mínimas:

```text
matter
matter_member
matter_document
conversation_thread
conversation_message
review_run
claim
citation
lawyer_decision
```

Requisitos:

- autorização por `matter_id` em toda leitura e escrita;
- histórico imutável de versões de documentos e recomendações;
- `thread_id` separado por processo e finalidade;
- exclusão e retenção controladas;
- nenhum texto de outro processo disponível ao prompt ou às ferramentas.

## 4. Minuta com `citation gate`

A minuta é uma etapa posterior à matriz e ao crítico. Antes de liberar o artefato:

1. extrair as afirmações materiais do texto gerado;
2. exigir ao menos uma fonte válida para cada afirmação;
3. bloquear citações de documento não consultado;
4. marcar inferências e argumentos jurídicos separadamente de fatos;
5. exigir revisão humana antes de exportar ou protocolar.

Formatos iniciais: relatório de risco, resumo executivo e minuta defensiva. DOCX ou PDF são artefatos de saída; não são fonte de verdade da revisão.

## 5. Revisão humana estruturada

A interface deve oferecer:

```text
accept
adjust
reject
```

Campos obrigatórios:

```text
action
reason_code
reason_text
changed_fields
reviewer_id
timestamp
policy_version
model_version
prompt_version
```

O feedback pode alimentar avaliação e futura revalidação do modelo. Não deve entrar automaticamente como dado de treino sem curadoria, controle de versão e prevenção de leakage.

## 6. Conectores jurídicos oficiais

Priorizar fontes oficiais brasileiras e APIs/licenças permitidas. Cada passagem recuperada precisa preservar:

- fonte e tribunal;
- URL ou identificador canônico;
- data de publicação e de consulta;
- órgão julgador e número, quando disponível;
- trecho exato utilizado;
- parâmetros da busca.

Não usar pesquisa aberta na web como autoridade jurídica dentro do fluxo decisório. Conteúdo externo continua não confiável até validação de origem, atualidade e pertinência.

## 7. Avaliação por afirmação

Separar pelo menos quatro métricas:

1. **retrieval recall:** a passagem necessária foi recuperada;
2. **citation correctness:** a citação aponta para a passagem informada;
3. **claim support:** a passagem sustenta realmente a afirmação;
4. **answer quality:** a resposta é útil, completa e adequada ao pedido.

Manter conjunto dourado com casos sintéticos e anonimizados. Avaliações sobre casos reais exigem autorização e política de retenção.

## Ordem de implementação

```text
Matriz fato–prova–fonte
  -> Crítico de contradições
  -> Workspace persistente
  -> Citation gate e minutas
  -> Feedback humano
  -> Conectores oficiais
  -> Avaliação contínua
```

Matriz e crítico vêm primeiro porque todos os recursos seguintes dependem de proveniência factual confiável.

---

# Configuração do LangSmith

## O que a integração atual registra

A revisão judicial executa o grafo com:

- `run_name`: `judge-document-review`;
- tags: `judge-review` e o ambiente;
- metadata: referência SHA-256 truncada do processo, quantidade de documentos e modelo;
- `run_id`: o mesmo UUID devolvido pela API em `trace_id`.

O código relevante está em:

- `backend/app/observability.py`;
- `backend/app/services/judge.py`;
- `backend/app/config.py`.

LangGraph e LangChain enviam os traces automaticamente quando as variáveis abaixo estão habilitadas.

## 1. Criar projeto e chave

1. Entre no LangSmith.
2. Crie uma API key no workspace que receberá os traces.
3. Escolha projetos separados por ambiente, por exemplo:
   - `enter-os-dev`;
   - `enter-os-staging`;
   - `enter-os-prod`.
4. Se a chave for vinculada a múltiplos workspaces, copie também o workspace ID.

Nunca versione API keys nem coloque a chave em imagens Docker.

## 2. Configuração local

Copie o template:

```bash
cp backend/.env.example backend/.env
```

Edite `backend/.env`:

```env
OPENAI_API_KEY=sua_chave_openai
OPENAI_MODEL=gpt-5.4-mini

LANGSMITH_TRACING=true
LANGSMITH_API_KEY=sua_chave_langsmith
LANGSMITH_PROJECT=enter-os-dev
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_WORKSPACE_ID=
```

Use `LANGSMITH_WORKSPACE_ID` quando a API key exigir seleção explícita de workspace.

Endpoints SaaS:

```env
# Estados Unidos
LANGSMITH_ENDPOINT=https://api.smith.langchain.com

# Região europeia
LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com
```

Use o endpoint da região em que a conta foi criada; não altere apenas por proximidade geográfica.

O tracing somente fica ativo quando `LANGSMITH_TRACING=true` **e** `LANGSMITH_API_KEY` não está vazia. A resposta da API expõe `tracing_enabled` para confirmar essa decisão de configuração.

## 3. Iniciar a aplicação

Com Docker:

```bash
cd backend
docker compose up --build
```

Ou localmente:

```bash
cd backend
uv sync --locked
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Faça uma chamada a `POST /v1/judge/reviews`. Depois:

1. copie `trace_id` da resposta;
2. abra o projeto informado em `langsmith_project`;
3. procure a execução `judge-document-review` pelo run ID;
4. confirme os nós do grafo, ferramentas, latência, erros e modelo.

Uma execução que falha também deve manter o mesmo `trace_id` nos logs locais para correlação.

## 4. Configuração recomendada por ambiente

| Ambiente | Projeto | Dados | Política recomendada |
|---|---|---|---|
| Desenvolvimento | `enter-os-dev` | Casos sintéticos | Tracing habilitado para depuração |
| Staging | `enter-os-staging` | Sintéticos ou anonimizados | Avaliações e comparação de prompts/modelos |
| Produção | `enter-os-prod` | Dados autorizados | Acesso restrito, redaction e retenção aprovadas antes de habilitar |

## 5. Alerta de confidencialidade

**A configuração atual não redige automaticamente inputs e outputs do trace.** Embora a metadata use uma referência anonimizada do número do processo, o trace automático pode conter prompts, respostas de ferramentas e texto extraído dos documentos.

Portanto:

- use apenas os casos sintéticos deste repositório durante desenvolvimento;
- não habilite LangSmith SaaS para processos reais antes de implementar redaction e aprovar região, acesso e retenção;
- não envie CPF, conta, nome, número bruto do processo ou PDF completo como tag/metadata;
- prefira IDs internos opacos;
- mantenha decisões, feedback e resultados no PostgreSQL, não apenas no LangSmith.

Para produção, implementar um `langsmith.Client` com `hide_inputs` e `hide_outputs`, ou usar `tracing_context` com inputs/outputs removidos para tenants sensíveis. A metadata operacional pode permanecer, desde que siga uma allowlist sem PII.

## 6. Tags e metadata seguras

Allowlist recomendada:

```text
environment
case_reference anonimizada
document_count
model
model_version
policy_version
prompt_version
node_name
review_outcome
```

Nunca incluir em tags ou metadata:

```text
nome
CPF
conta bancária
número bruto do processo
texto dos documentos
pergunta contendo dados pessoais
```

## 7. Diagnóstico

### `tracing_enabled` retorna `false`

Verifique se ambos estão configurados:

```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=valor_nao_vazio
```

Reinicie o processo após alterar `.env`.

### A API retorna `tracing_enabled=true`, mas o trace não aparece

Confira:

- projeto correto em `LANGSMITH_PROJECT`;
- endpoint correspondente à região da conta;
- `LANGSMITH_WORKSPACE_ID` para chave com múltiplos workspaces;
- permissões e validade da API key;
- saída de rede HTTPS do container;
- busca pelo `trace_id` devolvido pela API.

Em scripts curtos, aguarde o envio assíncrono com `wait_for_all_tracers()`. O servidor Uvicorn normalmente permanece ativo tempo suficiente para o envio em background.

### LangSmith está indisponível

A observabilidade não deve virar dependência do resultado jurídico. Monitore a falha de exportação, mas preserve o processamento e a persistência de negócio no PostgreSQL.

## Referências oficiais

- [LangSmith — tracing com LangChain](https://docs.langchain.com/langsmith/trace-with-langchain)
- [LangSmith — tracing com LangGraph](https://docs.langchain.com/langsmith/trace-with-langgraph)
- [LangSmith — mascarar inputs e outputs](https://docs.langchain.com/langsmith/mask-inputs-outputs)
- [LangSmith — tracing condicional](https://docs.langchain.com/langsmith/conditional-tracing)
