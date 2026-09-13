"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import {
  ArrowRight,
  Building2,
  Check,
  CircleAlert,
  CircleCheckBig,
  CircleX,
  Clock3,
  FileCheck2,
  RefreshCw,
  Scale,
  ShieldCheck,
  TrendingDown,
} from "lucide-react";
import { apiEventStream, apiFetch } from "@/lib/api";
import type {
  BankDashboardResponse,
  BankDecisionItem,
  BankJudgeReview,
  DecisionChoice,
} from "@/lib/types";
import styles from "./bank-dashboard.module.css";

const decisionLabels: Record<DecisionChoice, string> = {
  agreement: "Acordo",
  defense: "Defesa",
  human_review: "Revisão humana",
};

const adherenceLabels: Record<BankDecisionItem["adherence_status"], string> = {
  adherent: "Aderente",
  justified: "Justificada",
  divergent: "Divergente",
};

const judgeDispositionLabels: Record<BankJudgeReview["disposition"], string> = {
  grant_claim: "Procedência",
  deny_claim: "Improcedência",
  partial_grant: "Procedência parcial",
  insufficient_evidence: "Prova insuficiente",
};
const OUTCOME_SIMULATION_MS = 3_000;


function formatCurrency(value: number): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatPercent(value: number): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "percent",
    maximumFractionDigits: 1,
  }).format(value);
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "America/Sao_Paulo",
  }).format(new Date(value));
}

function formatMonth(value: string): string {
  const [year, month] = value.split("-").map(Number);
  return new Intl.DateTimeFormat("pt-BR", { month: "short", year: "2-digit" })
    .format(new Date(Date.UTC(year, month - 1, 1)))
    .replace(" de ", " ");
}

