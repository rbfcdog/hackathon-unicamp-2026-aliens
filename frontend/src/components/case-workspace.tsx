"use client";

import { ArrowLeft, ChartColumnBig, MessageSquare } from "lucide-react";
import { useState } from "react";
import { ProcessFinancialDashboard } from "./process-financial-dashboard";
import { ProcessChat } from "./process-chat";
import type { LegalProcess } from "@/lib/types";

type WorkspaceView = "chat" | "financial";

type Props = {
  legalProcess: LegalProcess;
  initialDocumentUploadCompleted: number;
  initialDocumentUploadCurrentName: string | null;
  initialDocumentUploadError: string | null;
  initialDocumentUploadTotal: number;
  initialDocumentsUploading: boolean;
  onBack: () => void;
  onProcessUpdated: (legalProcess: LegalProcess) => void;
  onViewChange: (view: WorkspaceView) => void;
  view: WorkspaceView;
};

export function CaseWorkspace({
  legalProcess,
  onBack,
  initialDocumentUploadCompleted,
  initialDocumentUploadCurrentName,
  initialDocumentUploadError,
  initialDocumentUploadTotal,
  initialDocumentsUploading,
  onProcessUpdated,
  onViewChange,
  view,
}: Props) {
  const [agreementJustificationReviewForCase, setAgreementJustificationReviewForCase] =
    useState<string | null>(null);
  const agreementJustificationReviewEnabled =
    agreementJustificationReviewForCase === legalProcess.case_number;

  function setAgreementJustificationReviewEnabled(enabled: boolean) {
    setAgreementJustificationReviewForCase(enabled ? legalProcess.case_number : null);
  }

  function requestAgreementJustificationReview() {
    setAgreementJustificationReviewEnabled(true);
    onViewChange("chat");
  }

  return (
    <div className="case-workspace case-chat-workspace">
      <header className="workspace-case-bar">
        {!legalProcess.is_draft && (
          <button className="back-button" onClick={onBack} type="button">
            <ArrowLeft size={15} /> Processos
          </button>
        )}
        <div className="workspace-case-identity">
          <h1>{legalProcess.title}</h1>
          <p className="mono-label">{legalProcess.case_number}</p>
        </div>
        <div className="workspace-view-switcher" aria-label="Visualização do processo">
          <button
            className={view === "chat" ? "selected" : ""}
            onClick={() => onViewChange("chat")}
            type="button"
          >
            <MessageSquare size={14} /> Conversa
          </button>
          <button
            className={view === "financial" ? "selected" : ""}
            onClick={() => onViewChange("financial")}
            type="button"
          >
            <ChartColumnBig size={14} /> Painel financeiro
          </button>
        </div>
      </header>

      {view === "financial" ? (
        <ProcessFinancialDashboard
          legalProcess={legalProcess}
          onProcessUpdated={onProcessUpdated}
          onRequestAgreementJustification={requestAgreementJustificationReview}
        />
      ) : (
        <ProcessChat
          agreementJustificationReviewEnabled={agreementJustificationReviewEnabled}
          legalProcess={legalProcess}
          initialDocumentUploadCompleted={initialDocumentUploadCompleted}
          initialDocumentUploadCurrentName={initialDocumentUploadCurrentName}
          initialDocumentUploadError={initialDocumentUploadError}
          initialDocumentUploadTotal={initialDocumentUploadTotal}
          initialDocumentsUploading={initialDocumentsUploading}
          onAgreementJustificationReviewChange={setAgreementJustificationReviewEnabled}
          onProcessUpdated={onProcessUpdated}
        />
      )}
    </div>
  );
}
