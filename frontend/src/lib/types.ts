export type EvidenceKey =
  | "contract"
  | "bank_statement"
  | "credit_proof"
  | "dossier"
  | "debt_evolution"
  | "referenced_report";

export type DocumentType = EvidenceKey | "case_record" | "other";

export type EvidenceInput = Record<EvidenceKey, boolean>;

export type DocumentReference = {
  path: string;
  document_type: DocumentType;
};

export type DocumentCatalogItem = {
  path: string;
  kind: "pdf" | "spreadsheet" | "csv";
  size_bytes: number;
};

export type DocumentCatalogResponse = {
  document_root: string;
  documents: DocumentCatalogItem[];
};

export type AgreementRange = {
  opening: number;
  target: number;
  ceiling: number;
};

export type AnalysisRequest = {
  case_number: string;
  state: string;
  sub_subject: "fraud" | "generic";
  claim_amount: number;
  evidence: EvidenceInput;
};

export type AnalysisResult = {
  recommendation: "agreement" | "defense" | "human_review";
  risk_band: "low" | "medium" | "high";
  evidence_score: number;
  loss_probability: number;
  expected_condemnation: number;
  condemnation_q10: number;
  condemnation_q50: number;
  condemnation_q90: number;
  model_disagreement: number;
  component_probabilities: Record<string, number>;
  ensemble_weights: Record<string, number>;
  requires_model_review: boolean;
  model_version: string;
  expected_defense_cost: number;
  evaluated_agreement_cost: number | null;
  agreement_cheaper: boolean | null;
  agreement_range: AgreementRange | null;
  next_action: "propose_agreement" | "prepare_defense" | "human_review";
  human_review_reason: string | null;
  factors_for_agreement: string[];
  factors_for_defense: string[];
  explanation: string;
  policy_version: string;
};

export type AnalysisResponse = {
  id: string;
  case_number: string;
  status: "processing" | "completed" | "failed";
  request: AnalysisRequest;
  result: AnalysisResult | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type ReviewFinding = {
  issue: string;
  conclusion: string;
  reasoning: string;
  citations: Array<{
    document_path: string;
    locator: string;
    excerpt: string;
  }>;
};

export type ReviewResponse = {
  case_number: string;
  disposition:
    | "grant_claim"
    | "deny_claim"
    | "partial_grant"
    | "insufficient_evidence";
  confidence: number;
  summary: string;
  findings: ReviewFinding[];
  missing_evidence: string[];
  consulted_documents: string[];
  unreadable_documents: string[];
  model: string;
  trace_id: string;
  tracing_enabled: boolean;
  ml_analysis: {
    loss_probability: number;
    expected_condemnation: number;
    condemnation_q10: number;
    condemnation_q50: number;
    condemnation_q90: number;
    model_disagreement: number;
    requires_model_review: boolean;
    model_version: string;
  } | null;
  strategy: {
    recommendation: "agreement" | "defense" | "human_review";
    risk_band: "low" | "medium" | "high";
    expected_defense_cost: number;
    evaluated_agreement_cost: number | null;
    agreement_cheaper: boolean | null;
    agreement_range: AgreementRange | null;
    next_action: "propose_agreement" | "prepare_defense" | "human_review";
    human_review_reason: string | null;
    if_agreement_rejected: "counterproposal" | null;
  } | null;
  model_card_consulted: boolean;
  ml_tool_errors: string[];
  document_node_reads: Record<string, string[]>;
};
