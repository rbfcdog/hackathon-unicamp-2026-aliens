"use client";

import { useEffect, useState, type CSSProperties, type FormEvent } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Database,
  FileCheck2,
  RefreshCw,
  Save,
  Scale,
  SendHorizontal,
  ShieldCheck,
  WandSparkles,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import type {
  EvidenceInput,
  EvidenceKey,
  LegalProcess,
  ProcessFinancialOverview,
  SubmittedProcessDecision,
} from "@/lib/types";

type Props = {
  legalProcess: LegalProcess;
  onProcessUpdated: (legalProcess: LegalProcess) => void;
};

type EditableProcess = {
  case_number: string;
  title: string;
  location: string;
  state: string;
  subject: string;
  sub_subject: "fraud" | "generic";
  claim_amount: string;
  evidence: EvidenceInput;
};

type DecisionChoice = "agreement" | "defense" | "human_review";

const evidenceLabels: Record<EvidenceKey, string> = {
  contract: "Contrato",
  bank_statement: "Extrato bancário",
  credit_proof: "Comprovante de crédito",
  dossier: "Dossiê",
  debt_evolution: "Evolução da dívida",
  referenced_report: "Laudo referenciado",
};

const decisionLabels: Record<DecisionChoice, string> = {
  agreement: "Acordo",
  defense: "Defesa",
  human_review: "Revisão humana",
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
    maximumFractionDigits: 0,
  }).format(value);
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "America/Sao_Paulo",
  }).format(new Date(value));
}

function isMeaningfulCaseValue(value: string): boolean {
  const normalized = value.trim().toLocaleLowerCase("pt-BR");
  return Boolean(normalized) && !["sem informações", "novo processo", "na"].includes(normalized);
}



function editableProcess(overview: ProcessFinancialOverview): EditableProcess {
  return {
    case_number: overview.case_number,
    title: overview.title,
    location: overview.location,
    state: overview.state,
    subject: overview.subject,
    sub_subject: overview.sub_subject,
    claim_amount: overview.claim_amount > 0.01 ? String(overview.claim_amount) : "",
    evidence: overview.evidence,
  };
}

