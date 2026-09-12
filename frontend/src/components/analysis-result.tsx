import {
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  CircleDollarSign,
  FileCheck2,
  Scale,
  ShieldAlert,
} from "lucide-react";
import type { AnalysisResponse, ReviewResponse } from "@/lib/types";

const currency = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});

const percentage = new Intl.NumberFormat("pt-BR", {
  style: "percent",
  maximumFractionDigits: 1,
});

const RECOMMENDATION_LABEL = {
  agreement: "Propor acordo",
  defense: "Preparar defesa",
  human_review: "Revisão humana",
};

const DISPOSITION_LABEL = {
  grant_claim: "Procedência",
  deny_claim: "Improcedência",
  partial_grant: "Procedência parcial",
  insufficient_evidence: "Prova insuficiente",
};

type Props =
  | { analysis: AnalysisResponse; review?: never }
  | { analysis?: never; review: ReviewResponse };

export function AnalysisResultPanel({ analysis, review }: Props) {
  if (analysis) return <AnalysisResult analysis={analysis} />;
  return <ReviewResult review={review} />;
}

function AnalysisResult({ analysis }: { analysis: AnalysisResponse }) {
  const result = analysis.result;
  if (!result) {
    return (
      <div className="empty-result">
        <AlertTriangle size={20} />
        <p>{analysis.error_message ?? "A análise ainda não produziu um resultado."}</p>
      </div>
    );
  }

  return (
    <section className="result-panel" aria-label="Resultado da análise">
      <div className="result-hero">
        <div>
          <span className="section-kicker">Recomendação da política</span>
          <h2>{RECOMMENDATION_LABEL[result.recommendation]}</h2>
          <p>{result.explanation}</p>
        </div>
        <RiskDial value={result.loss_probability} />
      </div>

      <div className="metric-grid">
        <Metric
          icon={<Scale size={17} />}
          label="Custo esperado da defesa"
          value={currency.format(result.expected_defense_cost)}
        />
        <Metric
          icon={<CircleDollarSign size={17} />}
          label="Condenação esperada"
          value={currency.format(result.expected_condemnation)}
        />
        <Metric
          icon={<FileCheck2 size={17} />}
          label="Força documental"
          value={percentage.format(result.evidence_score)}
        />
      </div>

      {result.agreement_range && (
        <div className="agreement-band">
          <div>
            <span>Abertura</span>
            <strong>{currency.format(result.agreement_range.opening)}</strong>
          </div>
          <ArrowUpRight size={18} />
          <div>
            <span>Alvo</span>
            <strong>{currency.format(result.agreement_range.target)}</strong>
          </div>
          <ArrowUpRight size={18} />
          <div>
            <span>Teto</span>
            <strong>{currency.format(result.agreement_range.ceiling)}</strong>
          </div>
        </div>
      )}

      <div className="factor-columns">
        <FactorList
          icon={<CheckCircle2 size={16} />}
          items={result.factors_for_defense}
          title="Fatores para defesa"
        />
        <FactorList
          icon={<ShieldAlert size={16} />}
          items={result.factors_for_agreement}
          title="Fatores para acordo"
        />
      </div>

      <footer className="audit-footer">
        <span>Política {result.policy_version}</span>
        <span>Modelo {result.model_version}</span>
        <span>ID {analysis.id.slice(0, 8)}</span>
      </footer>
    </section>
  );
}

function ReviewResult({ review }: { review: ReviewResponse }) {
  return (
    <section className="result-panel" aria-label="Resultado da revisão documental">
      <div className="result-hero review-hero">
        <div>
          <span className="section-kicker">Parecer documental</span>
          <h2>{DISPOSITION_LABEL[review.disposition]}</h2>
          <p>{review.summary}</p>
        </div>
        <RiskDial
          label="Confiança"
          value={review.confidence}
          risk={review.ml_analysis?.loss_probability}
        />
      </div>

      {review.strategy && (
        <div className="strategy-strip">
          <div>
            <span>Estratégia</span>
            <strong>{RECOMMENDATION_LABEL[review.strategy.recommendation]}</strong>
          </div>
          <div>
            <span>Custo esperado</span>
            <strong>{currency.format(review.strategy.expected_defense_cost)}</strong>
          </div>
          <div>
            <span>Risco</span>
            <strong>{review.strategy.risk_band}</strong>
          </div>
          {review.strategy.agreement_range && (
            <div>
              <span>Valor-alvo do acordo</span>
              <strong>{currency.format(review.strategy.agreement_range.target)}</strong>
            </div>
          )}
        </div>
      )}

      <div className="findings-list">
        {review.findings.map((finding, index) => (
          <article className="finding-card" key={`${finding.issue}-${index}`}>
            <span className="finding-index">{String(index + 1).padStart(2, "0")}</span>
            <div>
              <h3>{finding.issue}</h3>
              <strong>{finding.conclusion}</strong>
              <p>{finding.reasoning}</p>
              {finding.citations.map((citation) => (
                <blockquote key={`${citation.document_path}-${citation.locator}`}>
                  “{citation.excerpt}”
                  <cite>{citation.locator}</cite>
                </blockquote>
              ))}
            </div>
          </article>
        ))}
      </div>

      <footer className="audit-footer">
        <span>{review.consulted_documents.length} documentos consultados</span>
        <span>Modelo {review.model}</span>
        <span>Trace {review.trace_id.slice(0, 8)}</span>
      </footer>
    </section>
  );
}

function RiskDial({
  value,
  label = "Risco de perda",
  risk,
}: {
  value: number;
  label?: string;
  risk?: number;
}) {
  return (
    <div className="risk-dial" style={{ "--risk": `${value * 100}%` } as React.CSSProperties}>
      <div>
        <strong>{percentage.format(value)}</strong>
        <span>{label}</span>
        {risk !== undefined && <small>Risco {percentage.format(risk)}</small>}
      </div>
    </div>
  );
}

function Metric({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="metric-card">
      <span>{icon}</span>
      <div>
        <small>{label}</small>
        <strong>{value}</strong>
      </div>
    </div>
  );
}

function FactorList({
  icon,
  items,
  title,
}: {
  icon: React.ReactNode;
  items: string[];
  title: string;
}) {
  return (
    <div className="factor-list">
      <h3>{icon}{title}</h3>
      {items.length ? (
        <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul>
      ) : (
        <p>Nenhum fator adicional registrado.</p>
      )}
    </div>
  );
}
