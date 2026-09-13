"use client";

import { ArrowLeft, ChartColumnBig, MessageSquare } from "lucide-react";
import { ProcessFinancialDashboard } from "./process-financial-dashboard";
import { ProcessChat } from "./process-chat";
import type { LegalProcess } from "@/lib/types";

type WorkspaceView = "chat" | "financial";

type Props = {
  legalProcess: LegalProcess;
  onBack: () => void;
  onProcessUpdated: (legalProcess: LegalProcess) => void;
  onViewChange: (view: WorkspaceView) => void;
  view: WorkspaceView;
};

export function CaseWorkspace({
  legalProcess,
  onBack,
  onProcessUpdated,
  onViewChange,
  view,
}: Props) {
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
        />
      ) : (
        <ProcessChat
          caseNumber={legalProcess.case_number}
          isDraft={legalProcess.is_draft}
          onProcessUpdated={onProcessUpdated}
        />
      )}
    </div>
  );
}
