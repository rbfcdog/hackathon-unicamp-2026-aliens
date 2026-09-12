import type { DocumentType } from "./types";

export const DOCUMENT_LABELS: Record<DocumentType, string> = {
  case_record: "Autos do processo",
  contract: "Contrato",
  bank_statement: "Extrato bancário",
  credit_proof: "Comprovante de crédito",
  dossier: "Dossiê de autenticidade",
  debt_evolution: "Evolução da dívida",
  referenced_report: "Laudo referenciado",
  other: "Outro documento",
};
