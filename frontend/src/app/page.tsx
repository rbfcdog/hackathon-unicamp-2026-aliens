"use client";

import { useCallback, useEffect, useState } from "react";
import { ChartColumnBig, FilePlus2, Menu, Search, X } from "lucide-react";
import { CaseWorkspace } from "@/components/case-workspace";
import {
  NewAnalysisDialog,
  type NewProcessRequest,
} from "@/components/new-analysis-dialog";
import { apiFetch } from "@/lib/api";
import type { AnalysisResponse, LegalProcess } from "@/lib/types";

type BusyState = "processes" | "draft" | null;
type WorkspaceView = "chat" | "financial";
type InitialDocumentUpload = {
  completed: number;
  currentDocumentName: string | null;
  error: string | null;
  total: number;
};


function mergeProcessSnapshots(
  current: LegalProcess[],
  incoming: LegalProcess[],
): LegalProcess[] {
  const incomingIds = new Set(incoming.map((legalProcess) => legalProcess.id));
  return [
    ...incoming,
    ...current.filter((legalProcess) => !incomingIds.has(legalProcess.id)),
  ];
}

export default function Home() {
  const [processes, setProcesses] = useState<LegalProcess[]>([]);
  const [selectedProcess, setSelectedProcess] = useState<LegalProcess | null>(null);
  const [draftProcess, setDraftProcess] = useState<LegalProcess | null>(null);
  const [busy, setBusy] = useState<BusyState>("processes");
  const [error, setError] = useState<string | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [connectionRevision, setConnectionRevision] = useState(0);
  const [workspaceView, setWorkspaceView] = useState<WorkspaceView>("chat");
  const [newProcessOpen, setNewProcessOpen] = useState(false);
  const [initialDocumentUploads, setInitialDocumentUploads] = useState<
    Record<string, InitialDocumentUpload>
  >({});


  useEffect(() => {
    let active = true;
    let inFlight = false;

    async function syncApi(showLoading: boolean) {
      if (inFlight) return;
      inFlight = true;
      if (showLoading) setBusy("processes");

      try {
        const [fetchedProcesses, health] = await Promise.all([
          apiFetch<LegalProcess[]>("/v1/processes"),
          apiFetch<{ status: string }>("/ready"),
        ]);
        if (!active) return;
        if (health.status !== "ok") throw new Error("A API ainda não está pronta.");
        let persistedProcesses = fetchedProcesses;
        const existingDraft = persistedProcesses.find(
          (legalProcess) => legalProcess.is_draft,
        );
        if (!existingDraft) {
          try {
            const draft = await apiFetch<LegalProcess>("/v1/processes/drafts", {
              method: "POST",
            });
            if (!active) return;
            persistedProcesses = [draft, ...persistedProcesses];
          } catch {
            if (!active) return;
            setProcesses((current) =>
              mergeProcessSnapshots(current, persistedProcesses),
            );
            setDraftProcess(null);
            setConnectionError(null);
            setError("Não foi possível abrir uma nova conversa.");
            return;
          }
        }
        setProcesses((current) => mergeProcessSnapshots(current, persistedProcesses));
        setDraftProcess(
          persistedProcesses.find((legalProcess) => legalProcess.is_draft) ?? null,
        );
        setSelectedProcess((current) => {
          if (!current) return current;
          return (
            persistedProcesses.find((legalProcess) => legalProcess.id === current.id) ??
            current
          );
        });
        setConnectionError(null);
        setError(null);
      } catch (caught: unknown) {
        if (!active) return;
        setConnectionError(
          caught instanceof Error
            ? caught.message
            : "Não foi possível consultar a API.",
        );
      } finally {
        inFlight = false;
        if (active && showLoading) {
          setBusy((current) => (current === "processes" ? null : current));
        }
      }
    }

    void syncApi(true);
    const retryTimer = window.setInterval(() => {
      void syncApi(false);
    }, 5_000);

    return () => {
      active = false;
      window.clearInterval(retryTimer);
    };
  }, [connectionRevision]);

  const createProcess = useCallback(async (payload: NewProcessRequest) => {
    setBusy("draft");
    setError(null);
    try {
      const {
        documents,
        case_number: caseNumber,
        title,
        state,
        sub_subject: subSubject,
        claim_amount: claimAmount,
        evidence,
      } = payload;
      const hasCompleteInputs =
        caseNumber !== undefined &&
        state !== undefined &&
        claimAmount !== undefined;
      let created: LegalProcess;

      if (hasCompleteInputs) {
        const analysisInput = {
          case_number: caseNumber,
          state,
          sub_subject: subSubject,
          claim_amount: claimAmount,
          evidence,
        };
        created = await apiFetch<LegalProcess>("/v1/processes", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ...analysisInput,
            ...(title ? { title } : {}),
          }),
        });

        if (documents.length === 0) {
          await apiFetch<AnalysisResponse>("/v1/analyses", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(analysisInput),
          });
        }
      } else {
        created = await apiFetch<LegalProcess>("/v1/processes/drafts", {
          method: "POST",
        });
        const hasEvidence = Object.values(evidence).some(Boolean);
        const draftUpdate = {
          ...(caseNumber ? { case_number: caseNumber } : {}),
          ...(title ? { title } : {}),
          ...(subSubject === "fraud" ? { sub_subject: subSubject } : {}),
          ...(claimAmount !== undefined ? { claim_amount: claimAmount } : {}),
          ...(hasEvidence ? { evidence } : {}),
        };
        if (Object.keys(draftUpdate).length > 0) {
          created = await apiFetch<LegalProcess>(
            `/v1/processes/${encodeURIComponent(created.case_number)}`,
            {
              method: "PATCH",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(draftUpdate),
            },
          );
        }
      }

      setProcesses((current) => mergeProcessSnapshots(current, [created]));
      setSelectedProcess(created);
      setWorkspaceView("chat");

      if (documents.length === 0) return;

      setInitialDocumentUploads((current) => ({
        ...current,
        [created.id]: {
          completed: 0,
          currentDocumentName: documents[0]?.file.name ?? null,
          error: null,
          total: documents.length,
        },
      }));

      void (async () => {
        let completed = 0;
        let uploadsCompleted = false;
        try {
          for (const [index, document] of documents.entries()) {
            setInitialDocumentUploads((current) => ({
              ...current,
              [created.id]: {
                completed,
                currentDocumentName: document.file.name,
                error: null,
                total: documents.length,
              },
            }));
            const form = new FormData();
            form.append("file", document.file);
            form.append("document_type", document.documentType);
            await apiFetch(
              `/v1/processes/${encodeURIComponent(created.case_number)}/documents`,
              { method: "POST", body: form },
            );
            completed = index + 1;
            setInitialDocumentUploads((current) => ({
              ...current,
              [created.id]: {
                completed,
                currentDocumentName: documents[index + 1]?.file.name ?? document.file.name,
                error: null,
                total: documents.length,
              },
            }));
          }
          uploadsCompleted = true;
          const renamed = await apiFetch<LegalProcess>(
            `/v1/processes/${encodeURIComponent(created.case_number)}/infer-title`,
            { method: "POST" },
          );
          setProcesses((current) => mergeProcessSnapshots(current, [renamed]));
          setSelectedProcess((current) =>
            current?.id === created.id ? renamed : current,
          );
          setDraftProcess((current) => {
            if (current?.id !== created.id) return current;
            return renamed.is_draft ? renamed : null;
          });
          setInitialDocumentUploads((current) => {
            const remaining = { ...current };
            delete remaining[created.id];
            return remaining;
          });
        } catch (caught: unknown) {
          const message = uploadsCompleted
            ? "Os documentos foram adicionados, mas não foi possível sugerir o nome."
            : caught instanceof Error
              ? caught.message
              : "Os documentos iniciais não puderam ser processados.";
          setInitialDocumentUploads((current) => ({
            ...current,
            [created.id]: {
              completed,
              currentDocumentName: documents[completed]?.file.name ?? null,
              error: message,
              total: documents.length,
            },
          }));
        }
      })();

    } finally {
      setBusy(null);
    }
  }, []);


  const normalizedFilter = query.trim().toLowerCase();
  const filteredProcesses = normalizedFilter
    ? processes.filter(
        (legalProcess) =>
          legalProcess.case_number.toLowerCase().includes(normalizedFilter) ||
          legalProcess.title.toLowerCase().includes(normalizedFilter),
      )
    : processes;
  const activeProcess = selectedProcess ?? draftProcess;
  const initialDocumentUpload = activeProcess
    ? initialDocumentUploads[activeProcess.id]
    : undefined;


  function chooseProcess(legalProcess: LegalProcess) {
    setSelectedProcess(legalProcess);
    setWorkspaceView("chat");
    setError(null);
    setMobileNavOpen(false);
  }

  function openFinancialOverview(legalProcess: LegalProcess) {
    setSelectedProcess(legalProcess);
    setWorkspaceView("financial");
    setError(null);
    setMobileNavOpen(false);
  }

  function updateProcessSnapshot(updated: LegalProcess) {
    setProcesses((current) =>
      current.map((legalProcess) =>
        legalProcess.id === updated.id ? updated : legalProcess,
      ),
    );
    setSelectedProcess(updated);
    setDraftProcess((current) => {
      if (current?.id !== updated.id) return current;
      return updated.is_draft ? updated : null;
    });
  }

  function returnHome() {
    setSelectedProcess(null);
    setWorkspaceView("chat");
    setError(null);
  }

  return (
    <div className="app-shell">
      <aside className={mobileNavOpen ? "case-sidebar open" : "case-sidebar"}>
        <div className="sidebar-brand">
          <button className="sidebar-home" onClick={returnHome} type="button">
            ENTER<span>OS</span>
          </button>
          <button
            aria-label="Fechar navegação"
            className="sidebar-close"
            onClick={() => setMobileNavOpen(false)}
            type="button"
          >
            <X size={18} />
          </button>
        </div>

        <button
          className="new-process-button"
          onClick={() => {
            setNewProcessOpen(true);
            setMobileNavOpen(false);
          }}
          type="button"
        >
          <FilePlus2 size={17} />
          Novo processo
        </button>

        <label className="sidebar-search">
          <Search size={16} />
          <span className="sr-only">Buscar processo</span>
          <input
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Buscar processo"
            value={query}
          />
        </label>

        <div className="sidebar-section">
          <div className="sidebar-section-heading">Processos</div>
          <div className="case-list">
            {filteredProcesses.map((legalProcess) => (
              <div
                className={
                  activeProcess?.id === legalProcess.id
                    ? "case-list-entry selected"
                    : "case-list-entry"
                }
                key={legalProcess.id}
              >
                <button
                  className={
                    activeProcess?.id === legalProcess.id && workspaceView === "chat"
                      ? "case-list-item selected"
                      : "case-list-item"
                  }
                  onClick={() => chooseProcess(legalProcess)}
                  type="button"
                >
                  <span>
                    <strong>{legalProcess.title}</strong>
                    {!legalProcess.is_draft && (
                      <small>{legalProcess.case_number}</small>
                    )}
                  </span>
                </button>
                <button
                  aria-label={`Abrir painel financeiro de ${legalProcess.title}`}
                  className={
                    activeProcess?.id === legalProcess.id &&
                    workspaceView === "financial"
                      ? "case-financial-button selected"
                      : "case-financial-button"
                  }
                  onClick={() => openFinancialOverview(legalProcess)}
                  title="Painel financeiro"
                  type="button"
                >
                  <ChartColumnBig size={15} />
                </button>
              </div>
            ))}
            {!filteredProcesses.length && busy !== "processes" && (
              <p className="empty-case-list">Nenhum processo disponível.</p>
            )}
          </div>
        </div>
      </aside>

      {mobileNavOpen && (
        <button
          aria-label="Fechar navegação"
          className="mobile-nav-backdrop"
          onClick={() => setMobileNavOpen(false)}
          type="button"
        />
      )}


      <NewAnalysisDialog
        loading={busy === "draft"}
        onClose={() => setNewProcessOpen(false)}
        onSubmit={createProcess}
        open={newProcessOpen}
      />
      <main className="main-canvas">
        <button
          aria-label="Abrir navegação"
          className="mobile-menu-button"
          onClick={() => setMobileNavOpen(true)}
          type="button"
        >
          <Menu size={20} />
        </button>

        <div className="canvas-content">
          {activeProcess ? (
            <CaseWorkspace
              key={activeProcess.id}
              initialDocumentUploadCompleted={initialDocumentUpload?.completed ?? 0}
              initialDocumentUploadCurrentName={initialDocumentUpload?.currentDocumentName ?? null}
              initialDocumentUploadError={initialDocumentUpload?.error ?? null}
              initialDocumentUploadTotal={initialDocumentUpload?.total ?? 0}
              initialDocumentsUploading={initialDocumentUpload?.error === null}
              legalProcess={activeProcess}
              onBack={returnHome}
              onProcessUpdated={updateProcessSnapshot}
              onViewChange={setWorkspaceView}
              view={workspaceView}
            />
          ) : (
            <section className="draft-chat-loading" aria-live="polite">
              {busy === "draft" || busy === "processes" ? (
                <>
                  <span className="spinner" /> Abrindo nova conversa
                </>
              ) : (
                <>
                  <p>
                    {connectionError ??
                      error ??
                      "Não foi possível abrir uma nova conversa."}
                  </p>
                  <button
                    className="primary-button"
                    onClick={() =>
                      setConnectionRevision((current) => current + 1)
                    }
                    type="button"
                  >
                    Tentar novamente
                  </button>
                </>
              )}
            </section>
          )}

          {connectionError && activeProcess && (
            <div className="connection-error" role="alert">
              <span>{connectionError}</span>
              <button
                disabled={busy !== null}
                onClick={() => setConnectionRevision((current) => current + 1)}
                type="button"
              >
                Tentar novamente
              </button>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
