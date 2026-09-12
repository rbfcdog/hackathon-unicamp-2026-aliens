"use client";

import { useEffect, useState, type FormEvent } from "react";
import { ShieldCheck, X } from "lucide-react";
import type { AnalysisRequest, EvidenceInput, EvidenceKey } from "@/lib/types";

const EMPTY_EVIDENCE: EvidenceInput = {
  contract: false,
  bank_statement: false,
  credit_proof: false,
  dossier: false,
  debt_evolution: false,
  referenced_report: false,
};

const EVIDENCE_OPTIONS: Array<{ key: EvidenceKey; label: string }> = [
  { key: "contract", label: "Contrato" },
  { key: "bank_statement", label: "Extrato bancário" },
  { key: "credit_proof", label: "Comprovante de crédito" },
  { key: "dossier", label: "Dossiê de autenticidade" },
  { key: "debt_evolution", label: "Evolução da dívida" },
  { key: "referenced_report", label: "Laudo referenciado" },
];

type Props = {
  open: boolean;
  loading: boolean;
  onClose: () => void;
  onSubmit: (payload: AnalysisRequest) => Promise<void>;
};

export function NewAnalysisDialog({ open, loading, onClose, onSubmit }: Props) {
  const [caseNumber, setCaseNumber] = useState("");
  const [state, setState] = useState("SP");
  const [subSubject, setSubSubject] = useState<"fraud" | "generic">("generic");
  const [claimAmount, setClaimAmount] = useState("10000");
  const [evidence, setEvidence] = useState<EvidenceInput>(EMPTY_EVIDENCE);

  useEffect(() => {
    if (!open) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !loading) onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [loading, onClose, open]);

  if (!open) return null;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSubmit({
      case_number: caseNumber.trim(),
      state,
      sub_subject: subSubject,
      claim_amount: Number(claimAmount),
      evidence,
    });
  }

  function toggleEvidence(key: EvidenceKey) {
    setEvidence((current) => ({ ...current, [key]: !current[key] }));
  }

  return (
    <div
      className="dialog-backdrop"
      role="presentation"
      onMouseDown={loading ? undefined : onClose}
    >
      <section
        aria-labelledby="new-analysis-title"
        aria-modal="true"
        className="analysis-dialog"
        role="dialog"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="dialog-heading">
          <h2 id="new-analysis-title">Novo processo</h2>
          <button
            aria-label="Fechar formulário"
            className="icon-button"
            disabled={loading}
            onClick={onClose}
            type="button"
          >
            <X size={18} />
          </button>
        </div>

        <form className="analysis-form" onSubmit={handleSubmit}>
          <label className="field field-wide">
            <span>Número do processo</span>
            <input
              autoFocus
              maxLength={64}
              onChange={(event) => setCaseNumber(event.target.value)}
              placeholder="0000000-00.0000.0.00.0000"
              required
              value={caseNumber}
            />
          </label>

          <label className="field">
            <span>UF</span>
            <input
              maxLength={2}
              minLength={2}
              onChange={(event) => setState(event.target.value.toUpperCase())}
              pattern="[A-Za-z]{2}"
              required
              value={state}
            />
          </label>

          <label className="field">
            <span>Subassunto</span>
            <select
              onChange={(event) =>
                setSubSubject(event.target.value as "fraud" | "generic")
              }
              value={subSubject}
            >
              <option value="generic">Não reconhece operação</option>
              <option value="fraud">Suspeita de fraude</option>
            </select>
          </label>

          <label className="field field-wide">
            <span>Valor da causa</span>
            <div className="money-input">
              <b>R$</b>
              <input
                min="0.01"
                onChange={(event) => setClaimAmount(event.target.value)}
                required
                step="0.01"
                type="number"
                value={claimAmount}
              />
            </div>
          </label>

          <fieldset className="evidence-fieldset field-wide">
            <legend>Subsídios disponíveis</legend>
            <p>Marque somente os documentos efetivamente presentes.</p>
            <div className="evidence-options">
              {EVIDENCE_OPTIONS.map((option) => (
                <label className="evidence-option" key={option.key}>
                  <input
                    checked={evidence[option.key]}
                    onChange={() => toggleEvidence(option.key)}
                    type="checkbox"
                  />
                  <span className="custom-check" aria-hidden="true">
                    <ShieldCheck size={14} />
                  </span>
                  {option.label}
                </label>
              ))}
            </div>
          </fieldset>

          <div className="dialog-actions field-wide">
            <button className="primary-button" disabled={loading} type="submit">
              {loading ? <span className="spinner" /> : <ShieldCheck size={17} />}
              {loading ? "Criando processo" : "Criar e analisar"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
