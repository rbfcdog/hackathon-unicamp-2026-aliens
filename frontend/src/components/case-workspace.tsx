"use client";

import { ArrowLeft } from "lucide-react";
import { ProcessChat } from "./process-chat";
import type { LegalProcess } from "@/lib/types";

type Props = {
  legalProcess: LegalProcess;
  onBack: () => void;
};

export function CaseWorkspace({ legalProcess, onBack }: Props) {
  return (
    <div className="case-workspace case-chat-workspace">
      <header className="workspace-case-bar">
        {!legalProcess.is_draft && (
          <button className="back-button" onClick={onBack} type="button">
            <ArrowLeft size={15} /> Processos
          </button>
        )}
        <div>
          <h1>{legalProcess.is_draft ? "Nova conversa" : legalProcess.title}</h1>
          <p className="mono-label">
            {legalProcess.is_draft
              ? "Adicione documentos quando quiser para fundamentar a conversa."
              : `CNJ ${legalProcess.case_number}`}
          </p>
        </div>
      </header>

      <ProcessChat
        caseNumber={legalProcess.case_number}
        defaultQuestion={legalProcess.default_question}
        isDraft={legalProcess.is_draft}
      />
    </div>
  );
}
