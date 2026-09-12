# Análise das entregas do Hackathon UFMG 2026

## Resumo executivo

A planilha `Entregas Hackathon UFMG.xlsx` contém 13 registros e 10 repositórios públicos únicos, correspondentes aos grupos 1 a 10. Todos os 10 repositórios foram inspecionados em 12/09/2026, incluindo a árvore de arquivos, documentação e os principais módulos de política, precificação, interface e monitoramento.

Esta análise é uma revisão estática. Os projetos não foram executados e as métricas declaradas nos READMEs não foram reproduzidas. Sempre que uma métrica aparece abaixo, ela está identificada como declaração do próprio repositório.

Os projetos convergem em cinco ideias:

1. usar UF, sub-assunto, valor da causa e presença dos seis subsídios como variáveis centrais;
2. separar a previsão de risco da definição do valor de acordo;
3. exibir justificativas e evidências para o advogado, em vez de apenas uma classificação;
4. registrar a decisão humana para medir aderência;
5. comparar o custo observado com um custo esperado de litígio para estimar efetividade.

As melhores peças encontradas para reaproveitar conceitualmente no projeto EnterOS são:

- modelagem financeira e intervalos de incerteza do grupo 8;
- núcleo determinístico e rastreável do grupo 3;
- versionamento, crítica e trilha de decisão do grupo 4;
- monitoramento operacional do grupo 6;
- transparência sobre hipóteses e dados sintéticos do grupo 9;
- experiência de upload, recomendação fundamentada e revisão humana do grupo 10.

A combinação recomendada não é copiar um projeto inteiro. É manter o cálculo de decisão determinístico e auditável, usar ML para estimar probabilidades e valores, e restringir o LLM à extração e explicação com citações.

## Repositórios analisados

