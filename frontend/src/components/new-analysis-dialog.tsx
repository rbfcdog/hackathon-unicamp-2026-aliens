"use client";

import {
  useCallback,
  useEffect,
  useState,
  type ChangeEvent,
  type FormEvent,
} from "react";
import { FilePlus2, FileText, ShieldCheck, X } from "lucide-react";
import { DOCUMENT_LABELS } from "@/lib/legal-documents";
import type {
  AnalysisRequest,
  DocumentType,
  EvidenceInput,
  EvidenceKey,
} from "@/lib/types";

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

const DOCUMENT_TYPES: DocumentType[] = [
  "case_record",
  "contract",
  "bank_statement",
  "credit_proof",
  "dossier",
  "debt_evolution",
  "referenced_report",
  "other",
];

const MAX_INITIAL_DOCUMENTS = 20;

export type PendingDocument = {
  id: string;
  file: File;
  documentType: DocumentType;
};

export type NewProcessRequest = Omit<AnalysisRequest, "documents"> & {
  title: string;
  location: string;
  subject: string;
  documents: PendingDocument[];
};

type Props = {
  open: boolean;
  loading: boolean;
  onClose: () => void;
  onSubmit: (payload: NewProcessRequest) => Promise<void>;
};

function formatFileSize(size: number) {
  if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function documentKey(file: File) {
  return `${file.name}-${file.size}-${file.lastModified}`;
}

export function NewAnalysisDialog({ open, loading, onClose, onSubmit }: Props) {
  const [caseNumber, setCaseNumber] = useState("");
  const [title, setTitle] = useState("");
  const [location, setLocation] = useState("");
  const [subject, setSubject] = useState("");
  const [state, setState] = useState("SP");
  const [subSubject, setSubSubject] = useState<"fraud" | "generic">("generic");
  const [claimAmount, setClaimAmount] = useState("");
  const [evidence, setEvidence] = useState<EvidenceInput>(EMPTY_EVIDENCE);
  const [documents, setDocuments] = useState<PendingDocument[]>([]);
  const [submissionError, setSubmissionError] = useState<string | null>(null);

  const resetForm = useCallback(() => {
    setCaseNumber("");
    setTitle("");
    setLocation("");
    setSubject("");
    setState("SP");
    setSubSubject("generic");
    setClaimAmount("");
    setEvidence(EMPTY_EVIDENCE);
    setDocuments([]);
    setSubmissionError(null);
  }, []);

  const closeDialog = useCallback(() => {
    if (loading) return;
    resetForm();
    onClose();
  }, [loading, onClose, resetForm]);

  useEffect(() => {
    if (!open) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeDialog();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [closeDialog, open]);

  if (!open) return null;

  function toggleEvidence(key: EvidenceKey) {
    setEvidence((current) => ({ ...current, [key]: !current[key] }));
  }

  function addDocuments(event: ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(event.target.files ?? []);
    const unsupported = selected.filter((file) => !/\.(pdf|csv)$/iu.test(file.name));
    const supported = selected.filter((file) => !unsupported.includes(file));
    const remainingSlots = Math.max(0, MAX_INITIAL_DOCUMENTS - documents.length);
    const accepted = supported.slice(0, remainingSlots);
    setDocuments((current) => {
      const existing = new Set(current.map(({ file }) => documentKey(file)));
      return [
        ...current,
        ...accepted
          .filter((file) => !existing.has(documentKey(file)))
          .map((file) => ({
            id: documentKey(file),
            file,
            documentType: "other" as const,
          })),
      ];
    });
    setSubmissionError(
      unsupported.length
        ? "Envie somente arquivos PDF ou CSV."
        : supported.length > accepted.length
          ? `A primeira análise aceita até ${MAX_INITIAL_DOCUMENTS} documentos.`
          : null,
    );
    event.target.value = "";
  }

  function updateDocumentType(id: string, documentType: DocumentType) {
    setDocuments((current) =>
      current.map((document) =>
        document.id === id ? { ...document, documentType } : document,
      ),
    );
  }

  function removeDocument(id: string) {
    setDocuments((current) =>
      current.filter((document) => document.id !== id),
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmissionError(null);
    const effectiveEvidence = { ...evidence };
    for (const document of documents) {
      if (document.documentType in effectiveEvidence) {
        effectiveEvidence[document.documentType as EvidenceKey] = true;
      }
    }

    try {
      await onSubmit({
        case_number: caseNumber.trim(),
        title: title.trim(),
        location: location.trim(),
        subject: subject.trim(),
        state,
        sub_subject: subSubject,
        claim_amount: Number(claimAmount),
        evidence: effectiveEvidence,
        documents,
      });
      resetForm();
      onClose();
    } catch (caught: unknown) {
      setSubmissionError(
        caught instanceof Error
          ? caught.message
          : "Não foi possível criar o processo.",
      );
    }
  }

  return (
    <div
      className="dialog-backdrop"
      role="presentation"
      onMouseDown={loading ? undefined : closeDialog}
    >
      <section
        aria-labelledby="new-analysis-title"
        aria-modal="true"
        className="analysis-dialog"
        role="dialog"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="dialog-heading">
          <div>
            <p className="dialog-kicker">Dossiê de entrada</p>
            <h2 id="new-analysis-title">Novo processo</h2>
          </div>
          <button
            aria-label="Fechar formulário"
            className="icon-button"
            disabled={loading}
            onClick={closeDialog}
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

          <label className="field">
            <span>Título do processo</span>
            <input
              maxLength={160}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Opcional"
              value={title}
            />
          </label>

          <label className="field">
            <span>Localização</span>
            <input
              maxLength={160}
              onChange={(event) => setLocation(event.target.value)}
              placeholder="Comarca ou tribunal"
              value={location}
            />
          </label>

          <label className="field field-wide">
            <span>Assunto</span>
            <input
              maxLength={255}
              onChange={(event) => setSubject(event.target.value)}
              placeholder="Ex.: empréstimo consignado"
              value={subject}
            />
          </label>

          <label className="field field-wide">
            <span>Valor da causa</span>
            <div className="money-input">
              <b>R$</b>
              <input
                min="0.01"
                onChange={(event) => setClaimAmount(event.target.value)}
                placeholder="N/A"
                required
                step="0.01"
                type="number"
                value={claimAmount}
              />
            </div>
          </label>

          <fieldset className="evidence-fieldset field-wide">
            <legend>Subsídios disponíveis</legend>
            <p>
              Os tipos escolhidos nos anexos também entram na análise.
            </p>
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

          <section
            aria-labelledby="new-process-documents"
            className="process-document-intake field-wide"
          >
            <div className="document-intake-heading">
              <div>
                <span id="new-process-documents">Documentos</span>
                <p>PDF ou CSV. Você pode anexar mais de um arquivo.</p>
              </div>
              <label className="document-picker">
                <FilePlus2 aria-hidden="true" size={15} />
                Selecionar arquivos
                <input
                  accept=".pdf,.csv,application/pdf,text/csv"
                  multiple
                  onChange={addDocuments}
                  type="file"
                />
              </label>
            </div>

            {documents.length > 0 && (
              <ul className="document-intake-list" aria-live="polite">
                {documents.map((document) => (
                  <li key={document.id}>
                    <div className="document-intake-file">
                      <FileText aria-hidden="true" size={15} />
                      <span title={document.file.name}>{document.file.name}</span>
                      <small>{formatFileSize(document.file.size)}</small>
                    </div>
                    <label className="document-type-select">
                      <span className="sr-only">
                        Tipo de {document.file.name}
                      </span>
                      <select
                        onChange={(event) =>
                          updateDocumentType(
                            document.id,
                            event.target.value as DocumentType,
                          )
                        }
                        value={document.documentType}
                      >
                        {DOCUMENT_TYPES.map((documentType) => (
                          <option key={documentType} value={documentType}>
                            {DOCUMENT_LABELS[documentType]}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button
                      aria-label={`Remover ${document.file.name}`}
                      className="remove-document"
                      onClick={() => removeDocument(document.id)}
                      type="button"
                    >
                      <X size={15} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {submissionError && (
            <p className="dialog-error field-wide" role="alert">
              {submissionError}
            </p>
          )}

          <div className="dialog-actions field-wide">
            <button className="primary-button" disabled={loading} type="submit">
              {loading ? <span className="spinner" /> : <ShieldCheck size={17} />}
              {loading
                ? "Criando processo"
                : documents.length
                  ? "Criar e analisar documentos"
                  : "Criar processo"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
