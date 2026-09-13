"use client";
// Financial dashboard lets counsel register case data and assess documented evidence.


import { useEffect, useState, type CSSProperties, type FormEvent } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Database,
  FileCheck2,
  FileText,
  PencilLine,
  RefreshCw,
  Save,
  Scale,
  SendHorizontal,
  ShieldCheck,
  WandSparkles,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import type {
  AgreementJustificationReview,
  EvidenceInput,
  EvidenceKey,
  EvidenceMatrixEntry,
  EvidenceMatrixResponse,
  LegalProcess,
  ProcessFinancialOverview,
  SubmittedProcessDecision,
} from "@/lib/types";

type Props = {
  legalProcess: LegalProcess;
  onProcessUpdated: (legalProcess: LegalProcess) => void;
  onRequestAgreementJustification: () => void;
};

type EditableProcess = {
  case_number: string;
  title: string;
  state: string;
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

type DecisionJustificationDrafts = Record<DecisionChoice, string>;

const emptyDecisionJustifications: DecisionJustificationDrafts = {
  agreement: "",
  defense: "",
  human_review: "",
};

const reviewVerdictLabels: Record<AgreementJustificationReview["verdict"], string> = {
  supported: "Justificativa sustentada pelos documentos",
  partially_supported: "Justificativa parcialmente sustentada",
  insufficient_evidence: "Documentação insuficiente para validar a justificativa",
  not_supported: "Justificativa não sustentada pelos documentos",
};

const evidenceMatrixStatusLabels: Record<EvidenceMatrixEntry["status"], string> = {
  supported: "Sustentado",
  contradicted: "Contradito",
  no_evidence: "Sem prova",
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




function editableProcess(overview: ProcessFinancialOverview): EditableProcess {
  return {
    case_number: overview.case_number,
    title: overview.title,
    state: overview.state,
    sub_subject: overview.sub_subject,
    claim_amount: overview.claim_amount > 0.01 ? String(overview.claim_amount) : "",
    evidence: overview.evidence,
  };
}

export function ProcessFinancialDashboard({
  legalProcess,
  onProcessUpdated,
  onRequestAgreementJustification,
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
  const [decisionJustifications, setDecisionJustifications] =
    useState<DecisionJustificationDrafts>(emptyDecisionJustifications);
  const [submittedDecision, setSubmittedDecision] = useState<SubmittedProcessDecision | null>(null);
  const [editingDecision, setEditingDecision] = useState(false);
  const [evidenceMatrix, setEvidenceMatrix] = useState<EvidenceMatrixResponse | null>(null);
  const [evidenceMatrixError, setEvidenceMatrixError] = useState<string | null>(null);
  const [evidenceMatrixRevision, setEvidenceMatrixRevision] = useState(0);
  const decisionJustification = decisionJustifications[decisionChoice];

  useEffect(() => {
    const controller = new AbortController();

    apiFetch<ProcessFinancialOverview>(
      `/v1/processes/${encodeURIComponent(legalProcess.case_number)}/financial-overview`,
      { signal: controller.signal },
    )
      .then((result) => {
        setOverview(result);
        setForm(editableProcess(result));
        const choice =
          result.latest_decision?.recommendation ??
          result.decision?.recommendation ??
          "human_review";
        const justifications = {
          ...emptyDecisionJustifications,
          ...result.decision_justifications,
        };
        if (result.latest_decision?.justification) {
          justifications[choice] = result.latest_decision.justification;
        }
        setSubmittedDecision(result.latest_decision);
        setEditingDecision(result.latest_decision === null);
        setDecisionChoice(choice);
        setDecisionAmount(
          result.latest_decision?.amount
            ? String(result.latest_decision.amount)
            : result.decision?.agreement_range
              ? String(result.decision.agreement_range.target)
              : "",
        );
        setDecisionJustifications(justifications);
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

  useEffect(() => {
    const controller = new AbortController();


    apiFetch<EvidenceMatrixResponse>(
      `/v1/processes/${encodeURIComponent(legalProcess.case_number)}/evidence-matrix`,
      { signal: controller.signal },
    )
      .then((result) => {
        setEvidenceMatrix(result);
        setEvidenceMatrixError(null);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setEvidenceMatrix(null);
        setEvidenceMatrixError(
          caught instanceof Error
            ? caught.message
            : "Não foi possível organizar as provas documentais.",
        );
      });

    return () => controller.abort();
  }, [legalProcess.case_number, revision, evidenceMatrixRevision]);

  async function persistForm(): Promise<LegalProcess> {
    if (!form) throw new Error("Os campos do processo ainda não foram carregados.");
    const claimAmount = Number(form.claim_amount.replace(",", "."));
    if (!form.case_number.trim() || !form.title.trim()) {
      throw new Error("Preencha o nome e o número do processo.");
    }
    if (form.state.trim().length !== 2) {
      throw new Error("A UF precisa ter exatamente duas letras.");
    }
    if (!Number.isFinite(claimAmount) || claimAmount <= 0) {
      throw new Error("Preencha um valor da causa maior que zero.");
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
          state: form.state.trim().toUpperCase(),
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
      setError(caught instanceof Error ? caught.message : "Não foi possível sugerir o nome.");
    } finally {
      setNaming(false);
    }
  }

  async function submitDecision() {
    if (!form || saving || naming || submitting || (submittedDecision && !editingDecision)) return;
    if (decisionChoice === "agreement") {
      const amount = Number(decisionAmount.replace(",", "."));
      if (!Number.isFinite(amount) || amount <= 0) {
        setError("Informe um valor positivo para submeter o acordo.");
        return;
      }
    }
    if (
      overview?.decision &&
      decisionChoice !== overview.decision.recommendation &&
      !decisionJustification.trim()
    ) {
      setError("Justifique a decisão quando ela divergir da recomendação atual.");
      return;
    }

    setSubmitting(true);
    setError(null);
    setFeedback(null);
    try {
      const decision = await apiFetch<SubmittedProcessDecision>(
        `/v1/processes/${encodeURIComponent(legalProcess.case_number)}/decisions`,
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
      setEditingDecision(false);
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
        <p>Consultando as informações salvas do processo.</p>
      </section>
    );
  }

  const evidenceEntries = Object.entries(form.evidence) as Array<[EvidenceKey, boolean]>;
  const claimAmount = Number(form.claim_amount.replace(",", "."));
  const missingAgentInputs = [
    form.state.trim().length === 2 && form.state.trim().toUpperCase() !== "NA"
      ? null
      : "UF",
    Number.isFinite(claimAmount) && claimAmount > 0.01 ? null : "valor da causa",
  ].filter((value): value is string => value !== null);
  const risk = overview.risk;
  const decision = overview.decision;
  const modelAvailable = risk !== null && decision !== null;
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
                    {naming ? "Gerando" : "Sugerir nome"}
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
            </div>
          </article>
        </div>


        <fieldset className="financial-evidence-editor">
          <legend>Documentos para análise</legend>
          <p>A análise considera os documentos reconhecidos, mas a quantidade não bloqueia o envio.</p>
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

        <section aria-labelledby="evidence-matrix-title" className="evidence-matrix">
          <header className="evidence-matrix-header">
            <div>
              <span>Leitura documental</span>
              <h3 id="evidence-matrix-title">Alegações e provas</h3>
            </div>
            <button
              onClick={() => setEvidenceMatrixRevision((current) => current + 1)}
              type="button"
            >
              <RefreshCw size={14} />
              Atualizar
            </button>
          </header>
          {evidenceMatrixError ? (
            <div className="evidence-matrix-message error" role="alert">
              <p>{evidenceMatrixError}</p>
              <button
                onClick={() => setEvidenceMatrixRevision((current) => current + 1)}
                type="button"
              >
                Tentar novamente
              </button>
            </div>
          ) : !evidenceMatrix ? (
            <div aria-live="polite" className="evidence-matrix-message" role="status">
              <span className="spinner" />
              Organizando as evidências documentais.
            </div>
          ) : (
            <div className="evidence-matrix-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Ponto</th>
                    <th>Situação</th>
                    <th>Leitura</th>
                    <th>Documento</th>
                  </tr>
                </thead>
                <tbody>
                  {evidenceMatrix.entries.map((entry) => (
                    <tr key={entry.question}>
                      <th scope="row">{entry.question}</th>
                      <td>
                        <span className={`evidence-matrix-status ${entry.status}`}>
                          {evidenceMatrixStatusLabels[entry.status]}
                        </span>
                      </td>
                      <td>{entry.explanation}</td>
                      <td>
                        {entry.citations.length > 0 ? (
                          <div className="evidence-matrix-citations">
                            {entry.citations.map((citation) => (
                              <a
                                href={`/api/backend/v1/processes/${encodeURIComponent(
                                  legalProcess.case_number,
                                )}/documents/content?document_path=${encodeURIComponent(
                                  citation.document_path,
                                )}#page=${citation.page}`}
                                key={`${citation.document_path}-${citation.page}`}
                                rel="noreferrer"
                                target="_blank"
                              >
                                <FileText size={13} />
                                {citation.document_name} · p. {citation.page}
                              </a>
                            ))}
                          </div>
                        ) : (
                          <span className="evidence-matrix-no-source">
                            Sem página referenciada
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

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

            <aside
              aria-label="Sugestão de encaminhamento"
              className={`financial-suggestion-card ${decisionTone}`}
            >
              <span>Sugestão de encaminhamento</span>
              <strong>{decisionLabels[decisionTone]}</strong>
            </aside>
          </>
        )}

        {modelAvailable && (
          <section className="agreement-justification-section" aria-labelledby="agreement-review-title">
            {overview.agreement_justification_review && (
              <article
                className={`agreement-justification-review ${overview.agreement_justification_review.verdict}`}
              >
                <div>
                  <FileCheck2 aria-hidden="true" size={20} />
                  <div>
                    <span>Revisão da justificativa</span>
                    <h3>{reviewVerdictLabels[overview.agreement_justification_review.verdict]}</h3>
                  </div>
                </div>
                <p>{overview.agreement_justification_review.summary}</p>
                {overview.agreement_justification_review.supporting_evidence.length > 0 && (
                  <ul>
                    {overview.agreement_justification_review.supporting_evidence.map((evidence) => (
                      <li key={evidence}>{evidence}</li>
                    ))}
                  </ul>
                )}
                {overview.agreement_justification_review.missing_documents.length > 0 && (
                  <p className="review-missing-documents">
                    Ainda faltam: {overview.agreement_justification_review.missing_documents.join(", ")}.
                  </p>
                )}
                <small>Esta conferência não altera o risco nem a exposição estimada.</small>
              </article>
            )}
            <article className="agreement-justification-card">
              <div>
                <span>Conferência documental</span>
                <h3 id="agreement-review-title">Revisar justificativa no chat</h3>
                <p>
                  Explique por que a decisão escolhida é adequada. A próxima mensagem será
                  confrontada com os documentos e a fundamentação já registrados.
                </p>
              </div>
              <button onClick={onRequestAgreementJustification} type="button">
                <FileCheck2 size={16} />
                Justificar no chat
              </button>
            </article>
          </section>
        )}

        <article
          className={`financial-decision-card submission ${modelAvailable ? decisionTone : "no-data"} ${
            submittedDecision && !editingDecision ? "locked" : ""
          }`}
        >
          <div className="decision-icon">
            {modelAvailable && decisionTone === "human_review" ? <AlertTriangle size={20} /> : <ShieldCheck size={20} />}
          </div>
          <div className="decision-copy">
            <span>Decisão do processo</span>
            <h3>{submittedDecision && !editingDecision ? "Decisão registrada" : "Registrar decisão"}</h3>
            <p>
              {submittedDecision && !editingDecision
                ? "Clique em editar para alterar esta decisão."
                : modelAvailable
                  ? "A recomendação está disponível."
                  : missingAgentInputs.length > 0
                    ? `Faltam ${missingAgentInputs.join(" e ")} para concluir a análise. Você pode submeter agora.`
                    : "Salve as alterações para atualizar a recomendação. Você pode submeter agora."}
            </p>
          </div>
          <div className="decision-controls">
            <div className="decision-options" role="radiogroup" aria-label="Decisão do processo">
              {(Object.keys(decisionLabels) as DecisionChoice[]).map((choice) => (
                <label className={decisionChoice === choice ? "selected" : ""} key={choice}>
                  <input
                    checked={decisionChoice === choice}
                    disabled={saving || naming || submitting || Boolean(submittedDecision && !editingDecision)}
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
                  disabled={saving || naming || submitting || Boolean(submittedDecision && !editingDecision)}
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
                disabled={saving || naming || submitting || Boolean(submittedDecision && !editingDecision)}
                maxLength={2000}
                onChange={(event) =>
                  setDecisionJustifications((current) => ({
                    ...current,
                    [decisionChoice]: event.target.value,
                  }))
                }
                placeholder={
                  overview.decision_justifications
                    ? "Sugestão da análise; edite antes de enviar"
                    : !overview.decision || decisionChoice === overview.decision.recommendation
                      ? "Opcional"
                      : "Obrigatória quando a decisão for diferente da recomendação"
                }
                rows={3}
                value={decisionJustification}
              />
            </label>
          </div>
          <button
            className={`submit-decision-button ${
              submittedDecision && !editingDecision ? "edit-decision-button" : ""
            }`}
            disabled={saving || naming || submitting}
            onClick={() => {
              if (submittedDecision && !editingDecision) {
                setEditingDecision(true);
                setFeedback(null);
                setError(null);
                return;
              }
              void submitDecision();
            }}
            type="button"
          >
            {submittedDecision && !editingDecision ? (
              <PencilLine size={15} />
            ) : submitting ? (
              <span className="spinner" />
            ) : (
              <SendHorizontal size={15} />
            )}
            {submittedDecision && !editingDecision
              ? "Editar decisão"
              : submitting
                ? "Submetendo"
                : "Submeter decisão"}
          </button>
          {submittedDecision && (
            <div className="submitted-decision-note">
              <CheckCircle2 size={14} />
              <span>
                Decisão registrada: {decisionLabels[submittedDecision.recommendation]}
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
