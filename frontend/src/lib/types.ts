// Shared frontend contracts keep API responses consistent across workspaces.


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
  state: string;
  sub_subject: "fraud" | "generic";
  claim_amount: number;
  evidence: EvidenceInput;
  default_question: string;
  model_inputs_edited: boolean;
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

export type EvidenceMatrixCitation = {
  document_path: string;
  document_name: string;
  page: number;
};

export type EvidenceMatrixEntry = {
  question:
    | "Houve contratação?"
    | "O crédito entrou na conta?"
    | "Os descontos batem?"
    | "A assinatura é compatível?";
  status: "supported" | "contradicted" | "no_evidence";
  explanation: string;
  citations: EvidenceMatrixCitation[];
};

export type EvidenceMatrixResponse = {
  entries: EvidenceMatrixEntry[];
};


export type ChatSession = {
  id: string;
  case_number: string;
  created_at: string;
  updated_at: string;
};

export type ChatToolCall = {
  id: string;
  tool: string;
  document_path: string;
  status: "complete" | "error";
};


export type ChatMessage = {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  document_paths: string[];
  tool_calls: ChatToolCall[];

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
      data: { id: string; tool: string; document_path: string };
    }
  | {
      event: "tool_end";
      data: { id: string; tool: string; document_path: string; status: string };
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

export type AgreementJustificationReview = {
  verdict:
    | "supported"
    | "partially_supported"
    | "insufficient_evidence"
    | "not_supported";
  summary: string;
  supporting_evidence: string[];
  missing_documents: string[];
};

export type SubmittedProcessDecision = {
  id: string;
  process_id: string;
  recommendation: "agreement" | "defense" | "human_review";
  amount: number | null;
  justification: string | null;
  bank_status: "pending" | "approved";
  bank_reviewed_at: string | null;
  outcome: "pending" | "favorable" | "settled" | "unfavorable";
  actual_cost: number | null;
  outcome_recorded_at: string | null;
  negotiation_status: NegotiationStatus;
  negotiation_amount: number | null;
  negotiation_updated_at: string | null;
  created_at: string;
};

export type ProcessFinancialOverview = {
  case_number: string;
  title: string;
  updated_at: string;
  input_source: "workbook_row" | "process_registry";
  workbook_path: string;
  source_rows: Record<string, number>;
  state: string;
  sub_subject: "fraud" | "generic";
  claim_amount: number;
  evidence: EvidenceInput;
  evidence_score: number;
  risk: {
    loss_probability: number;
    expected_condemnation: number;
    condemnation_q10: number;
    condemnation_q50: number;
    condemnation_q90: number;
    model_disagreement: number;
    component_probabilities: Record<string, number>;
    requires_model_review: boolean;
    model_version: string;
  } | null;
  decision: {
    recommendation: "agreement" | "defense" | "human_review";
    risk_band: "low" | "medium" | "high";
    expected_defense_cost: number;
    evaluated_agreement_cost: number | null;
    agreement_range: AgreementRange | null;
    next_action: "propose_agreement" | "prepare_defense" | "human_review";
    human_review_reason: string | null;
  } | null;
  latest_decision: SubmittedProcessDecision | null;
  agreement_justification_review: AgreementJustificationReview | null;
  decision_justifications: {
    agreement: string;
    defense: string;
    human_review: string;
  } | null;
};
export type DecisionChoice = "agreement" | "defense" | "human_review";
export type AdherenceStatus = "adherent" | "justified" | "divergent" | "unavailable";
export type NegotiationStatus =
  | "not_applicable"
  | "pending"
  | "accepted"
  | "refused"
  | "counterproposal";


export type BankDecisionItem = {
  id: string;
  process_id: string;
  case_number: string;
  process_title: string;
  state: string;
  recommendation: DecisionChoice;
  model_recommendation: DecisionChoice | null;
  adherence_status: AdherenceStatus;
  amount: number | null;
  justification: string | null;
  bank_status: "pending" | "approved";
  evidence_count: number;
  claim_amount: number;
  expected_cost: number;
  outcome: "pending" | "favorable" | "settled" | "unfavorable";
  actual_cost: number | null;
  outcome_recorded_at: string | null;
  negotiation_status: NegotiationStatus;
  negotiation_amount: number | null;
  negotiation_updated_at: string | null;
  created_at: string;
  bank_reviewed_at: string | null;
};

export type BankJudgeReview = {
  disposition: "grant_claim" | "deny_claim" | "partial_grant" | "insufficient_evidence";
  confidence: number;
  summary: string;
  findings: Array<{
    issue: string;
    conclusion: string;
    reasoning: string;
  }>;
  missing_evidence: string[];
  case_number: string;
  consulted_documents: string[];
  unreadable_documents: string[];
};

export type JudgeChatTurn = {
  role: "user" | "assistant";
  content: string;
};

export type BankDashboardResponse = {
  generated_at: string;
  metrics: {
    process_count: number;
    decision_count: number;
    approved_count: number;
    outcome_recorded_count: number;
    pending_outcome_count: number;
    actual_cost_total: number;
    expected_cost_total: number;
    cost_difference: number;
    adherence_eligible_count: number;
    adherent_count: number;
    justified_divergence_count: number;
    divergent_count: number;
    adherence_rate: number;
    negotiation_count: number;
    accepted_count: number;
    refused_count: number;
    counterproposal_count: number;
    acceptance_rate: number;
  };
  decisions: BankDecisionItem[];
};


export type AnalysisRequest = {
  case_number: string;
  state: string | null;
  sub_subject: "fraud" | "generic" | null;
  claim_amount: number | null;
  evidence: EvidenceInput | null;
  documents?: DocumentReference[];
};

export type AnalysisResult = {
  recommendation: "agreement" | "defense" | "human_review";
  risk_band: "low" | "medium" | "high";
  evidence_score: number;
  loss_probability: number;
  expected_condemnation: number | null;
  condemnation_q10: number | null;
  condemnation_q50: number | null;
  condemnation_q90: number | null;
  model_disagreement: number;
  component_probabilities: Record<string, number>;
  ensemble_weights: Record<string, number>;
  requires_model_review: boolean;
  model_version: string;
  expected_defense_cost: number | null;
  evaluated_agreement_cost: number | null;
  agreement_cheaper: boolean | null;
  agreement_range: AgreementRange | null;
  next_action: "propose_agreement" | "prepare_defense" | "human_review";
  human_review_reason: string | null;
  factors_for_agreement: string[];
  factors_for_defense: string[];
  explanation: string;
  policy_version: string;
  model_inputs: {
    state: string;
    sub_subject: "fraud" | "generic";
    claim_amount: number | null;
    evidence: EvidenceInput;
    input_source: "request_fields" | "documents" | "request_fields_and_documents";
    document_summary: string;
  } | null;
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

