"use client";

import { useCallback, useEffect, useState } from "react";
import { ArrowRight, FilePlus2, Menu, Search, X } from "lucide-react";
import { CaseWorkspace } from "@/components/case-workspace";
import { apiFetch } from "@/lib/api";
import type { LegalProcess } from "@/lib/types";

type BusyState = "processes" | "draft" | null;

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

  const createDraftProcess = useCallback(async () => {
    setBusy("draft");
    setError(null);
    try {
      const draft = await apiFetch<LegalProcess>("/v1/processes/drafts", {
        method: "POST",
      });
      setDraftProcess(draft);
      setProcesses((current) => mergeProcessSnapshots(current, [draft]));
      setSelectedProcess(draft);
    } catch {
      setError("Não foi possível abrir uma nova conversa.");
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

  function chooseProcess(legalProcess: LegalProcess) {
    setSelectedProcess(legalProcess);
    setError(null);
    setMobileNavOpen(false);
  }

  function returnHome() {
    setSelectedProcess(null);
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
            void createDraftProcess();
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
              <button
                className={
                  activeProcess?.id === legalProcess.id
                    ? "case-list-item selected"
                    : "case-list-item"
                }
                key={legalProcess.id}
                onClick={() => chooseProcess(legalProcess)}
                type="button"
              >
                <span>
                  <strong>{legalProcess.title}</strong>
                  <small>
                    {legalProcess.is_draft ? "Sem informações" : legalProcess.case_number}
                  </small>
                </span>
                <ArrowRight size={15} />
              </button>
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
              legalProcess={activeProcess}
              onBack={returnHome}
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
                    onClick={() => {
                      if (connectionError) {
                        setConnectionRevision((current) => current + 1);
                        return;
                      }
                      void createDraftProcess();
                    }}
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
