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


export type LegalProcess = {
  id: string;
  case_number: string;
  title: string;
  location: string;
  state: string;
  subject: string;
  sub_subject: "fraud" | "generic";
  claim_amount: number;
  evidence: EvidenceInput;
  default_question: string;
  is_draft: boolean;
  created_at: string;
  updated_at: string;
};

export type ProcessDocument = {
  id: string | null;
  case_number: string;
  path: string;
  original_filename: string;
  document_type: DocumentType;
  kind: "pdf" | "csv";
  source: "bundled" | "upload";
  size_bytes: number;
  sha256: string | null;
  created_at: string | null;
};

export type ProcessDocumentListResponse = {
  case_number: string;
  documents: ProcessDocument[];
};

export type ChatSession = {
  id: string;
  case_number: string;
  created_at: string;
  updated_at: string;
};

export type ChatMessage = {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  document_paths: string[];
  trace_id: string | null;
  created_at: string;
};

export type ChatHistoryResponse = {
  session: ChatSession;
  messages: ChatMessage[];
};

export type ChatStreamEvent =
  | {
      event: "ready";
      data: { chat_id: string; trace_id: string; document_count: number };
    }
  | {
      event: "tool_start";
      data: { tool: string; document_path: string };
    }
  | {
      event: "tool_end";
      data: { tool: string; document_path: string; status: string };
    }
  | { event: "token"; data: { text: string } }
  | {
      event: "complete";
      data: {
        message: ChatMessage;
        consulted_documents: string[];
        unreadable_documents: string[];
      };
    }
  | { event: "error"; data: { message: string; trace_id: string } };

export type ProcessDataRecord = {
  workbook_path: string;
  process_number: string;
  state: string;
  subject: string;
  sub_subject: "fraud" | "generic";
  claim_amount: number;
  evidence: EvidenceInput;
  source_rows: Record<string, number>;
  excluded_post_outcome_columns: string[];
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
