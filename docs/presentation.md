# EnterOS — Pitch final

> Duração máxima: 15 minutos. Substitua os campos marcados antes da entrega.

## Link da apresentação

**Apresentação publicada:** [adicionar link]

## Mensagem central

O EnterOS transforma documentos dispersos em uma decisão jurídica rastreável: recomenda acordo ou defesa, calcula uma faixa financeira, orienta o advogado e mostra ao banco a aderência e o resultado de cada decisão.

## Roteiro de 15 minutos

| Tempo | Tela | Mensagem |
|---|---|---|
| 0:00–1:15 | Problema | O Banco UFMG recebe milhares de ações repetitivas. Cada decisão inconsistente aumenta custo, risco e dificuldade de governança. |
| 1:15–2:15 | Proposta | Um workspace único conecta autos, evidências, análise estatística, política de acordo e acompanhamento bancário. |
| 2:15–4:15 | Política | O risco combina histórico judicial, perfil do processo e força documental. A política converte risco e exposição em defesa, revisão ou acordo com abertura, alvo e teto. |
| 4:15–7:30 | Experiência do advogado | Abrir processo, anexar documentos, conversar com citações clicáveis, revisar recomendação e registrar uma decisão definitiva. |
| 7:30–9:45 | Experiência do banco | Receber a decisão, executar revisão independente, acompanhar aderência e registrar o resultado da causa. |
| 9:45–11:30 | Impacto financeiro | Comparar condenação-base e custo efetivo; medir economia acumulada e taxa de aceitação apenas sobre decisões concluídas. |
| 11:30–13:15 | Arquitetura e segurança | Explicar os fluxos de ingestão, análise, streaming, persistência e auditoria usando [`architecture.svg`](architecture.svg). |
| 13:15–14:15 | Limitações | Qualidade da recomendação depende dos dados e documentos disponíveis; o modelo apoia, não substitui, o julgamento profissional. |
| 14:15–15:00 | Próximos passos e fechamento | Calibração contínua, autenticação corporativa, avaliação prospectiva e implantação monitorada. |

## Estrutura sugerida dos slides

### 1. Decisões repetitivas, impacto não repetitivo

- Cerca de 15 mil novos processos por mês.
- Aproximadamente 5 mil casos de não reconhecimento de empréstimo.
- Problema operacional: decidir, executar e medir uma política em escala.

### 2. Uma decisão rastreável de ponta a ponta

- Autos e subsídios organizados por processo.
- Chat documental com ferramentas em tempo real.
- Citações que abrem o PDF na página consultada.
- Análise estratégica e decisão persistida.

### 3. Política orientada por risco e evidência

- Ensemble estatístico para probabilidade de perda.
- Força documental calculada pelos subsídios presentes.
- Exposição financeira e custo esperado da defesa.
- Faixa de acordo com abertura, alvo e teto.

### 4. Jornada do advogado

1. Seleciona ou cria o processo.
2. Anexa os documentos disponíveis.
3. Acompanha a análise durante o upload.
4. Consulta os autos pelo chat.
5. Revisa a recomendação e os fundamentos.
6. Submete acordo, defesa ou revisão humana.

### 5. Jornada do banco

- Decisões recebidas em uma fila operacional.
- Revisão independente automática.
- Aderência entre recomendação e decisão do advogado.
- Resultado favorável ou desfavorável após o prosseguimento.
- Efeito financeiro consolidado por período.

### 6. Demonstração

Use o roteiro de [`demo_video.md`](demo_video.md). Na apresentação ao vivo, priorize um único processo completo em vez de navegar por funcionalidades isoladas.

### 7. Valor financeiro

- Condenação-base: valor da causa multiplicado pela razão histórica de condenação.
- Economia de acordo: condenação-base menos proposta aceita.
- Economia de defesa favorável: condenação-base preservada.
- Custo desfavorável: condenação e custos atribuídos ao desfecho.
- Métricas agregadas usam apenas decisões encaminhadas e concluídas.

### 8. Arquitetura e governança

Apresente [`architecture.svg`](architecture.svg) destacando:

- separação entre experiências do advogado e do banco;
- processamento documental e ferramentas de consulta;
- modelo estatístico e política de decisão;
- persistência de processos, análises, decisões e resultados;
- streaming SSE, trilha de auditoria e observabilidade.

### 9. Limitações conhecidas

- Dados históricos podem carregar vieses e mudanças de distribuição.
- Documentos ausentes reduzem a força probatória.
- OCR e extração podem exigir validação em arquivos degradados.
- Probabilidades precisam de calibração contínua com resultados reais.
- A recomendação é apoio à decisão jurídica, não decisão autônoma.

### 10. Próximos 30 dias

- Autenticação e autorização por perfil.
- Avaliação prospectiva com grupo de controle.
- Monitoramento de deriva e recalibração.
- Filas resilientes para análise documental em escala.
- Integração com sistemas corporativos de processos e documentos.

## Fechamento

> O EnterOS não entrega apenas uma recomendação. Entrega evidência, decisão operacional e aprendizado financeiro no mesmo fluxo.

## Checklist antes da apresentação

- [ ] Inserir o link final da apresentação.
- [ ] Confirmar que o ambiente da demonstração está acessível.
- [ ] Preparar um processo com documentos e análise concluída.
- [ ] Ensaiar o fluxo completo em até 15 minutos.
- [ ] Conferir os números financeiros exibidos no dia.
- [ ] Manter o vídeo de demonstração disponível como contingência.
