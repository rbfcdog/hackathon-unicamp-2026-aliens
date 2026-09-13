import {
  AlertTriangle,
  ArrowUpRight,
  Calculator,
  CheckCircle2,
  CircleDollarSign,
  FileCheck2,
  Scale,
  ShieldAlert,
  Waypoints,
} from "lucide-react";
import type { AnalysisResponse } from "@/lib/types";

const currency = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});

const preciseCurrency = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
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


function roundCurrency(value: number): number {
  return Math.round(value * 100) / 100;
}

type Props = { analysis: AnalysisResponse };

export function AnalysisResultPanel({ analysis }: Props) {
  return <AnalysisResult analysis={analysis} />;
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

  const claimAmount = result.model_inputs?.claim_amount;
  const pricingUnavailable =
    result.expected_condemnation === null ||
    result.expected_defense_cost === null ||
    (claimAmount !== null && claimAmount !== undefined && claimAmount <= 0.01);
  const recommendationLabel = pricingUnavailable
    ? "Revisão necessária"
    : RECOMMENDATION_LABEL[result.recommendation];
  const explanation = pricingUnavailable
    ? "A avaliação de risco considera a UF, o tipo do processo e as evidências disponíveis. Informe o valor da causa para calcular a condenação esperada, o custo da defesa e a faixa de acordo."
    : result.explanation;
  const economics =
    !pricingUnavailable &&
    result.expected_condemnation !== null &&
    result.expected_defense_cost !== null
      ? (() => {
          const expectedCondemnation = result.expected_condemnation;
          const expectedDefenseCost = result.expected_defense_cost;
          const riskAdjustedLoss = roundCurrency(
            result.loss_probability * expectedCondemnation,
          );
          const fixedDefenseCost = roundCurrency(
            Math.max(0, expectedDefenseCost - riskAdjustedLoss),
          );
          const evidence = result.model_inputs?.evidence;
          const availableEvidence = evidence
            ? Object.values(evidence).filter(Boolean).length
            : null;

          return {
            expectedCondemnation,
            expectedDefenseCost,
            riskAdjustedLoss,
            fixedDefenseCost,
            availableEvidence,
          };
        })()
      : null;

  return (
    <section className="result-panel" aria-label="Resultado da análise">
      <div className="result-hero">
        <div>
          <span className="section-kicker">Recomendação</span>
          <h2>{recommendationLabel}</h2>
          <p>{explanation}</p>
        </div>
        <RiskDial value={result.loss_probability} />
      </div>

      <div className="metric-grid">
        <Metric
          icon={<Scale size={17} />}
          label="Custo total esperado"
          value={result.expected_defense_cost === null ? "Indisponível" : currency.format(result.expected_defense_cost)}
        />
        <Metric
          icon={<CircleDollarSign size={17} />}
          label="Condenação se houver perda"
          value={result.expected_condemnation === null ? "Indisponível" : currency.format(result.expected_condemnation)}
        />
        <Metric
          icon={<FileCheck2 size={17} />}
          label="Força documental"
          value={percentage.format(result.evidence_score)}
        />
      </div>

      {pricingUnavailable && (
        <div className="pricing-unavailable" role="status">
          <AlertTriangle size={18} />
          <div>
            <strong>Valor da causa não informado</strong>
            <span>Preencha esse campo no perfil do processo para liberar abertura, alvo e teto.</span>
          </div>
        </div>
      )}

      {!pricingUnavailable && result.agreement_range && (
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

      {economics && (
        <section className="economic-proof" aria-labelledby="economic-proof-title">
          <header className="economic-proof-heading">
            <div>
              <span className="section-kicker">Evidência econômica</span>
              <h3 id="economic-proof-title">Memória de cálculo da decisão</h3>
            </div>
            <div className="economic-proof-confidence">
              <Waypoints size={16} />
              <span>
                {economics.availableEvidence === null
                  ? "Base documental avaliada"
                  : `${economics.availableEvidence}/6 documentos avaliados`}
              </span>
            </div>
          </header>

          <div className="economic-proof-grid">
            <div className="calculation-ledger">
              <div className="calculation-ledger-title">
                <Calculator size={16} />
                <strong>Custo esperado da defesa</strong>
              </div>
              <dl>
                <div>
                  <dt>Probabilidade de perda</dt>
                  <dd>{percentage.format(result.loss_probability)}</dd>
                </div>
                <div>
                  <dt>Condenação em cenário desfavorável</dt>
                  <dd>{preciseCurrency.format(economics.expectedCondemnation)}</dd>
                </div>
                <div className="calculation-operation">
                  <dt>Risco financeiro</dt>
                  <dd>
                    {percentage.format(result.loss_probability)}
                    {" × "}
                    {preciseCurrency.format(economics.expectedCondemnation)}
                    {" = "}
                    {preciseCurrency.format(economics.riskAdjustedLoss)}
                  </dd>
                </div>
                <div>
                  <dt>Custo processual considerado</dt>
                  <dd>+ {preciseCurrency.format(economics.fixedDefenseCost)}</dd>
                </div>
                <div className="calculation-total">
                  <dt>Total esperado</dt>
                  <dd>{preciseCurrency.format(economics.expectedDefenseCost)}</dd>
                </div>
              </dl>
            </div>

            <div className="decision-threshold">
              <span className="section-kicker">Ponto de indiferença</span>
              <strong>{preciseCurrency.format(economics.expectedDefenseCost)}</strong>
              {result.recommendation === "defense" ? (
                <p>
                  A política recomenda defesa. Um acordo acima deste valor custa mais que
                  defender em valor esperado. O número é um teto econômico de contingência,
                  não uma oferta recomendada.
                </p>
              ) : result.agreement_range ? (
                <p>
                  O alvo de {preciseCurrency.format(result.agreement_range.target)} fica{" "}
                  {preciseCurrency.format(
                    economics.expectedDefenseCost - result.agreement_range.target,
                  )}{" "}
                  abaixo do custo esperado da defesa.
                </p>
              ) : (
                <p>
                  Este é o valor no qual acordo e defesa possuem o mesmo custo esperado.
                </p>
              )}
            </div>
          </div>

        </section>
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

    </section>
  );
}



function RiskDial({ value }: { value: number }) {
  return (
    <div className="risk-dial" style={{ "--risk": `${value * 100}%` } as React.CSSProperties}>
      <div>
        <strong>{percentage.format(value)}</strong>
        <span>Risco de perda</span>
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
