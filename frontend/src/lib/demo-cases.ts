import type { DocumentType } from "./types";

export type DemoCase = {
  id: "case-01" | "case-02";
  folder: string;
  eyebrow: string;
  title: string;
  caseNumber: string;
  location: string;
  state: string;
  subSubject: "fraud" | "generic";
  claimAmount: number;
  question: string;
};

export const DEMO_CASES: DemoCase[] = [
  {
    id: "case-01",
    folder: "Caso_01_0801234-56-2024-8-10-0001",
    eyebrow: "Dossiê completo",
    title: "Caso 01 · São Luís",
    caseNumber: "0801234-56.2024.8.10.0001",
    location: "São Luís · MA",
    state: "MA",
    subSubject: "generic",
    claimAmount: 20_000,
    question:
      "Analise a existência da contratação, do crédito e da dívida e apresente uma decisão fundamentada.",
  },
  {
    id: "case-02",
    folder: "Caso_02_0654321-09-2024-8-04-0001",
    eyebrow: "Provas incompletas",
    title: "Caso 02 · Amazonas",
    caseNumber: "0654321-09.2024.8.04.0001",
    location: "Amazonas · AM",
    state: "AM",
    subSubject: "fraud",
    claimAmount: 25_000,
    question:
      "Compare as alegações com as provas de crédito e evolução da dívida e indique contradições ou documentos ausentes.",
  },
];

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

export function documentTypeFromPath(path: string): DocumentType {
  const name = path.toLowerCase();
  if (name.includes("autos_processo")) return "case_record";
  if (name.includes("contrato")) return "contract";
  if (name.includes("extrato")) return "bank_statement";
  if (name.includes("comprovante")) return "credit_proof";
  if (name.includes("dossie")) return "dossier";
  if (name.includes("evolucao_divida")) return "debt_evolution";
  if (name.includes("laudo")) return "referenced_report";
  return "other";
}

export function documentsForCase<T extends { path: string }>(
  documents: T[],
  demoCase: DemoCase,
): T[] {
  return documents.filter((document) =>
    document.path.includes(`/cases/${demoCase.folder}/`.slice(1)),
  );
}