export function ProcessFinancialDashboard({
  legalProcess,
  onProcessUpdated,
}: Props) {
  const [overview, setOverview] = useState<ProcessFinancialOverview | null>(null);
  const [form, setForm] = useState<EditableProcess | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [saving, setSaving] = useState(false);
  const [naming, setNaming] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [decisionChoice, setDecisionChoice] = useState<DecisionChoice>("human_review");
  const [decisionAmount, setDecisionAmount] = useState("");
  const [decisionJustification, setDecisionJustification] = useState("");
  const [submittedDecision, setSubmittedDecision] = useState<SubmittedProcessDecision | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    apiFetch<ProcessFinancialOverview>(
      `/v1/processes/${encodeURIComponent(legalProcess.case_number)}/financial-overview`,
      { signal: controller.signal },
    )
      .then((result) => {
        setOverview(result);
        setForm(editableProcess(result));
        setSubmittedDecision(result.latest_decision);
        const choice = result.latest_decision?.recommendation ?? result.decision?.recommendation ?? "human_review";
        setDecisionChoice(choice);
        setDecisionAmount(
          result.latest_decision?.amount
            ? String(result.latest_decision.amount)
            : result.decision?.agreement_range
              ? String(result.decision.agreement_range.target)
              : "",
        );
        setDecisionJustification(result.latest_decision?.justification ?? "");
        setError(null);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          caught instanceof Error
            ? caught.message
            : "Não foi possível carregar a visão estratégica.",
        );
      });

    return () => controller.abort();
  }, [legalProcess.case_number, revision]);

  async function persistForm(): Promise<LegalProcess> {
    if (!form) throw new Error("Os campos do processo ainda não foram carregados.");
    const claimAmount = Number(form.claim_amount.replace(",", "."));
    if (!form.case_number.trim() || !form.title.trim() || !form.location.trim()) {
      throw new Error("Preencha o nome, o número e a localização do processo.");
    }
    if (form.state.trim().length !== 2) {
      throw new Error("A UF precisa ter exatamente duas letras.");
    }
    if (!form.subject.trim() || !Number.isFinite(claimAmount) || claimAmount <= 0) {
      throw new Error("Preencha o assunto e um valor da causa maior que zero.");
    }

    return apiFetch<LegalProcess>(
      `/v1/processes/${encodeURIComponent(legalProcess.case_number)}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...form,
          case_number: form.case_number.trim(),
          title: form.title.trim(),
          location: form.location.trim(),
          state: form.state.trim().toUpperCase(),
          subject: form.subject.trim(),
          claim_amount: claimAmount,
        }),
      },
    );
  }

  async function saveChanges(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (!form || saving || naming || submitting) return;
    setSaving(true);
    setError(null);
    setFeedback(null);
    try {
      let updated = await persistForm();
      onProcessUpdated(updated);
      if (updated.title.trim().toLowerCase() === "novo processo") {
        setNaming(true);
        updated = await apiFetch<LegalProcess>(
          `/v1/processes/${encodeURIComponent(updated.case_number)}/infer-title`,
          { method: "POST" },
        );
        onProcessUpdated(updated);
      }
      setFeedback("Alterações salvas no processo.");
      setRevision((current) => current + 1);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "Não foi possível salvar o processo.");
    } finally {
      setSaving(false);
      setNaming(false);
    }
  }

  async function inferTitle() {
    if (!form || saving || naming || submitting) return;
    setNaming(true);
    setError(null);
    setFeedback(null);
    try {
      const persisted = await persistForm();
      const updated = await apiFetch<LegalProcess>(
        `/v1/processes/${encodeURIComponent(persisted.case_number)}/infer-title`,
        { method: "POST" },
      );
      onProcessUpdated(updated);
      setForm((current) => (current ? { ...current, title: updated.title } : current));
      setRevision((current) => current + 1);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "A IA não conseguiu sugerir o nome.");
    } finally {
      setNaming(false);
    }
  }

  async function submitDecision() {
    if (!overview?.decision) {
      setError("Preencha todos os dados e marque os seis documentos antes de registrar uma decisão.");
      return;
    }
    if (!form || saving || naming || submitting) return;
    if (decisionChoice === "agreement") {
      const amount = Number(decisionAmount.replace(",", "."));
      if (!Number.isFinite(amount) || amount <= 0) {
        setError("Informe um valor positivo para submeter o acordo.");
        return;
      }
    }
    if (
      decisionChoice !== overview.decision.recommendation &&
      !decisionJustification.trim()
    ) {
      setError("Justifique a decisão quando ela divergir da recomendação do modelo.");
      return;
    }

    setSubmitting(true);
    setError(null);
    setFeedback(null);
    try {
      const updated = await persistForm();
      onProcessUpdated(updated);
      const decision = await apiFetch<SubmittedProcessDecision>(
        `/v1/processes/${encodeURIComponent(updated.case_number)}/decisions`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            recommendation: decisionChoice,
            amount:
              decisionChoice === "agreement"
                ? Number(decisionAmount.replace(",", "."))
                : null,
            justification: decisionJustification.trim() || null,
          }),
        },
      );
      setSubmittedDecision(decision);
      setFeedback("Decisão submetida e armazenada.");
      setRevision((current) => current + 1);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "Não foi possível submeter a decisão.");
    } finally {
      setSubmitting(false);
    }
  }

  if (error && (!overview || !form)) {
    return (
      <section className="financial-dashboard-state" role="alert">
        <AlertTriangle size={22} />
        <strong>Visão estratégica indisponível</strong>
        <p>{error}</p>
        <button
          onClick={() => {
            setError(null);
            setRevision((current) => current + 1);
          }}
          type="button"
        >
          <RefreshCw size={14} /> Tentar novamente
        </button>
      </section>
    );
  }

  if (!overview || !form) {
    return (
      <section className="financial-dashboard-state" aria-live="polite">
        <span className="spinner" />
        <strong>Calculando risco e estratégia</strong>
        <p>Consultando os dados salvos e o modelo local.</p>
      </section>
    );
  }

  const evidenceEntries = Object.entries(form.evidence) as Array<[EvidenceKey, boolean]>;
  const claimAmount = Number(form.claim_amount.replace(",", "."));
  const hasCompleteInputs =
    isMeaningfulCaseValue(form.title) &&
    isMeaningfulCaseValue(form.location) &&
    form.state.trim().length === 2 &&
    form.state.trim().toUpperCase() !== "NA" &&
    isMeaningfulCaseValue(form.subject) &&
    Number.isFinite(claimAmount) &&
    claimAmount > 0.01 &&
    evidenceEntries.every(([, available]) => available);
  const risk = overview.risk;
  const decision = overview.decision;
  const modelAvailable = hasCompleteInputs && risk !== null && decision !== null;
  const decisionTone = decision?.recommendation ?? "human_review";
  const riskStyle = {
    "--risk-angle": `${(risk?.loss_probability ?? 0) * 360}deg`,
  } as CSSProperties;

  return (
    <section className="financial-dashboard">
      <form className="financial-dashboard-inner" onSubmit={saveChanges}>
        <header className="financial-dashboard-title compact">
          <h2>Visão estratégica do processo</h2>
          <button className="financial-save-button" disabled={saving || naming || submitting} type="submit">
            {saving ? <span className="spinner" /> : <Save size={15} />}
            {saving ? "Salvando" : "Salvar alterações"}
          </button>
        </header>

        <div className="financial-overview-grid editable">
          <article className="financial-card case-profile-card">
            <div className="financial-card-heading">
              <span>Perfil do caso</span>
              <Scale size={16} />
            </div>
            <div className="financial-fields">
              <label>
                <span>Localização</span>
                <input
                  onChange={(event) => setForm({ ...form, location: event.target.value })}
                  value={form.location}
                />
              </label>
              <label>
                <span>UF</span>
                <input
                  maxLength={2}
                  onChange={(event) => setForm({ ...form, state: event.target.value.toUpperCase() })}
                  value={form.state}
                />
              </label>
              <label>
                <span>Tipo</span>
                <select
                  onChange={(event) =>
                    setForm({ ...form, sub_subject: event.target.value as "fraud" | "generic" })
                  }
                  value={form.sub_subject}
                >
                  <option value="fraud">Suspeita de fraude</option>
                  <option value="generic">Genérico</option>
                </select>
              </label>
              <label>
                <span>Valor da causa</span>
                <input
                  min="0.01"
                  onChange={(event) => setForm({ ...form, claim_amount: event.target.value })}
                  placeholder="N/A"
                  step="0.01"
                  type="number"
                  value={form.claim_amount}
                />
              </label>
            </div>
          </article>

          <article className="financial-card process-info-card">
            <div className="financial-card-heading">
              <span>Informações do processo</span>
              <Database size={16} />
            </div>
            <div className="financial-fields process-fields">
              <label className="process-name-field">
                <span>Nome do processo</span>
                <div>
                  <input
                    onChange={(event) => setForm({ ...form, title: event.target.value })}
                    value={form.title}
                  />
                  <button disabled={saving || naming || submitting} onClick={() => void inferTitle()} type="button">
                    {naming ? <span className="spinner" /> : <WandSparkles size={14} />}
                    {naming ? "Gerando" : "Sugerir com IA"}
                  </button>
                </div>
              </label>
              <label>
                <span>Número</span>
                <input
                  className="mono-value"
                  onChange={(event) => setForm({ ...form, case_number: event.target.value })}
                  value={form.case_number}
                />
              </label>
              <label>
                <span>Assunto</span>
                <input
                  onChange={(event) => setForm({ ...form, subject: event.target.value })}
                  value={form.subject}
                />
              </label>
            </div>
          </article>
        </div>


        <fieldset className="financial-evidence-editor">
          <legend>Documentos para análise</legend>
          <p>Marque os documentos disponíveis. A avaliação é liberada com os seis subsídios.</p>
          <div className="evidence-mini-list">
            {evidenceEntries.map(([key, available]) => (
              <label className={available ? "available" : "missing"} key={key}>
                <input
                  checked={available}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      evidence: { ...form.evidence, [key]: event.target.checked },
                    })
                  }
                  type="checkbox"
                />
                {available ? <FileCheck2 size={12} /> : <span className="empty-check" />}
                <span>{evidenceLabels[key]}</span>
              </label>
            ))}
          </div>
        </fieldset>

        {modelAvailable && risk && decision && (
          <>
            <div className="financial-metrics-grid complete">
              <article className="financial-metric risk-metric">
                <span className="metric-kicker">Risco de perda</span>
                <div className="metric-dial risk" style={riskStyle}>
                  <div>
                    <strong>{formatPercent(risk.loss_probability)}</strong>
                    <small>
                      {decision.risk_band === "high"
                        ? "alto"
                        : decision.risk_band === "medium"
                          ? "médio"
                          : "baixo"}
                    </small>
                  </div>
                </div>
              </article>

              <article className="financial-metric amount-metric">
                <span className="metric-kicker">Exposição estimada</span>
                <strong className="main-amount">{formatCurrency(risk.expected_condemnation)}</strong>
                <div className="amount-range">
                  <span>{formatCurrency(risk.condemnation_q10)}</span>
                  <div><i /></div>
                  <span>{formatCurrency(risk.condemnation_q90)}</span>
                </div>
              </article>
            </div>

            <aside className={`financial-suggestion-card ${decisionTone}`} aria-label="Sugestão da IA">
              <span>Sugestão da IA</span>
              <strong>{decisionLabels[decisionTone]}</strong>
            </aside>
          </>
        )}

        <article className={`financial-decision-card submission ${modelAvailable ? decisionTone : "no-data"}`}>
          <div className="decision-icon">
            {modelAvailable && decisionTone === "human_review" ? <AlertTriangle size={20} /> : <ShieldCheck size={20} />}
          </div>
          <div className="decision-copy">
            <span>Decisão do advogado</span>
            <h3>{modelAvailable ? "Registrar decisão" : "Aguardando dados completos"}</h3>
            <p>
              {modelAvailable
                ? "Esta escolha ficará disponível para a operação bancária."
                : "Preencha os dados do processo, marque os seis documentos e salve para liberar esta decisão."}
            </p>
          </div>
          <div className="decision-controls">
            <div className="decision-options" role="radiogroup" aria-label="Decisão do processo">
              {(Object.keys(decisionLabels) as DecisionChoice[]).map((choice) => (
                <label className={[decisionChoice === choice ? "selected" : "", !modelAvailable ? "disabled" : ""].filter(Boolean).join(" ")} key={choice}>
                  <input
                    checked={decisionChoice === choice}
                    disabled={!modelAvailable}
                    name="decision"
                    onChange={() => setDecisionChoice(choice)}
                    type="radio"
                    value={choice}
                  />
                  {decisionLabels[choice]}
                </label>
              ))}
            </div>
            {decisionChoice === "agreement" && (
              <label className="decision-amount-field">
                <span>Valor aprovado</span>
                <input
                  disabled={!modelAvailable}
                  min="0.01"
                  onChange={(event) => setDecisionAmount(event.target.value)}
                  placeholder="0,00"
                  step="0.01"
                  type="number"
                  value={decisionAmount}
                />
              </label>
            )}
            <label className="decision-justification-field">
              <span>Justificativa da decisão</span>
              <textarea
                disabled={!modelAvailable}
                maxLength={2000}
                onChange={(event) => setDecisionJustification(event.target.value)}
                placeholder={
                  decisionChoice === overview.decision?.recommendation
                    ? "Opcional quando a decisão segue o modelo"
                    : "Obrigatória para registrar uma divergência"
                }
                rows={3}
                value={decisionJustification}
              />
            </label>
          </div>
          <button
            className="submit-decision-button"
            disabled={!modelAvailable || saving || naming || submitting}
            onClick={() => void submitDecision()}
            type="button"
          >
            {submitting ? <span className="spinner" /> : <SendHorizontal size={15} />}
            {submitting ? "Submetendo" : "Submeter decisão"}
          </button>
          {submittedDecision && (
            <div className="submitted-decision-note">
              <CheckCircle2 size={14} />
              <span>
                Última decisão: {decisionLabels[submittedDecision.recommendation]}
                {submittedDecision.amount ? ` · ${formatCurrency(submittedDecision.amount)}` : ""}
                {` · ${formatDate(submittedDecision.created_at)}`}
              </span>
            </div>
          )}
        </article>

        {(feedback || error) && (
          <div className={error ? "financial-form-message error" : "financial-form-message success"} role="status">
            {error ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}
            {error ?? feedback}
          </div>
        )}

      </form>
    </section>
  );
}