| Grupo | Repositório | Nome/proposta observada | Stack principal |
|---:|---|---|---|
| 1 | [DataCaio/hackathon-ufmg-2026-exit](https://github.com/DataCaio/hackathon-ufmg-2026-exit) | EXIT | Python, XGBoost, OpenAI, React/Vite |
| 2 | [gstvortiz/hackathon-ufmg-2026](https://github.com/gstvortiz/hackathon-ufmg-2026) | JurisIA | Python, Flask, CatBoost/GLM, SQLite, HTML/Tailwind |
| 3 | [hackaton-estouradores-de-batata/Hackaton](https://github.com/hackaton-estouradores-de-batata/Hackaton) | Estouradores de Batata | Next.js, TypeScript, FastAPI, SQLite, OpenAI, FAISS |
| 4 | [GilCFP/grupo_4_carona](https://github.com/GilCFP/grupo_4_carona) | Carona | TypeScript, React/Vite, Fastify, Prisma/SQLite, OpenAI |
| 5 | [bisalela/hackathon-ufmg-2026-grupo5](https://github.com/bisalela/hackathon-ufmg-2026-grupo5) | AI Agent Enter | React/Vite, Node/TypeScript, Python, OpenAI, Supabase |
| 6 | [PhPires13/hackathon-ufmg-2026-grupo6](https://github.com/PhPires13/hackathon-ufmg-2026-grupo6) | Estrangeiros | Django, Python, modelos serializados, OpenAI opcional |
| 7 | [Beloeser/hackathon-ufmg-2026-grupo7](https://github.com/Beloeser/hackathon-ufmg-2026-grupo7) | CoffeeBreakers | React, Node/Express, MongoDB, Python, OpenAI |
| 8 | [marco-fabian/hackathon-ufmg-2026-grupo8](https://github.com/marco-fabian/hackathon-ufmg-2026-grupo8) | Política de acordos com IFP | Python, FastAPI, PostgreSQL, XGBoost, OpenAI |
| 9 | [Saliv07/hackathon-ufmg-2026-grupo9](https://github.com/Saliv07/hackathon-ufmg-2026-grupo9) | Habeas Código | Flask, React/Vite, Plotly Dash, XGBoost, OpenAI |
| 10 | [Gr-moura/Hackathon-Enter-UFMG](https://github.com/Gr-moura/Hackathon-Enter-UFMG) | EanterOS | React/Vite, FastAPI, PostgreSQL/pgvector, PyTorch, OpenAI |

O link submetido pelo grupo 10 redireciona para `Gr-moura/Hackathon-Enter-UFMG`.

## Matriz comparativa

| Grupo | Regra de decisão | Sugestão de valor | Experiência do advogado | Aderência e efetividade | Principal força | Principal ressalva |
|---:|---|---|---|---|---|---|
| 1 | XGBoost; defesa quando `P(êxito) >= 0,60` | Regressor XGBoost de condenação e quantis de erro | Busca do caso, evidências, recomendação e geração de defesa | Histórico e painéis no frontend | Explicabilidade local e rascunho de defesa | Persistência operacional do monitoramento não ficou evidente |
| 2 | Compara custo esperado de acordo e defesa | GLM Gamma para acordo; perda esperada por UF | Upload de PDFs e tela Flask | SQLite com análises, feedback e KPIs | Formulação econômica clara | Backend concentra responsabilidades; parte da demonstração usa dados simulados |
| 3 | Matriz determinística por UF, sub-assunto e quantidade de documentos | Faixas de abertura, alvo e teto por risco | Inbox, tela de caso, evidências e justificativa | Entidades de resultado e dashboard | Decisão auditável e LLM fora do núcleo | Matrizes extensas codificadas manualmente |
| 4 | Workflow multiagente com calibração, crítica e score mínimo | Faixas derivadas de buckets históricos e custo judicial esperado | Tela de caso, explicação e trilha dos agentes | Política versionada, traces e dashboard | Governança e rastreabilidade | Cadeia de agentes aumenta latência, custo e pontos de falha |
| 5 | Predição multiclasses do resultado micro, com SHAP | Regressão linear explícita, limitada a 10%–60% da causa | Frontend React com fluxo de processo e relatório | Supabase para processos, documentos e análises | Integração relatório + explicação do modelo | Setup externo pesado e repositório com cópias incompletas de `node_modules` |
| 6 | Modelos de risco e custo; acordo se `P(perda) > 0,60` | `0,60 × condenação estimada` | Django integrado: upload, casos, decisão e ação | Métricas de aderência, custo, resultado e comparação seguiu/não seguiu | Monólito convencional e monitoramento detalhado | Preço não otimiza custo esperado; README referencia pipeline ausente na árvore atual |
| 7 | Compara custo esperado do acordo otimizado com defesa | Otimização numérica com curva logística de aceite | Gestão de casos, documentos, chat e dashboard admin | MongoDB, eventos e comparação modelo × advogado | Tenta otimizar a negociação, não só prever sentença | Curva de aceite e custos usam parâmetros assumidos, não dados reais de recusas |
| 8 | Custo esperado + três perfis de risco + overrides de evidência | Quantis de condenação e `alpha` de acordos históricos | Análise detalhada, IFP e decisão final do escritório | PostgreSQL e dashboard histórico | Melhor tratamento de incerteza e impacto financeiro | Taxa de aceite é proxy treinada apenas com acordos aceitos |
| 9 | Regras críticas; XGBoost apenas na zona cinzenta | Base de 30% da causa com ajustes e limites | App único com recomendação e dashboards | Muitos KPIs; hipóteses sintéticas identificadas | Transparência sobre decisões e suposições | Economia depende de taxa de aceite contrafactual configurável |
| 10 | RN1 PyTorch + RAG do processo + classificador LLM; fallback por threshold | Valuador LLM dentro dos limites da política | Evidence Hub, Decision Lab, citações e revisão humana | PostgreSQL, aderência por advogado, economia e drift | Experiência completa e fundamentação documental | LLM participa da decisão final; política contém flags juridicamente invertidas |

## Análise por grupo

### Grupo 1 — EXIT

**O que construiu**

- Classificador XGBoost para estimar a chance de êxito da defesa.
- Regressor XGBoost separado para estimar condenação e construir uma faixa de acordo.
- Explicações locais usando contribuições do booster, no estilo SHAP.
- Priorização dos documentos presentes e dos subsídios ausentes mais importantes.
- Geração de estratégia e rascunho de defesa por OpenAI, com exportação em PDF.
- Frontend React com perfis de advogado e banco.

**Política**

As variáveis do classificador são UF, sub-assunto, valor da causa e os seis indicadores de subsídio. A decisão é defesa quando a probabilidade de êxito é pelo menos 60%; abaixo disso, acordo. A resposta inclui probabilidade, confiança, fatores relevantes e documentos prioritários.

**Valor de acordo**

O regressor prevê a condenação. A faixa de negociação usa quantis robustos dos resíduos históricos, e o alvo é ajustado pela probabilidade de êxito da defesa e pela cobertura documental.

**Monitoramento**

O frontend registra decisões em estado React e apresenta visões para advogado e banco. Na árvore inspecionada, não ficou evidente uma API transacional própria para persistir toda a trilha, negociação e resultado real.

**O que vale aproveitar**

- separar classificador de risco e modelo de severidade;
- explicação local dos fatores do caso;
- transformar a recomendação de defesa em um artefato imediatamente útil.

**Arquivos centrais inspecionados**

- `src/policy/politicaDecisao.py`
- `src/policy/politicaAcordo.py`
- `src/policy/politicaDefesa.py`
- `src/interface/interface-front/src/App.jsx`

### Grupo 2 — JurisIA

**O que construiu**

- Aplicação Flask com upload e classificação dos documentos.
- Modelo CatBoost para probabilidade de êxito sem acordo.
- Estimador da fração de condenação por UF.
- GLM Gamma para estimar o custo de acordo.
- SQLite para análises, feedback e relatórios gerenciais.
- OpenAI opcional para justificativa e relatório em linguagem natural.

**Política**

A lógica compara duas alternativas:

```text
custo_defesa = (1 - P(êxito sem acordo | X)) × E[alpha | UF] × valor_causa
custo_acordo = E(valor pago | acordo, valor_causa)
recomendação = alternativa de menor custo esperado
```

É uma das formulações mais claras do problema como decisão econômica, em vez de mera classificação de sentença.

**Monitoramento**

As tabelas `analises` e `analises_feedback` registram recomendação, valores, aderência, resultado real e valor pago. O painel calcula acurácia, aderência e efetividade. Há também suporte a dados simulados para demonstrar a interface.

**O que vale aproveitar**

- comparação direta entre alternativas econômicas;
- OpenAI opcional, sem bloquear a decisão mínima;
- persistência simples dos dados necessários para fechar o ciclo.

**Arquivos centrais inspecionados**

- `docs/architecture.md`
- `src/policy/app/inference.py`
- `src/policy/app/app.py`
- `src/interface/management_report.py`

### Grupo 3 — Estouradores de Batata

**O que construiu**

- Frontend Next.js e API FastAPI.
- Política determinística versionada.
- Entidades para caso, subsídios, recomendação e resultado.
- LLM usado nas bordas: extração, julgamento auxiliar e explicação.
- Recuperação por embeddings/FAISS disponível, mas fora do caminho crítico da regra.
- Dashboard e registro de resultados.

**Política**

A V5 usa matrizes por UF, sub-assunto e quantidade de documentos para calcular chance de sucesso, peso documental e faixas de acordo. Há regras explícitas para contradições, falta de valor da causa e revisão manual. O `decision_engine` produz um trace da política junto da recomendação.

**Valor de acordo**

A política calcula abertura, alvo e teto, com descontos por UF e risco. `Decimal` é usado nos cálculos financeiros.

**Monitoramento**

O modelo de dados contempla resultado e o dashboard agrega o histórico. A separação entre decisão determinística e explicação generativa facilita auditoria.

**O que vale aproveitar**

- política determinística com trace completo;
- LLM sem autoridade para alterar silenciosamente a decisão;
- abertura, alvo e teto em vez de um único número.

**Riscos observados**

- matrizes grandes e rígidas exigem processo de recalibração claro;
- o repositório contém arquivos aparentemente alheios ao desafio, inclusive documentos com aparência de dados de pessoal; revisar higiene e privacidade antes de reutilizar qualquer material.

**Arquivos centrais inspecionados**

- `docs/architecture.md`
- `src/api/app/services/agreement_policy_v5.py`
- `src/api/app/services/decision_engine.py`

### Grupo 4 — Carona

**O que construiu**

- Aplicação full TypeScript com React, Fastify, Prisma e SQLite.
- Workflow offline para calibrar e publicar versões da política.
- Workflow online para analisar um caso.
- Agentes especializados em extração, crítica, risco, proposta e explicação.
- Recuperação de casos similares, ferramentas de pesquisa e traces de execução.

**Política**

O calibrador divide dados de forma determinística, cria buckets por documentos, faixa de valor e perfil do caso, calcula taxa de perda e mediana de custo, propõe regras, critica a proposta e só publica quando o score atende ao limiar configurado. Na análise online, fatos extraídos são criticados antes da recomendação.

**Valor de acordo**

As faixas são derivadas de buckets históricos e do custo judicial esperado. A regra possui fallback determinístico quando o custo esperado de defesa excede o alvo de acordo.

**Monitoramento**

A política é versionada e cada etapa dos workflows é rastreável. Isso permite explicar tanto a origem da política quanto a decisão de um caso.

**O que vale aproveitar**

- versionar política, modelo e decisão juntos;
- crítica explícita dos fatos extraídos;
- divisão temporal/determinística para avaliar regras antes de publicar;
- trace por etapa.

**Risco observado**

A cadeia multiagente é tecnicamente interessante, mas aumenta latência, custo, não determinismo e superfície de falha. A regra financeira deve continuar independente dessa orquestração.

**Arquivos centrais inspecionados**

- `backend/ARCHITECTURE_FLOW.md`
- `backend/domain/policy-calibration/logic.ts`
- `backend/domain/case-decision/logic.ts`

### Grupo 5 — AI Agent Enter

**O que construiu**

- Frontend React/Vite para advogado e administrador.
- Backend Node/TypeScript integrado à OpenAI e Supabase.
- Extração de PDFs e pipeline Python para inferência.
- Modelo multiclasses para improcedência, parcial procedência e procedência.
- SHAP, com fallback para importância global das features.
- Geração de relatório LaTeX/PDF.

**Política**

O modelo calcula `P(não êxito)` somando as probabilidades de parcial procedência e procedência. A camada de agente combina essa previsão com checklist documental e justificativa em linguagem natural.

**Valor de acordo**

O cálculo é uma regressão linear explícita:

```text
-250,11 + 0,303 × valor_causa + coeficiente_UF + coeficientes de sub-assunto/documentos
```

O resultado é limitado entre 10% e 60% do valor da causa.

**Monitoramento**

O Supabase armazena perfis, processos, documentos e análises. O setup exige projeto externo, usuários de Auth e chaves de serviço. O login demonstrado no frontend é local/mockado.

**O que vale aproveitar**

- fórmula de preço inspecionável;
- relatório de decisão como artefato de trabalho;
- fallback quando SHAP não estiver disponível.

**Riscos observados**

- muitos pré-requisitos externos para uma demonstração;
- duas pastas `node_modules_incomplete_*` foram commitadas, aumentando ruído e risco de dependências inconsistentes;
- a regra linear precisa de validação econômica, não apenas ajuste estatístico.

**Arquivos centrais inspecionados**

- `src/AI_Agent_Enter/agent.ts`
- `src/AI_Agent_Enter/main.py`
- `src/AI_Agent_Enter/predict.py`
- `src/AI_Agent_Enter/settlementCalculator.ts`
- `SETUP.md`

### Grupo 6 — Estrangeiros

**O que construiu**

- Aplicação Django integrada, com upload de PDFs, lista de casos, detalhe e decisão do advogado.
- Modelo de risco para `P(perda)`.
- Modelo de custo para condenação esperada.
- Engenharia de features documentais com peso por tipo de subsídio.
- Insight textual por OpenAI, com fallback determinístico.
- Painéis de aderência e efetividade.

**Política**

A recomendação é acordo quando `P(perda) > 0,60`; caso contrário, defesa. O custo esperado é calculado como `P(perda) × condenação estimada`, mas a decisão usa diretamente o threshold de probabilidade.

**Valor de acordo**

Quando recomenda acordo, usa `0,60 × condenação estimada`. É simples e fácil de explicar, porém não compara a oferta com custo de defesa, chance de aceite ou alçada.

**Monitoramento**

É um dos módulos mais completos da amostra. Mede:

- aderência à ação e à faixa de valor;
- desvio médio do valor;
- taxa de êxito da defesa;
- aceitação e conversão de acordos;
- custo observado versus condenação esperada;
- comparação entre casos que seguiram e não seguiram a recomendação;
- matriz recomendação × ação tomada.

**O que vale aproveitar**

- schema de ação e resultado;
- comparação entre aderentes e não aderentes;
- uso do LLM apenas para explicar números já calculados.

**Risco observado**

O README descreve `legalapp/agent/pipeline.py`, mas esse caminho não apareceu na árvore pública inspecionada e retornou 404. O fluxo funcional observado está implementado diretamente em `views.py` e `ml_service.py`.

**Arquivos centrais inspecionados**

- `src/estrangeirosplatform/legalapp/views.py`
- `src/estrangeirosplatform/legalapp/ml_service.py`
- `SETUP.md`

### Grupo 7 — CoffeeBreakers

**O que construiu**

- Frontend React e backend Node/Express/MongoDB.
- Serviço Python para previsão e otimização.
- Gestão de casos, documentos, usuários e eventos.
- Assistente de chat com OpenAI.
- Dashboard administrativo com comparação modelo × advogado.

**Política**

O modelo estima chance de vitória e, a partir dela, perda esperada. A recomendação compara o custo esperado de defender com o custo esperado de tentar acordo.

**Valor de acordo**

A oferta é otimizada numericamente. A probabilidade de aceite é modelada por uma sigmoide em torno de `alpha × perda esperada`, e a função objetivo é:

```text
P(aceite) × oferta + (1 - P(aceite)) × (perda esperada + custo adicional)
```

Essa formulação é conceitualmente forte porque tenta escolher o preço, e não apenas prever um valor histórico.

**Monitoramento**

O dashboard registra recomendação, decisão do advogado, eventos, aderência por profissional e distribuição de decisões.

**Riscos observados**

- `alpha`, inclinação da sigmoide, custo adicional e custo de defesa possuem defaults assumidos;
- a base fornecida não contém propostas recusadas, portanto não identifica uma curva real de aceite;
- o indicador de economia do dashboard usa, em parte, diferença absoluta entre valor real e sugerido, que não representa necessariamente economia.

**Arquivos centrais inspecionados**

- `backend/ml/analise.py`
- `backend/ml/models/Acordo/train_acordo_gp.py`
- `backend/controllers/dashboardController.js`

### Grupo 8 — IFP e políticas por perfil de risco

**O que construiu**

- Pipeline Python com modelos XGBoost para risco e valor.
- Calibração de probabilidade.
- Regressão de quantis para faixa de condenação.
- Índice de Força Probatória (IFP), considerando presença e qualidade da prova.
- Três políticas: Conservadora, Moderada e Arriscada.
- FastAPI, PostgreSQL e tela de análise com persistência da decisão do escritório.

**Política**

O custo esperado de defesa combina probabilidade de perda, valor de condenação e custo processual. O IFP v2 distribui 60 pontos para presença documental e 40 para qualidade. Há overrides para documentação forte, documentação fraca e sinais de fraude.

**Valor de acordo**

O modelo estima condenação condicional à perda e quantis `q10/q50/q90`. Um fator `alpha` selecionado pelo perfil de risco é aplicado ao custo esperado, produzindo valores distintos para as três políticas.

**Métricas declaradas pelo repositório, não reproduzidas**

- AUC do classificador: 0,919;
- ECE após calibração: 0,026;
- MAE do modelo de condenação: R$ 2.449;
- R² do modelo de condenação: 0,563;
- cobertura empírica do intervalo de 80%: 73,4%.

**Monitoramento**

A decisão final do escritório é persistida em `decisao_escritorio`. O dashboard mostra histórico, risco, documentos, IFP e políticas. A API também mantém rotas antigas baseadas em fixtures, paralelas às rotas PostgreSQL.

**O que vale aproveitar**

- calibração de probabilidades;
- intervalo de condenação, não apenas ponto médio;
- qualidade da prova, não apenas presença do arquivo;
- diferentes apetites de risco representados explicitamente.

**Riscos observados**

- o modelo de `alpha` usa apenas 280 acordos concluídos;
- sem observações de propostas recusadas, a chamada `taxa_aceite_estimada` é um proxy, não uma probabilidade de aceite identificada;
- pesos do IFP e overrides precisam ser validados pelo jurídico e por backtest temporal.

**Arquivos centrais inspecionados**

- `docs/modelo.md`
- `docs/politica-acordos.md`
- `docs/api-analise.md`
- `src/backend/motor_decisao.py`
- `src/backend/ifp_v2.py`

### Grupo 9 — Habeas Código

**O que construiu**

- Flask, React/Vite e Plotly Dash servidos em uma aplicação integrada.
- Motor híbrido: regras determinísticas para casos claros e XGBoost na zona cinzenta.
- Assistentes OpenAI para texto, voz e imagem.
- Dashboard amplo de aderência e efetividade.
- Documento `DECISOES.md` com hipóteses e limitações explícitas.

**Política**

As regras críticas usam contrato, extrato e comprovante de crédito:

- dossiê não conforme: acordo;
- zero ou um documento crítico: acordo;
- três documentos críticos: defesa;
- dois documentos críticos: XGBoost;
- AM/AP com no máximo dois documentos críticos: acordo.

**Valor de acordo**

Parte de 30% do valor da causa e aplica ajustes de pontos percentuais conforme força documental, dossiê e risco da UF. Também calcula abertura e teto de negociação.

**Métricas declaradas pelo repositório, não reproduzidas**

- AUC do modelo: 0,91;
- economia anual potencial: R$ 64 milhões em simulação;
- 65 testes automatizados.

**Monitoramento**

A demonstração cria dimensões sintéticas de advogados, escritórios e datas. A taxa de aceite contrafactual é um parâmetro ajustável, com default de 40%. O repositório documenta essas hipóteses em vez de apresentá-las como observações reais.

**O que vale aproveitar**

- regras fortes antes do ML;
- documentação explícita das hipóteses H1–H14;
- separação visual entre aderência e efetividade;
- análise de sensibilidade da taxa de aceite.

**Risco observado**

A economia projetada muda materialmente com a taxa de aceite assumida. Não deve ser apresentada como economia realizada.

**Arquivos centrais inspecionados**

- `docs/politica_acordo.md`
- `docs/DECISOES.md`
- `src/policy/engine.py`
- `src/policy/pricing.py`

### Grupo 10 — EanterOS

**O que construiu**

- Frontend React com Evidence Hub, Decision Lab e Monitoring.
- API FastAPI com PostgreSQL/pgvector.
- Rede neural PyTorch para probabilidade de derrota.
- RAG limitado aos documentos do próprio processo.
- Classificador e valuador GPT com Structured Outputs.
- Revisão humana com aceitar, ajustar ou recusar.
- Persistência de análise, proposta, decisão do advogado e métricas.

**Política**

O pipeline executa:

1. extração de metadados;
2. recuperação de trechos sobre assinatura, valor, provas e fraude;
3. RN1 para probabilidade de derrota;
4. classificador LLM para acordo/defesa;
5. fallback determinístico pelo threshold da RN1 quando o LLM falha;
6. valuador LLM para casos de acordo;
7. persistência da recomendação e decisão humana.

Os thresholds são 0,60 e 0,85. Recomendações abaixo de 0,85 exigem supervisão.

**Valor de acordo**

A política define piso de 30%, teto de 70%, piso absoluto de R$ 1.500 e teto absoluto de R$ 50.000. O valuador LLM usa trechos recuperados e calcula alvo, intervalo e custo estimado de litigar.

**Monitoramento**

O backend calcula aceitação da recomendação por advogado, economia estimada, casos de baixa confiança e drift da confiança média. Um script fornece dados sintéticos para a demonstração.

**O que vale aproveitar**

- experiência do advogado orientada a evidências;
- citações dos trechos que sustentam a recomendação;
- exigência de justificativa para grande desvio de valor;
- fallback quando OpenAI ou o modelo falham.

**Riscos observados**

- a decisão final pode ser alterada pelo LLM, reduzindo reprodutibilidade;
- `n_casos_similares` é persistido como zero no pipeline atual; o RAG observado recupera trechos do próprio processo, não precedentes históricos;
- aderência global conta somente ação `ACEITAR`, tratando ajustes e recusas de forma simplificada;
- `policy.yaml` e `docs/policy.md` listam “assinatura evidentemente falsificada” e “ausência total de comprovante” como flags que forçam defesa. Isso contradiz o próprio prompt do classificador, que trata essas condições como fortes sinais para acordo. A configuração precisa ser corrigida ou removida.

**Arquivos centrais inspecionados**

- `src/back/app/services/ai/pipeline.py`
- `src/back/app/services/ai/llm_classifier.py`
- `src/back/app/services/ai/valuator.py`
- `src/back/app/services/metrics/aggregator.py`
- `src/back/policy.yaml`
- `docs/policy.md`

## Padrões comuns encontrados

### Variáveis

Quase todos usam o mesmo conjunto mínimo:

- UF;
- sub-assunto;
- valor da causa;
- contrato;
- extrato;
- comprovante de crédito;
- dossiê;
- demonstrativo da dívida;
- laudo referenciado.

A melhoria mais relevante sobre flags binárias aparece no grupo 8, que tenta medir qualidade da evidência, e no grupo 4, que procura contradições e correspondência de valores.

### Famílias de decisão

1. **Classificação direta:** grupos 1, 5, 6 e 10 estimam êxito/perda e aplicam um threshold.
2. **Valor esperado:** grupos 2, 7 e 8 comparam custos econômicos das alternativas.
3. **Regras determinísticas:** grupos 3 e 9 codificam cenários claros e auditáveis.
4. **Multiagente:** grupo 4 usa agentes para calibrar e criticar a política.
5. **Híbrida com LLM:** grupo 10 deixa o LLM participar da decisão, com fallback quantitativo.

Para produção, a melhor combinação é: regras determinísticas para invariantes jurídicos, modelos calibrados para risco e severidade, e comparação por valor esperado.

### Famílias de precificação

| Abordagem | Grupos | Observação |
|---|---|---|
| Regressão de condenação + quantis | 1 e 8 | Captura incerteza; exige modelo condicional bem calibrado |
| Menor custo esperado | 2 | Formulação econômica simples e correta |
| Faixas codificadas por risco | 3 e 4 | Explicável, mas precisa de recalibração versionada |
| Regressão linear com limites percentuais | 5 | Auditável, porém rígida |
| Percentual da condenação prevista | 6 | Fácil de explicar, mas não otimiza a decisão |
| Otimização com curva de aceite | 7 | Objetivo correto; parâmetros de aceite ainda não identificados |
| Percentual da causa com ajustes | 9 | Muito simples e demonstrável; menos responsivo ao valor esperado |
| Valuador LLM com guardrails | 10 | Flexível, porém não determinístico |

### Lacuna estrutural dos dados

A base histórica contém sentenças e alguns acordos concluídos, mas não contém o conjunto completo de tentativas de negociação, incluindo:

- valor de cada proposta;
- ordem das propostas;
- contraproposta;
- aceite ou recusa;
- tempo até a resposta;
- perfil do advogado/escritório;
- custo processual realizado.

Consequência: nenhum grupo consegue estimar uma função causal ou observacional robusta de `P(aceite | valor, caso)`. Modelos de aceite, taxas contrafactuais e economia simulada dependem de hipóteses. O sistema deve rotular esses números como **estimados**, nunca como realizados.

## O que adotar no projeto EnterOS

### 1. Núcleo de decisão

Usar uma equação explícita:

```text
custo_defesa = P(perda | caso) × E(condenação | perda, caso) + custo_processual
custo_acordo = valor_oferta + custo_operacional_acordo
```

A decisão compara as alternativas sob uma política de risco versionada. Overrides jurídicos são determinísticos e executados antes do modelo.

### 2. Evidência

Separar três conceitos:

- presença do arquivo;
- qualidade e coerência do conteúdo;
- contradições entre autos e subsídios.

Toda variável extraída deve guardar documento, página, trecho, método e confiança.

### 3. Valor de negociação

Retornar três valores:

- abertura;
- alvo recomendado;
- teto de alçada.

Enquanto não houver dados de propostas recusadas, calibrar esses valores por risco e custo esperado, sem afirmar uma taxa de aceite aprendida. Registrar cada tentativa permitirá treinar essa curva depois.

### 4. Papel do LLM

Usar LLM para:

- classificar e extrair fatos dos documentos;
- encontrar trechos de suporte;
- explicar a decisão em linguagem jurídica acessível;
- apontar inconsistências para revisão.

Não usar LLM como autoridade final para alterar probabilidade, regra ou preço. Isso preserva reprodutibilidade, auditoria e controle de alçada.

### 5. Dados operacionais mínimos

Persistir entidades separadas:

```text
Case
Document + Evidence
Recommendation(policy_version, model_version, inputs, outputs, trace)
LawyerDecision(action, value, reason, timestamp)
NegotiationAttempt(value, result, counteroffer, timestamp)
JudicialOutcome(result, condemnation, costs, timestamp)
```

Sem `NegotiationAttempt` e `JudicialOutcome`, o dashboard mede apenas adesão à ferramenta, não efetividade econômica.

### 6. Monitoramento

Separar três blocos no dashboard:

- **observado:** adesão, aceite, condenação e custo efetivamente registrados;
- **estimado:** perda esperada, economia contrafactual e risco;
- **qualidade do modelo:** calibração, drift, cobertura de intervalos e performance por UF/sub-assunto.

Nunca somar economia estimada e realizada no mesmo KPI.

## O que evitar

- classificar “acordo” histórico como se fosse sentença judicial;
- treinar probabilidade de aceite apenas com acordos aceitos;
- usar diferença absoluta entre oferta e valor pago como economia;
- apresentar dados sintéticos como comportamento real de advogados;
- deixar estado de auditoria somente no frontend;
- usar categoria ordinal para UF sem testar alternativas apropriadas;
- colocar uma cadeia de agentes ou RAG no caminho crítico sem fallback;
- permitir que o LLM ultrapasse limites de alçada;
- manter política contraditória entre configuração, prompt e código;
- commitar dados sensíveis, modelos sem proveniência ou dependências vendorizadas incompletas.

## Referência rápida por dimensão

| Dimensão | Referência mais útil | Motivo |
|---|---|---|
| Política econômica | Grupo 8 | Risco calibrado, severidade, quantis e perfis de risco |
| Simplicidade econômica | Grupo 2 | Comparação direta de custos esperados |
| Auditabilidade determinística | Grupo 3 | Trace e separação entre regra e LLM |
| Governança/versionamento | Grupo 4 | Calibração, crítica, score e publicação da política |
| Monitoramento operacional | Grupo 6 | Aderência, resultado, custo e comparação seguiu/não seguiu |
| Transparência de hipóteses | Grupo 9 | Premissas documentadas e contrafactual ajustável |
| Experiência do advogado | Grupo 10 | Upload guiado, trechos de evidência e HITL |
| Artefato de defesa | Grupo 1 | Rascunho de defesa gerado a partir da recomendação |

## Conclusão

O diferencial competitivo não está em adicionar mais agentes ou mais modelos. Está em fechar o ciclo operacional:

1. extrair fatos com evidência;
2. estimar risco e custo com incerteza calibrada;
3. aplicar uma política determinística e versionada;
4. entregar abertura, alvo e teto ao advogado;
5. registrar decisão, negociação e resultado;
6. recalibrar a política com resultados observados.

Para o projeto EnterOS, a direção mais segura é combinar a matemática do grupo 8, a auditabilidade do grupo 3, a governança do grupo 4, o monitoramento do grupo 6 e a UX do grupo 10, mantendo o LLM fora do cálculo final.