export function BankDashboard() {
  const [dashboard, setDashboard] = useState<BankDashboardResponse | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [judgeReview, setJudgeReview] = useState<BankJudgeReview | null>(null);
  const [approvingId, setApprovingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const requestedReviewsRef = useRef(new Set<string>());

  const loadDashboard = useCallback(async (background = false) => {
    if (background) setRefreshing(true);
    try {
      const result = await apiFetch<BankDashboardResponse>("/v1/bank/dashboard", {
        cache: "no-store",
      });
      setDashboard(result);
      setSelectedId((current) =>
        current && result.decisions.some((decision) => decision.id === current)
          ? current
          : result.decisions[0]?.id ?? null,
      );
      setError(null);
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Não foi possível carregar as decisões dos advogados.",
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    const initialTimer = window.setTimeout(() => void loadDashboard(), 0);
    const refreshTimer = window.setInterval(() => void loadDashboard(true), 15_000);
    return () => {
      window.clearTimeout(initialTimer);
      window.clearInterval(refreshTimer);
    };
  }, [loadDashboard]);

  const selectedDecision = useMemo(
    () => dashboard?.decisions.find((decision) => decision.id === selectedId) ?? null,
    [dashboard, selectedId],
  );

  const reviewedDecision =
    judgeReview?.case_number === selectedDecision?.case_number ? judgeReview : null;
  const selectedOutcomeImpact =
    selectedDecision?.projected_outcome === "favorable"
      ? selectedDecision.optimized_savings ?? 0
      : selectedDecision?.projected_outcome === "unfavorable"
        ? selectedDecision.projected_decision_cost ??
          selectedDecision.historical_estimated_condemnation
        : null;


  function selectDecision(decisionId: string) {
    setSelectedId(decisionId);
    setJudgeReview(null);
  }

  const reviewDecision = useCallback(async (decision: BankDecisionItem) => {
    if (reviewingId || approvingId) return;
    setReviewingId(decision.id);
    setJudgeReview(null);
    setError(null);
    try {
      let completedReview: BankJudgeReview | null = null;
      await apiEventStream(
        `/v1/bank/decisions/${decision.id}/judge-review/stream`,
        {},
        (event) => {
          if (event.event === "complete") {
            completedReview = event.data as BankJudgeReview;
            return;
          }
          if (event.event === "error") {
            const message =
              typeof event.data === "object" &&
              event.data !== null &&
              "message" in event.data &&
              typeof event.data.message === "string"
                ? event.data.message
                : "Não foi possível concluir a revisão do agente juiz.";
            throw new Error(message);
          }
        },
      );
      if (!completedReview) {
        throw new Error("A revisão do agente juiz foi encerrada sem parecer.");
      }
      setJudgeReview(completedReview);
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Não foi possível concluir a revisão do agente juiz.",
      );
    } finally {
      setReviewingId(null);
    }
  }, [approvingId, reviewingId]);

  useEffect(() => {
    if (
      !selectedDecision ||
      reviewedDecision ||
      requestedReviewsRef.current.has(selectedDecision.id)
    ) {
      return;
    }
    requestedReviewsRef.current.add(selectedDecision.id);
    void reviewDecision(selectedDecision);
  }, [reviewDecision, reviewedDecision, selectedDecision]);


  async function approveSelectedDecision() {
    if (!selectedDecision || approvingId) return;
    if (!reviewedDecision) {
      setError("Revise a decisão com o agente juiz antes de encaminhá-la.");
      return;
    }
    setApprovingId(selectedDecision.id);
    setError(null);
    try {
      const { promise, resolve } = Promise.withResolvers<void>();
      window.setTimeout(resolve, OUTCOME_SIMULATION_MS);
      await promise;
      await apiFetch<BankDecisionItem>(
        `/v1/bank/decisions/${selectedDecision.id}/approve`,
        { method: "POST" },
      );
      await loadDashboard(true);
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Não foi possível encaminhar a decisão.",
      );
    } finally {
      setApprovingId(null);
    }
  }

  if (loading && !dashboard) {
    return (
      <main className={styles.statePage} aria-live="polite">
        <span className={styles.loader} />
        <strong>Conectando à operação bancária</strong>
        <p>Carregando decisões persistidas no banco de dados.</p>
      </main>
    );
  }

  if (!dashboard) {
    return (
      <main className={styles.statePage} role="alert">
        <CircleAlert size={24} />
        <strong>Painel indisponível</strong>
        <p>{error}</p>
        <button onClick={() => void loadDashboard()} type="button">
          <RefreshCw size={15} /> Tentar novamente
        </button>
      </main>
    );
  }

  const { metrics } = dashboard;
  const kpis = [
    {
      label: "Aderência",
      value: formatPercent(metrics.adherence_rate),
      icon: ShieldCheck,
    },
    {
      label: "Economia",
      value: formatCurrency(metrics.estimated_savings),
      icon: TrendingDown,
    },
    {
      label: "Êxito das decisões",
      value: formatPercent(metrics.projected_success_rate),
      icon: CircleCheckBig,
    },
    {
      label: "Processos",
      value: new Intl.NumberFormat("pt-BR").format(metrics.process_count),
      icon: Scale,
    },
  ];

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div className={styles.brandBlock}>
          <div className={styles.brand}>
            ENTER<span>OS</span>
          </div>
        </div>
        <div className={styles.headerTitle}>
          <Building2 size={17} />
          <div>
            <span>Administração</span>
            <strong>Política de acordos</strong>
          </div>
        </div>
        <button
          aria-label="Atualizar painel"
          className={styles.refreshButton}
          disabled={refreshing}
          onClick={() => void loadDashboard(true)}
          type="button"
        >
          <RefreshCw className={refreshing ? styles.spinning : undefined} size={15} />
          {refreshing ? "Atualizando" : "Atualizar"}
        </button>
      </header>

      <div className={styles.content}>

        <section
          aria-label="Indicadores principais"
          className={styles.kpiGrid}
          id="monitoramento"
        >
          {kpis.map(({ label, value, icon: Icon }) => (
            <article className={styles.kpiCard} key={label}>
              <div className={styles.kpiHeader}>
                <span>{label}</span>
                <Icon size={16} />
              </div>
              <strong>{value}</strong>
            </article>
          ))}
        </section>

        <section className={styles.adherenceSection}>
          <div className={styles.sectionHeading}>
            <div>
              <span>Leitura de aderência</span>
              <h2>Como os advogados estão respondendo à recomendação</h2>
            </div>
          </div>
          <div className={styles.adherenceRail}>
            {(
              [
                ["adherent", metrics.adherent_count],
                ["justified", metrics.justified_count],
                ["divergent", metrics.divergent_count],
              ] as const
            ).map(([status, count]) => (
              <article className={`${styles.adherenceCard} ${styles[status]}`} key={status}>
                <i />
                <strong>{count}</strong>
                <span>{adherenceLabels[status]}</span>
              </article>
            ))}
          </div>
        </section>

        <section className={styles.decisionsSection} id="decisoes">
          <div className={styles.sectionHeading}>
            <div>
              <span>Fila operacional</span>
              <h2>Últimas decisões dos advogados</h2>
            </div>
          </div>

          {dashboard.decisions.length === 0 ? (
            <div className={styles.emptyState}>
              <Clock3 size={20} />
              <strong>Nenhuma decisão recebida</strong>
              <p>As decisões submetidas na área do advogado aparecerão aqui automaticamente.</p>
            </div>
          ) : (
            <div className={styles.decisionWorkspace}>
              <div className={styles.decisionListColumn}>
                <div className={styles.tableWrap}>
                <table className={styles.decisionTable}>
                  <thead>
                    <tr>
                      <th>Processo</th>
                      <th>Recomendação</th>
                      <th>Advogado</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dashboard.decisions.map((decision) => (
                      <tr
                        aria-selected={decision.id === selectedId}
                        className={decision.id === selectedId ? styles.selectedRow : undefined}
                        key={decision.id}
                        onClick={() => selectDecision(decision.id)}
                      >
                        <td>
                          <button onClick={() => selectDecision(decision.id)} type="button">
                            <strong>{decision.process_title}</strong>
                            <small>{decision.case_number}</small>
                          </button>
                        </td>
                        <td>{decisionLabels[decision.model_recommendation]}</td>
                        <td>{decisionLabels[decision.lawyer_recommendation]}</td>
                        <td>
                          <span className={`${styles.statusPill} ${styles[decision.adherence_status]}`}>
                            <i /> {adherenceLabels[decision.adherence_status]}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
                {selectedDecision && (
                  <section className={styles.judgeReview} aria-label="Parecer do agente juiz">
                    <div className={styles.judgeReviewHeader}>
                      <div>
                        <span>Parecer independente</span>
                        <h4>Agente juiz</h4>
                      </div>
                      {reviewedDecision && (
                        <strong className={styles.judgeDisposition}>
                          {judgeDispositionLabels[reviewedDecision.disposition]}
                        </strong>
                      )}
                    </div>

                    {reviewingId === selectedDecision.id && !reviewedDecision ? (
                      <div
                        aria-live="polite"
                        className={styles.judgeInitialLoading}
                        role="status"
                      >
                        <div>
                          <Scale size={15} />
                          <strong>Analisando decisão e documentos</strong>
                        </div>
                        <span className={styles.judgeLoadingTrack}><i /></span>
                      </div>
                    ) : reviewedDecision ? (
                      <>
                        <p className={styles.judgeReviewCopy}>{reviewedDecision.summary}</p>
                        <p className={styles.judgeMeta}>
                          {formatPercent(reviewedDecision.confidence)} ·{" "}
                          {reviewedDecision.consulted_documents.length} documento
                          {reviewedDecision.consulted_documents.length === 1 ? "" : "s"}
                        </p>
                        {(reviewedDecision.findings.length > 0 ||
                          reviewedDecision.missing_evidence.length > 0) && (
                          <details className={styles.judgeEvidence}>
                            <summary>Ver fundamentos e provas necessárias</summary>
                            <div className={styles.judgeFindings}>
                              {reviewedDecision.findings.map((finding, index) => (
                                <article
                                  className={styles.judgeFinding}
                                  key={`${finding.issue}-${index}`}
                                >
                                  <strong>{finding.issue}</strong>
                                  <span>{finding.conclusion}</span>
                                  <p>{finding.reasoning}</p>
                                </article>
                              ))}
                            </div>
                            {reviewedDecision.missing_evidence.length > 0 && (
                              <p className={styles.judgeMissing}>
                                <strong>Provas necessárias:</strong>{" "}
                                {reviewedDecision.missing_evidence.join(" · ")}
                              </p>
                            )}
                          </details>
                        )}

                      </>
                    ) : (
                      <button
                        className={styles.judgeButton}
                        disabled={reviewingId !== null || approvingId !== null}
                        onClick={() => void reviewDecision(selectedDecision)}
                        type="button"
                      >
                        <Scale size={15} /> Tentar novamente
                      </button>
                    )}
                  </section>
                )}
              </div>

              {selectedDecision && (
                <article className={styles.decisionDetail}>
                  <div className={styles.detailTopline}>
                    <span>Revisão da decisão</span>
                    <small>{formatDate(selectedDecision.created_at)}</small>
                  </div>
                  <h3>{selectedDecision.process_title}</h3>
                  <p className={styles.caseNumber}>{selectedDecision.case_number} · {selectedDecision.state}</p>

                  <div className={styles.decisionFlow} aria-label="Fluxo da decisão">
                    <div>
                      <span>Recomendação</span>
                      <strong>{decisionLabels[selectedDecision.model_recommendation]}</strong>
                    </div>
                    <ArrowRight size={16} />
                    <div>
                      <span>Advogado</span>
                      <strong>{decisionLabels[selectedDecision.lawyer_recommendation]}</strong>
                    </div>
                    <ArrowRight size={16} />
                    <div>
                      <span>Banco</span>
                      <strong>{selectedDecision.bank_status === "approved" ? "Encaminhada" : "Pendente"}</strong>
                    </div>
                    <ArrowRight size={16} />
                    <div
                      className={
                        selectedDecision.projected_outcome
                          ? styles[selectedDecision.projected_outcome]
                          : undefined
                      }
                    >
                      <span>Resultado da causa</span>
                      <strong>
                        {selectedDecision.projected_outcome === "favorable"
                          ? "Favorável"
                          : selectedDecision.projected_outcome === "unfavorable"
                            ? "Desfavorável"
                            : "Aguardando"}
                      </strong>
                    </div>
                  </div>

                  {approvingId === selectedDecision.id && (
                    <div className={styles.outcomeWait} role="status" aria-live="polite">
                      <div>
                        <Clock3 size={17} />
                        <span>Aguardando resultado da causa</span>
                      </div>
                      <div className={styles.outcomeWaitTrack} aria-hidden="true">
                        <i />
                      </div>
                      <p>A decisão foi encaminhada. Consolidando o desfecho e o impacto financeiro.</p>
                    </div>
                  )}

                  {selectedDecision.projected_outcome && (
                    <div
                      className={`${styles.outcomePath} ${
                        styles[selectedDecision.projected_outcome]
                      }`}
                    >
                      <div className={styles.outcomePathHeader}>
                        {selectedDecision.projected_outcome === "favorable" ? (
                          <CircleCheckBig size={18} />
                        ) : (
                          <CircleX size={18} />
                        )}
                        <div>
                          <strong>
                            Causa encerrada com resultado{" "}
                            {selectedDecision.projected_outcome === "favorable"
                              ? "favorável"
                              : "desfavorável"}
                          </strong>
                        </div>
                      </div>
                      <div className={styles.outcomeBranches} aria-hidden="true">
                        <i className={styles.favorableBranch}>Favorável</i>
                        <i className={styles.unfavorableBranch}>Desfavorável</i>
                      </div>
                      {selectedOutcomeImpact !== null && (
                        <div className={styles.outcomeResultSummary}>
                          <div>
                            <span>
                              {selectedDecision.projected_outcome === "favorable"
                                ? "Economia obtida"
                                : "Perda na causa"}
                            </span>
                            <strong>{formatCurrency(selectedOutcomeImpact)}</strong>
                          </div>
                          <div>
                            <span>Custo final</span>
                            <strong>
                              {formatCurrency(selectedDecision.projected_decision_cost ?? 0)}
                            </strong>
                          </div>
                        </div>
                      )}
                      <p>{selectedDecision.projected_outcome_reason}</p>
                    </div>
                  )}

                  <dl className={styles.detailList}>
                    <div>
                      <dt>Justificativa</dt>
                      <dd>{selectedDecision.justification ?? "Decisão aderente; justificativa não exigida."}</dd>
                    </div>
                    <div>
                      <dt>Subsídios nos autos</dt>
                      <dd><FileCheck2 size={14} /> {selectedDecision.evidence_count} de 6 documentos disponíveis</dd>
                    </div>
                    <div>
                      <dt>Exposição</dt>
                      <dd>{formatCurrency(selectedDecision.expected_condemnation)}</dd>
                    </div>
                    <div>
                      <dt>Valor da causa</dt>
                      <dd>{formatCurrency(selectedDecision.claim_amount)}</dd>
                    </div>
                    <div>
                      <dt>Condenação de referência</dt>
                      <dd>
                        {formatCurrency(selectedDecision.historical_estimated_condemnation)}
                        {" · "}
                        {formatPercent(metrics.historical_condemnation_ratio)} do valor da causa
                      </dd>
                    </div>
                    {selectedDecision.projected_decision_cost !== null && (
                      <div>
                        <dt>Custo final da decisão</dt>
                        <dd>{formatCurrency(selectedDecision.projected_decision_cost)}</dd>
                      </div>
                    )}
                    {selectedDecision.optimized_savings !== null && (
                      <div>
                        <dt>Economia obtida</dt>
                        <dd className={styles.optimizedValue}>
                          {formatCurrency(selectedDecision.optimized_savings)}
                        </dd>
                      </div>
                    )}
                  </dl>


                  <button
                    className={styles.approveButton}
                    disabled={
                      selectedDecision.bank_status === "approved" ||
                      approvingId !== null ||
                      reviewingId !== null ||
                      !reviewedDecision
                    }
                    onClick={() => void approveSelectedDecision()}
                    type="button"
                  >
                    {approvingId === selectedDecision.id ? (
                      <span className={styles.loader} />
                    ) : selectedDecision.bank_status === "approved" ? (
                      <Check size={16} />
                    ) : (
                      <ArrowRight size={16} />
                    )}
                    {approvingId === selectedDecision.id
                      ? "Aguardando resultado"
                      : selectedDecision.bank_status === "approved"
                        ? "Resultado registrado"
                        : "Prosseguir com a decisão"}
                  </button>
                </article>
              )}
            </div>
          )}
        </section>

        <section className={styles.effectivenessSection} id="efetividade">
          <div className={styles.sectionHeading}>
            <div>
              <span>Efetividade</span>
              <h2>Resultados das decisões encaminhadas</h2>
            </div>
          </div>
          <div className={styles.effectivenessGrid}>
            <article className={styles.savingsCard}>
              <span>Economia acumulada</span>
              <strong>{formatCurrency(metrics.estimated_savings)}</strong>
              <div className={styles.outcomeLegend}>
                <span><i className={styles.favorableSwatch} /> Favorável</span>
                <span><i className={styles.unfavorableSwatch} /> Desfavorável</span>
              </div>
              {dashboard.monthly_effectiveness.length ? (
                <div className={styles.monthlyChart}>
                  {dashboard.monthly_effectiveness.map((item) => {
                    const total = item.favorable_count + item.unfavorable_count;
                    const favorableWidth = total ? (item.favorable_count / total) * 100 : 0;
                    const unfavorableWidth = total ? (item.unfavorable_count / total) * 100 : 0;
                    return (
                      <div className={styles.chartRow} key={item.month}>
                        <small>{formatMonth(item.month)}</small>
                        <div className={styles.outcomeBar}>
                          <i
                            className={styles.favorableBar}
                            style={{ "--bar-width": `${favorableWidth}%` } as CSSProperties}
                          />
                          <i
                            className={styles.unfavorableBar}
                            style={{ "--bar-width": `${unfavorableWidth}%` } as CSSProperties}
                          />
                        </div>
                        <span>
                          {formatCurrency(item.estimated_savings)}
                          {" · "}
                          {item.favorable_count}F/{item.unfavorable_count}D
                        </span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className={styles.chartEmpty}>
                  Os desfechos aparecem quando o banco prossegue com uma decisão.
                </p>
              )}
            </article>
            <div className={styles.effectivenessMetrics}>
              <article>
                <span>Condenação-base</span>
                <strong>{formatCurrency(metrics.estimated_condemnation_total)}</strong>
                <small>
                  {formatPercent(metrics.historical_condemnation_ratio)} do valor das causas
                </small>
              </article>
              <article>
                <span>Custo realizado das decisões</span>
                <strong>{formatCurrency(metrics.optimized_decision_cost)}</strong>
                <small>Acordos concluídos e causas desfavoráveis</small>
              </article>
            </div>
          </div>
        </section>

        {error && <div className={styles.errorBanner} role="alert"><CircleAlert size={15} /> {error}</div>}
      </div>
    </main>
  );
}
