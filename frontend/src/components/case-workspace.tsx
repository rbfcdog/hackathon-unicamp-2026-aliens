"use client";

import { useState } from "react";
import {
  ArrowLeft,
  Bot,
  CheckCircle2,
  FileText,
  FolderOpen,
  ScanSearch,
  Sparkles,
} from "lucide-react";
import { AnalysisResultPanel } from "./analysis-result";
import {
  DOCUMENT_LABELS,
  documentTypeFromPath,
  type DemoCase,
} from "@/lib/demo-cases";
import type { DocumentCatalogItem, ReviewResponse } from "@/lib/types";

const currency = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});

type Props = {
  demoCase: DemoCase;
  documents: DocumentCatalogItem[];
  error: string | null;
  loading: boolean;
  review: ReviewResponse | null;
  onBack: () => void;
  onRunReview: (question: string) => Promise<void>;
};

export function CaseWorkspace({
  demoCase,
  documents,
  error,
  loading,
  review,
  onBack,
  onRunReview,
}: Props) {
  const [question, setQuestion] = useState(demoCase.question);

  return (
    <div className="case-workspace">
      <button className="back-button" onClick={onBack} type="button">
        <ArrowLeft size={15} /> Voltar à visão geral
      </button>

      <header className="case-heading">
        <div>
          <span className="section-kicker">{demoCase.eyebrow}</span>
          <h1>{demoCase.title}</h1>
          <p className="mono-label">CNJ {demoCase.caseNumber}</p>
        </div>
        <div className="case-meta">
          <div><span>Origem</span><strong>{demoCase.location}</strong></div>
          <div><span>Valor da causa</span><strong>{currency.format(demoCase.claimAmount)}</strong></div>
          <div><span>Documentos</span><strong>{String(documents.length).padStart(2, "0")}</strong></div>
        </div>
      </header>

      <div className="evidence-workbench">
        <section className="document-docket" aria-labelledby="documents-title">
          <div className="panel-heading">
            <div>
              <span className="section-kicker">Trilho de evidências</span>
              <h2 id="documents-title">Autos e subsídios</h2>
            </div>
            <span className="verified-label"><CheckCircle2 size={14} /> Catálogo verificado</span>
          </div>

          <div className="document-rail">
            {documents.map((document, index) => {
              const type = documentTypeFromPath(document.path);
              return (
                <article className="document-card" key={document.path}>
                  <span className="rail-node">{String(index + 1).padStart(2, "0")}</span>
                  <div className="document-icon" aria-hidden="true">
                    {type === "case_record" ? <FolderOpen size={18} /> : <FileText size={18} />}
                  </div>
                  <div>
                    <h3>{DOCUMENT_LABELS[type]}</h3>
                    <p>{document.path.split("/").at(-1)?.replaceAll("_", " ")}</p>
                  </div>
                  <span className="document-size">{Math.ceil(document.size_bytes / 1024)} KB</span>
                </article>
              );
            })}
          </div>
        </section>

        <aside className="review-console">
          <div className="console-mark" aria-hidden="true"><Bot size={20} /></div>
          <span className="section-kicker">Revisão assistida</span>
          <h2>O que precisa ser verificado?</h2>
          <p>O agente lê somente os documentos listados e devolve citações auditáveis.</p>
          <label>
            <span>Pergunta jurídica</span>
            <textarea
              disabled={loading}
              maxLength={2000}
              minLength={10}
              onChange={(event) => setQuestion(event.target.value)}
              rows={6}
              value={question}
            />
          </label>
          <button
            className="primary-button full-button"
            disabled={loading || question.trim().length < 10 || documents.length === 0}
            onClick={() => onRunReview(question.trim())}
            type="button"
          >
            {loading ? <span className="spinner" /> : <ScanSearch size={17} />}
            {loading ? "Lendo evidências" : "Executar revisão"}
          </button>
          <div className="console-note">
            <Sparkles size={14} />
            <span>ML estima risco. A política decide. O LLM fundamenta com fontes.</span>
          </div>
        </aside>
      </div>

      {error && <div className="inline-error" role="alert">{error}</div>}
      {review && <AnalysisResultPanel review={review} />}
    </div>
  );
}
