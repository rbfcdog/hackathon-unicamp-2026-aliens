"use client";
// Admin dashboard records real case outcomes and compares them with approved decisions.

import { type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowRight,
  Building2,
  Check,
  CircleAlert,
  Clock3,
  FileCheck2,
  RefreshCw,
  Scale,
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

const outcomeLabels: Record<BankDecisionItem["outcome"], string> = {
  pending: "Não registrado",
  favorable: "Defesa favorável",
  settled: "Acordo celebrado",
  unfavorable: "Condenação",
};
const bankStatusLabels: Record<BankDecisionItem["bank_status"], string> = {
  pending: "Aguardando encaminhamento",
  approved: "Encaminhada",
};


const judgeDispositionLabels: Record<BankJudgeReview["disposition"], string> = {
  grant_claim: "Procedência",
  deny_claim: "Improcedência",
  partial_grant: "Procedência parcial",
  insufficient_evidence: "Prova insuficiente",
};

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 2,
  }).format(value);
}

function formatCostDifference(value: number): string {
  return `${value > 0 ? "+" : ""}${formatCurrency(value)}`;
}


function formatDate(value: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "America/Sao_Paulo",
  }).format(new Date(value));
}

const formatNumber = new Intl.NumberFormat("pt-BR");

export function BankDashboard() {
  const [dashboard, setDashboard] = useState<BankDashboardResponse | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [judgeReview, setJudgeReview] = useState<BankJudgeReview | null>(null);
  const [approvingId, setApprovingId] = useState<string | null>(null);
  const [recordingId, setRecordingId] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<Exclude<BankDecisionItem["outcome"], "pending">>(
    "favorable",
  );
  const [actualCost, setActualCost] = useState("");
  const [error, setError] = useState<string | null>(null);
  const requestedReviewsRef = useRef(new Set<string>());
  const selectedIdRef = useRef<string | null>(null);

  const loadDashboard = useCallback(async (background = false) => {
    if (background) setRefreshing(true);
    try {
      const result = await apiFetch<BankDashboardResponse>("/v1/bank/dashboard", {
        cache: "no-store",
      });
      const nextSelectedDecision =
        result.decisions.find(
          (decision) => decision.id === selectedIdRef.current,
        ) ?? result.decisions[0] ?? null;
      setDashboard(result);
      selectedIdRef.current = nextSelectedDecision?.id ?? null;
      setSelectedId(selectedIdRef.current);
      if (nextSelectedDecision) {
        setOutcome(
          nextSelectedDecision.outcome === "pending"
            ? "favorable"
            : nextSelectedDecision.outcome,
        );
        setActualCost(nextSelectedDecision.actual_cost?.toString() ?? "");
      }
      setError(null);
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Não foi possível carregar as decisões registradas.",
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


  function selectDecision(decision: BankDecisionItem) {
    selectedIdRef.current = decision.id;
    setSelectedId(decision.id);
    setOutcome(decision.outcome === "pending" ? "favorable" : decision.outcome);
    setActualCost(decision.actual_cost?.toString() ?? "");
    setJudgeReview(null);
  }

  const reviewDecision = useCallback(async (decision: BankDecisionItem) => {
    if (reviewingId || approvingId || recordingId) return;
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
                : "Não foi possível concluir a revisão independente.";
            throw new Error(message);
          }
        },
      );
      if (!completedReview) {
        throw new Error("A revisão independente foi encerrada sem parecer.");
      }
      setJudgeReview(completedReview);
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Não foi possível concluir a revisão independente.",
      );
    } finally {
      setReviewingId(null);
    }
  }, [approvingId, recordingId, reviewingId]);

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
      setError("Conclua a revisão independente antes de encaminhar a decisão.");
      return;
    }
    setApprovingId(selectedDecision.id);
    setError(null);
    try {
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

  async function recordSelectedOutcome(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedDecision || recordingId) return;
    const parsedCost = outcome === "favorable" ? 0 : Number(actualCost.replace(",", "."));
    if (!Number.isFinite(parsedCost) || parsedCost < 0 || (outcome !== "favorable" && !parsedCost)) {
      setError("Informe o custo realizado para registrar o resultado.");
      return;
    }
    setRecordingId(selectedDecision.id);
    setError(null);
    try {
      await apiFetch<BankDecisionItem>(
        `/v1/bank/decisions/${selectedDecision.id}/outcome`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ outcome, actual_cost: parsedCost }),
        },
      );
      await loadDashboard(true);
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Não foi possível registrar o resultado.",
      );
    } finally {
      setRecordingId(null);
    }
  }

  if (loading && !dashboard) {
    return (
      <main className={styles.statePage} aria-live="polite">
        <span className={styles.loader} />
        <strong>Conectando à operação</strong>
        <p>Carregando decisões registradas.</p>
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
      label: "Processos acompanhados",
      value: formatNumber.format(metrics.process_count),
      note: `${formatNumber.format(metrics.decision_count)} decisões registradas`,
      icon: Building2,
    },
    {
      label: "Decisões encaminhadas",
      value: formatNumber.format(metrics.approved_count),
      note: "Prontas para acompanhamento do resultado.",
      icon: Check,
    },
    {
      label: "Resultados registrados",
      value: formatNumber.format(metrics.outcome_recorded_count),
      note: "Com desfecho e custo efetivamente informados.",
      icon: FileCheck2,
    },
    {
      label: "Aguardando resultado",
      value: formatNumber.format(metrics.pending_outcome_count),
      note: "Decisões encaminhadas sem desfecho informado.",
      icon: Clock3,
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
            <strong>Decisões e resultados</strong>
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
          {kpis.map(({ label, value, note, icon: Icon }) => (
            <article className={styles.kpiCard} key={label}>
              <div className={styles.kpiHeader}>
                <span>{label}</span>
                <Icon size={16} />
              </div>
              <strong>{value}</strong>
              <p>{note}</p>
            </article>
          ))}
        </section>

        <section className={styles.decisionsSection} id="decisoes">
          <div className={styles.sectionHeading}>
            <div>
              <span>Decisões registradas</span>
              <h2>Acompanhamento das decisões</h2>
            </div>
          </div>

          {dashboard.decisions.length === 0 ? (
            <div className={styles.emptyState}>
              <Clock3 size={20} />
              <strong>Nenhuma decisão registrada</strong>
              <p>Quando uma decisão for registrada no processo, ela aparecerá aqui.</p>
            </div>
          ) : (
            <div className={styles.decisionWorkspace}>
              <div className={styles.decisionListColumn}>
                <div className={styles.tableWrap}>
                  <table className={styles.decisionTable}>
                    <thead>
                      <tr>
                        <th>Processo</th>
                        <th>Decisão</th>
                        <th>Encaminhamento</th>
                        <th>Resultado</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dashboard.decisions.map((decision) => (
                        <tr
                          aria-selected={decision.id === selectedId}
                          className={decision.id === selectedId ? styles.selectedRow : undefined}
                          key={decision.id}
                          onClick={() => selectDecision(decision)}
                        >
                          <td>
                            <button onClick={() => selectDecision(decision)} type="button">
                              <strong>{decision.process_title}</strong>
                              <small>{decision.case_number}</small>
                            </button>
                          </td>
                          <td>{decisionLabels[decision.recommendation]}</td>
                          <td>{bankStatusLabels[decision.bank_status]}</td>
                          <td>{outcomeLabels[decision.outcome]}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {selectedDecision && (
                  <section className={styles.judgeReview} aria-label="Parecer independente">
                    <div className={styles.judgeReviewHeader}>
                      <div>
                        <span>Parecer independente</span>
                        <h4>Revisão documental</h4>
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
                          {reviewedDecision.consulted_documents.length} documento
                          {reviewedDecision.consulted_documents.length === 1 ? "" : "s"}
                          {" consultado"}
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
                        disabled={reviewingId !== null || approvingId !== null || recordingId !== null}
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

                  <div className={styles.decisionFlow} aria-label="Situação da decisão">
                    <div>
                      <span>Decisão</span>
                      <strong>{decisionLabels[selectedDecision.recommendation]}</strong>
                    </div>
                    <ArrowRight size={16} />
                    <div>
                      <span>Encaminhamento</span>
                      <strong>{bankStatusLabels[selectedDecision.bank_status]}</strong>
                    </div>
                    <ArrowRight size={16} />
                    <div>
                      <span>Resultado</span>
                      <strong>{outcomeLabels[selectedDecision.outcome]}</strong>
                    </div>
                  </div>

                  <dl className={styles.detailList}>
                    <div>
                      <dt>Justificativa</dt>
                      <dd>{selectedDecision.justification ?? "Nenhuma justificativa foi registrada."}</dd>
                    </div>
                    <div>
                      <dt>Subsídios nos autos</dt>
                      <dd><FileCheck2 size={14} /> {selectedDecision.evidence_count} de 6 documentos disponíveis</dd>
                    </div>
                    <div>
                      <dt>Referência na decisão</dt>
                      <dd>{formatCurrency(selectedDecision.expected_cost)}</dd>
                    </div>
                    <div>
                      <dt>Valor da causa</dt>
                      <dd>{formatCurrency(selectedDecision.claim_amount)}</dd>
                    </div>
                    <div>
                      <dt>Resultado da causa</dt>
                      <dd>{outcomeLabels[selectedDecision.outcome]}</dd>
                    </div>
                    <div>
                      <dt>Custo realizado</dt>
                      <dd>
                        {selectedDecision.actual_cost === null
                          ? "Ainda não registrado."
                          : formatCurrency(selectedDecision.actual_cost)}
                      </dd>
                    </div>
                  </dl>

                  {selectedDecision.bank_status === "approved" ? (
                    <form className={styles.outcomeForm} onSubmit={recordSelectedOutcome}>
                      <div>
                        <span>Resultado processual</span>
                        <h4>Registrar resultado real</h4>
                      </div>
                      <label className={styles.outcomeField}>
                        <span>Desfecho</span>
                        <select
                          onChange={(event) => setOutcome(
                            event.target.value as Exclude<BankDecisionItem["outcome"], "pending">,
                          )}
                          value={outcome}
                        >
                          <option value="favorable">Defesa favorável</option>
                          <option value="settled">Acordo celebrado</option>
                          <option value="unfavorable">Condenação</option>
                        </select>
                      </label>
                      <label className={styles.outcomeField}>
                        <span>Custo realizado</span>
                        <input
                          disabled={outcome === "favorable"}
                          inputMode="decimal"
                          min="0"
                          onChange={(event) => setActualCost(event.target.value)}
                          placeholder={outcome === "favorable" ? "R$ 0,00" : "R$ 0,00"}
                          required={outcome !== "favorable"}
                          step="0.01"
                          type="number"
                          value={outcome === "favorable" ? "0" : actualCost}
                        />
                      </label>
                      <button
                        className={styles.outcomeButton}
                        disabled={recordingId !== null}
                        type="submit"
                      >
                        {recordingId === selectedDecision.id ? <span className={styles.loader} /> : <Check size={15} />}
                        {selectedDecision.outcome === "pending"
                          ? "Salvar resultado"
                          : "Atualizar resultado"}
                      </button>
                    </form>
                  ) : (
                    <button
                      className={styles.approveButton}
                      disabled={
                        approvingId !== null ||
                        reviewingId !== null ||
                        recordingId !== null ||
                        !reviewedDecision
                      }
                      onClick={() => void approveSelectedDecision()}
                      type="button"
                    >
                      {approvingId === selectedDecision.id ? (
                        <span className={styles.loader} />
                      ) : (
                        <ArrowRight size={16} />
                      )}
                      {approvingId === selectedDecision.id
                        ? "Encaminhando"
                        : "Prosseguir com a decisão"}
                    </button>
                  )}
                </article>
              )}
            </div>
          )}
        </section>

        <section className={styles.effectivenessSection} id="efetividade">
          <div className={styles.sectionHeading}>
            <div>
              <span>Resultados registrados</span>
              <h2>Comparação com resultados reais</h2>
            </div>
          </div>
          {metrics.outcome_recorded_count === 0 ? (
            <div className={styles.emptyState}>
              <Clock3 size={20} />
              <strong>Ainda não há resultados registrados</strong>
              <p>Registre o desfecho de uma decisão encaminhada para compará-lo com a referência.</p>
            </div>
          ) : (
            <div className={styles.comparisonGrid}>
              <article className={styles.comparisonCard}>
                <span>Resultados registrados</span>
                <strong>{formatNumber.format(metrics.outcome_recorded_count)}</strong>
                <p>Decisões com desfecho efetivamente informado.</p>
              </article>
              <article className={styles.comparisonCard}>
                <span>Custo realizado</span>
                <strong>{formatCurrency(metrics.actual_cost_total)}</strong>
                <p>Somatório dos resultados já registrados.</p>
              </article>
              <article className={styles.comparisonCard}>
                <span>Referência nas decisões</span>
                <strong>{formatCurrency(metrics.expected_cost_total)}</strong>
                <p>Valor registrado quando cada decisão foi encaminhada.</p>
              </article>
              <article
                className={`${styles.comparisonCard} ${
                  metrics.cost_difference <= 0 ? styles.comparisonPositive : styles.comparisonNegative
                }`}
              >
                <span>Variação apurada</span>
                <strong>{formatCostDifference(metrics.cost_difference)}</strong>
                <p>Realizado menos a referência da decisão.</p>
              </article>
            </div>
          )}
        </section>

        {error && <div className={styles.errorBanner} role="alert"><CircleAlert size={15} /> {error}</div>}
      </div>
    </main>
  );
}
