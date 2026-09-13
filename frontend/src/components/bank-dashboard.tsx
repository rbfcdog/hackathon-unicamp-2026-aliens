"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";
import {
  ArrowLeft,
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
import { apiFetch } from "@/lib/api";
import type { BankDashboardResponse, BankDecisionItem, DecisionChoice } from "@/lib/types";
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
  const [approvingId, setApprovingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  async function approveSelectedDecision() {
    if (!selectedDecision || approvingId) return;
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
      detail: `${metrics.adherent_count} decisões alinhadas`,
      icon: ShieldCheck,
    },
    {
      label: "Economia otimizada",
      value: formatCurrency(metrics.estimated_savings),
      detail: `${formatPercent(metrics.relative_savings)} sobre a condenação-base`,
      icon: TrendingDown,
    },
    {
      label: "Efetividade projetada",
      value: formatPercent(metrics.projected_success_rate),
      detail: `${metrics.favorable_count} favoráveis · ${metrics.unfavorable_count} desfavoráveis`,
      icon: CircleCheckBig,
    },
    {
      label: "Processos",
      value: new Intl.NumberFormat("pt-BR").format(metrics.process_count),
      detail: `${metrics.decision_count} com decisão submetida`,
      icon: Scale,
    },
  ];

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div className={styles.brandBlock}>
          <Link className={styles.backLink} href="/">
            <ArrowLeft size={15} /> Área do advogado
          </Link>
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
        <nav aria-label="Seções do painel" className={styles.nav}>
          <a href="#monitoramento">Monitoramento</a>
          <a href="#decisoes">Decisões</a>
          <a href="#efetividade">Efetividade</a>
        </nav>
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
        <section className={styles.intro} id="monitoramento">
          <div>
            <span className={styles.eyebrow}>Monitoramento da política</span>
            <h1>Da recomendação à decisão operacional.</h1>
          </div>
          <p>
            Cada número abaixo é calculado a partir da última decisão submetida pelos
            advogados e persistida no banco de dados.
          </p>
        </section>

        <section aria-label="Indicadores principais" className={styles.kpiGrid}>
          {kpis.map(({ label, value, detail, icon: Icon }) => (
            <article className={styles.kpiCard} key={label}>
              <div className={styles.kpiHeader}>
                <span>{label}</span>
                <Icon size={16} />
              </div>
              <strong>{value}</strong>
              <small>{detail}</small>
            </article>
          ))}
        </section>

        <section className={styles.adherenceSection}>
          <div className={styles.sectionHeading}>
            <div>
              <span>Leitura de aderência</span>
              <h2>Como os advogados estão respondendo ao modelo</h2>
            </div>
            <small>Uma decisão divergente só é justificada quando contém justificativa registrada.</small>
          </div>
          <div className={styles.adherenceRail}>
            {(
              [
                ["adherent", metrics.adherent_count, "Decisão igual à recomendação"],
                ["justified", metrics.justified_count, "Divergência fundamentada"],
                ["divergent", metrics.divergent_count, "Divergência sem justificativa"],
              ] as const
            ).map(([status, count, description]) => (
              <article className={`${styles.adherenceCard} ${styles[status]}`} key={status}>
                <i />
                <strong>{count}</strong>
                <span>{adherenceLabels[status]}</span>
                <small>{description}</small>
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
            <small>Selecione uma linha para revisar o processo.</small>
          </div>

          {dashboard.decisions.length === 0 ? (
            <div className={styles.emptyState}>
              <Clock3 size={20} />
              <strong>Nenhuma decisão recebida</strong>
              <p>As decisões submetidas na área do advogado aparecerão aqui automaticamente.</p>
            </div>
          ) : (
            <div className={styles.decisionWorkspace}>
              <div className={styles.tableWrap}>
                <table className={styles.decisionTable}>
                  <thead>
                    <tr>
                      <th>Processo</th>
                      <th>Modelo</th>
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
                        onClick={() => setSelectedId(decision.id)}
                      >
                        <td>
                          <button onClick={() => setSelectedId(decision.id)} type="button">
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
                <article className={styles.decisionDetail}>
                  <div className={styles.detailTopline}>
                    <span>Revisão da decisão</span>
                    <small>{formatDate(selectedDecision.created_at)}</small>
                  </div>
                  <h3>{selectedDecision.process_title}</h3>
                  <p className={styles.caseNumber}>{selectedDecision.case_number} · {selectedDecision.state}</p>

                  <div className={styles.decisionFlow} aria-label="Fluxo da decisão">
                    <div>
                      <span>Modelo</span>
                      <strong>{decisionLabels[selectedDecision.model_recommendation]}</strong>
                      <small>
                        {selectedDecision.recommended_amount === null
                          ? "Sem faixa monetária"
                          : `Alvo ${formatCurrency(selectedDecision.recommended_amount)}`}
                      </small>
                    </div>
                    <ArrowRight size={16} />
                    <div>
                      <span>Advogado</span>
                      <strong>{decisionLabels[selectedDecision.lawyer_recommendation]}</strong>
                      <small>
                        {selectedDecision.lawyer_amount === null
                          ? "Sem valor informado"
                          : formatCurrency(selectedDecision.lawyer_amount)}
                      </small>
                    </div>
                    <ArrowRight size={16} />
                    <div>
                      <span>Banco</span>
                      <strong>{selectedDecision.bank_status === "approved" ? "Encaminhada" : "Pendente"}</strong>
                      <small>
                        {selectedDecision.bank_reviewed_at
                          ? formatDate(selectedDecision.bank_reviewed_at)
                          : "Aguardando revisão"}
                      </small>
                    </div>
                    <ArrowRight size={16} />
                    <div
                      className={
                        selectedDecision.projected_outcome
                          ? styles[selectedDecision.projected_outcome]
                          : undefined
                      }
                    >
                      <span>Projeção</span>
                      <strong>
                        {selectedDecision.projected_outcome === "favorable"
                          ? "Favorável"
                          : selectedDecision.projected_outcome === "unfavorable"
                            ? "Desfavorável"
                            : "Aguardando"}
                      </strong>
                      <small>
                        {selectedDecision.projected_outcome
                          ? "Calculada no encaminhamento"
                          : "Disponível após prosseguir"}
                      </small>
                    </div>
                  </div>

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
                          <span>Resultado projetado</span>
                          <strong>
                            Caminho{" "}
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
                      <dt>Exposição estimada</dt>
                      <dd>{formatCurrency(selectedDecision.expected_condemnation)}</dd>
                    </div>
                    <div>
                      <dt>Valor da causa</dt>
                      <dd>{formatCurrency(selectedDecision.claim_amount)}</dd>
                    </div>
                    <div>
                      <dt>Condenação-base histórica</dt>
                      <dd>
                        {formatCurrency(selectedDecision.historical_estimated_condemnation)}
                        {" · "}
                        {formatPercent(metrics.historical_condemnation_ratio)} do valor da causa
                      </dd>
                    </div>
                    {selectedDecision.projected_decision_cost !== null && (
                      <div>
                        <dt>Custo projetado da decisão</dt>
                        <dd>{formatCurrency(selectedDecision.projected_decision_cost)}</dd>
                      </div>
                    )}
                    {selectedDecision.optimized_savings !== null && (
                      <div>
                        <dt>Economia otimizada</dt>
                        <dd className={styles.optimizedValue}>
                          {formatCurrency(selectedDecision.optimized_savings)}
                        </dd>
                      </div>
                    )}
                  </dl>

                  <button
                    className={styles.approveButton}
                    disabled={selectedDecision.bank_status === "approved" || approvingId !== null}
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
                      ? "Encaminhando"
                      : selectedDecision.bank_status === "approved"
                        ? "Decisão encaminhada"
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
              <h2>Resultado projetado das decisões encaminhadas</h2>
            </div>
            <small>
              Economia = condenação-base ({formatPercent(metrics.historical_condemnation_ratio)}
              {" × valor da causa) − custo da decisão. Base histórica: "}
              {new Intl.NumberFormat("pt-BR").format(metrics.historical_sample_size)} casos de
              parcial procedência.
            </small>
          </div>
          <div className={styles.effectivenessGrid}>
            <article className={styles.savingsCard}>
              <span>Economia otimizada acumulada</span>
              <strong>{formatCurrency(metrics.estimated_savings)}</strong>
              <p className={styles.economyFormula}>
                {formatCurrency(metrics.estimated_condemnation_total)} de condenação-base
                {" − "}
                {formatCurrency(metrics.optimized_decision_cost)} de custo projetado
                {" · "}
                {formatPercent(metrics.relative_savings)} de economia relativa
              </p>
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
                <span>Condenação-base estimada</span>
                <strong>{formatCurrency(metrics.estimated_condemnation_total)}</strong>
                <small>
                  {formatPercent(metrics.historical_condemnation_ratio)} do valor das causas
                </small>
              </article>
              <article>
                <span>Custo projetado das decisões</span>
                <strong>{formatCurrency(metrics.optimized_decision_cost)}</strong>
                <small>Acordos aceitos e caminhos desfavoráveis</small>
              </article>
              <article className={styles.favorableMetric}>
                <span>Economia relativa</span>
                <strong>{formatPercent(metrics.relative_savings)}</strong>
                <small>{metrics.favorable_count} favoráveis · {metrics.unfavorable_count} desfavoráveis</small>
              </article>
            </div>
          </div>
        </section>

        {error && <div className={styles.errorBanner} role="alert"><CircleAlert size={15} /> {error}</div>}
      </div>
    </main>
  );
}
