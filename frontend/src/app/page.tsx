"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  Activity,
  ArrowRight,
  BriefcaseBusiness,
  Command,
  FilePlus2,
  Gauge,
  HelpCircle,
  LayoutDashboard,
  Menu,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import { AnalysisResultPanel } from "@/components/analysis-result";
import { CaseWorkspace } from "@/components/case-workspace";
import { NewAnalysisDialog } from "@/components/new-analysis-dialog";
import { apiFetch } from "@/lib/api";
import {
  DEMO_CASES,
  documentTypeFromPath,
  documentsForCase,
  type DemoCase,
} from "@/lib/demo-cases";
import type {
  AnalysisRequest,
  AnalysisResponse,
  DocumentCatalogResponse,
  ReviewResponse,
} from "@/lib/types";

type BusyState = "catalog" | "analysis" | "review" | null;

export default function Home() {
  const [catalog, setCatalog] = useState<DocumentCatalogResponse | null>(null);
  const [selectedCase, setSelectedCase] = useState<DemoCase | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [review, setReview] = useState<ReviewResponse | null>(null);
  const [busy, setBusy] = useState<BusyState>("catalog");
  const [error, setError] = useState<string | null>(null);
  const [apiOnline, setApiOnline] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [query, setQuery] = useState("");

  useEffect(() => {
    let active = true;

    Promise.all([
      apiFetch<DocumentCatalogResponse>("/v1/documents"),
      apiFetch<{ status: string }>("/ready"),
    ])
      .then(([documentCatalog, health]) => {
        if (!active) return;
        setCatalog(documentCatalog);
        setApiOnline(health.status === "ok");
      })
      .catch((caught: unknown) => {
        if (!active) return;
        setError(
          caught instanceof Error
            ? caught.message
            : "Não foi possível consultar a API.",
        );
      })
      .finally(() => {
        if (active) setBusy(null);
      });

    return () => {
      active = false;
    };
  }, []);

  const caseDocuments = useMemo(() => {
    if (!catalog || !selectedCase) return [];
    return documentsForCase(catalog.documents, selectedCase);
  }, [catalog, selectedCase]);

  const loadedCases = catalog
    ? DEMO_CASES.filter(
        (demoCase) => documentsForCase(catalog.documents, demoCase).length > 0,
      )
    : [];

  async function createAnalysis(payload: AnalysisRequest) {
    setBusy("analysis");
    setError(null);
    setAnalysis(null);
    setSelectedCase(null);

    try {
      const response = await apiFetch<AnalysisResponse>("/v1/analyses", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setAnalysis(response);
      setDialogOpen(false);
    } catch (caught: unknown) {
      setError(
        caught instanceof Error ? caught.message : "A análise não foi concluída.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function runDocumentReview(question: string) {
    if (!selectedCase) return;

    setBusy("review");
    setError(null);
    setReview(null);

    try {
      const response = await apiFetch<ReviewResponse>("/v1/judge/reviews", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          case_number: selectedCase.caseNumber,
          question,
          documents: caseDocuments.map((document) => ({
            path: document.path,
            document_type: documentTypeFromPath(document.path),
          })),
          new_case_data: {
            state: selectedCase.state,
            sub_subject: selectedCase.subSubject,
            claim_amount: selectedCase.claimAmount,
          },
        }),
      });
      setReview(response);
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "A revisão documental não foi concluída.",
      );
    } finally {
      setBusy(null);
    }
  }

  function chooseCase(demoCase: DemoCase) {
    setSelectedCase(demoCase);
    setReview(null);
    setAnalysis(null);
    setError(null);
    setMobileNavOpen(false);
  }

  function handleCommand(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) {
      setDialogOpen(true);
      return;
    }

    const match = DEMO_CASES.find(
      (demoCase) =>
        demoCase.caseNumber.toLowerCase().includes(normalizedQuery) ||
        demoCase.title.toLowerCase().includes(normalizedQuery) ||
        demoCase.id.includes(normalizedQuery.replaceAll(" ", "-")),
    );

    if (match) {
      chooseCase(match);
      setQuery("");
      return;
    }

    setError(
      "Processo não encontrado no catálogo local. Abra uma nova análise para informar os dados.",
    );
  }

  function returnHome() {
    setSelectedCase(null);
    setReview(null);
    setError(null);
  }

  return (
    <div className="app-shell">
      <aside className="icon-rail" aria-label="Navegação principal">
        <button
          aria-label="Abrir navegação"
          className="mobile-menu-button"
          onClick={() => setMobileNavOpen(true)}
          type="button"
        >
          <Menu size={20} />
        </button>
        <button
          aria-label="Visão geral"
          className="rail-brand"
          onClick={returnHome}
          type="button"
        >
          <span className="brand-glyph" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
        </button>
        <nav>
          <button
            aria-label="Visão geral"
            className={!selectedCase ? "rail-action active" : "rail-action"}
            onClick={returnHome}
            type="button"
          >
            <LayoutDashboard size={19} />
          </button>
          <button
            aria-label="Novo processo"
            className="rail-action"
            onClick={() => setDialogOpen(true)}
            type="button"
          >
            <FilePlus2 size={19} />
          </button>
          <button
            aria-label="Indicadores"
            className="rail-action"
            onClick={returnHome}
            type="button"
          >
            <Gauge size={19} />
          </button>
        </nav>
        <a
          aria-label="Abrir documentação da API"
          className="rail-action rail-help"
          href="http://localhost:8000/docs"
          rel="noreferrer"
          target="_blank"
        >
          <HelpCircle size={19} />
        </a>
      </aside>

      <aside className={mobileNavOpen ? "case-sidebar open" : "case-sidebar"}>
        <div className="sidebar-brand">
          <div>
            <strong>ENTER<span>OS</span></strong>
            <small>Legal intelligence</small>
          </div>
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
            setDialogOpen(true);
            setMobileNavOpen(false);
          }}
          type="button"
        >
          <FilePlus2 size={17} />
          Novo processo
          <span>⌘ N</span>
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
          <div className="sidebar-section-heading">
            <span>Processos recentes</span>
            <b>{String(loadedCases.length).padStart(2, "0")}</b>
          </div>
          <div className="case-list">
            {DEMO_CASES.map((demoCase) => (
              <button
                className={
                  selectedCase?.id === demoCase.id
                    ? "case-list-item selected"
                    : "case-list-item"
                }
                key={demoCase.id}
                onClick={() => chooseCase(demoCase)}
                type="button"
              >
                <span className="case-list-marker" />
                <span>
                  <strong>{demoCase.title}</strong>
                  <small>{demoCase.caseNumber}</small>
                </span>
                <ArrowRight size={15} />
              </button>
            ))}
          </div>
        </div>

        <div className="sidebar-footnote">
          <ShieldCheck size={15} />
          <span>
            Política determinística
            <small>decision-tree-2026-09-12</small>
          </span>
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
        <header className="topbar">
          <div className="breadcrumb">
            <BriefcaseBusiness size={16} />
            <span>Operação jurídica</span>
            <i>/</i>
            <strong>{selectedCase ? selectedCase.title : "Visão geral"}</strong>
          </div>
          <div className="api-status">
            <span className={apiOnline ? "status-dot online" : "status-dot"} />
            <div>
              <small>API FastAPI</small>
              <strong>{apiOnline ? "Operacional" : busy === "catalog" ? "Conectando" : "Indisponível"}</strong>
            </div>
          </div>
        </header>

        <div className="canvas-content">
          {selectedCase ? (
            <CaseWorkspace
              demoCase={selectedCase}
              documents={caseDocuments}
              error={error}
              loading={busy === "review"}
              onBack={returnHome}
              onRunReview={runDocumentReview}
              review={review}
            />
          ) : (
            <section className="overview">
              <div className="overview-stat">
                <Activity size={16} />
                <span>Processos ativos</span>
                <strong>{String(loadedCases.length).padStart(2, "0")}</strong>
              </div>

              <div className="welcome-block">
                <span className="section-kicker">Workspace do advogado</span>
                <h1>
                  Olá. Qual processo
                  <br />
                  vamos avaliar hoje?
                </h1>
                <p>
                  Consulte os casos de demonstração ou inicie uma análise com a
                  política de acordos vigente.
                </p>

                <form className="command-bar" onSubmit={handleCommand}>
                  <Command size={19} />
                  <input
                    aria-label="Buscar processo ou iniciar análise"
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Digite 01, 02 ou um número de processo"
                    value={query}
                  />
                  <kbd>Enter</kbd>
                  <button aria-label="Executar comando" type="submit">
                    <ArrowRight size={17} />
                  </button>
                </form>

                <div className="quick-actions">
                  <span>Acessos rápidos</span>
                  <div>
                    {DEMO_CASES.map((demoCase) => (
                      <button
                        className="document-chip"
                        key={demoCase.id}
                        onClick={() => chooseCase(demoCase)}
                        type="button"
                      >
                        <BriefcaseBusiness size={16} />
                        <span>
                          <small>{demoCase.eyebrow}</small>
                          {demoCase.title}
                        </span>
                      </button>
                    ))}
                    <button
                      className="document-chip accent"
                      onClick={() => setDialogOpen(true)}
                      type="button"
                    >
                      <FilePlus2 size={16} />
                      <span>
                        <small>Dados estruturados</small>
                        Nova análise
                      </span>
                    </button>
                  </div>
                </div>
              </div>

              {error && <div className="inline-error overview-error" role="alert">{error}</div>}
              {busy === "catalog" && (
                <div className="catalog-loading">
                  <span className="spinner" /> Sincronizando catálogo documental
                </div>
              )}
              {analysis && <AnalysisResultPanel analysis={analysis} />}
            </section>
          )}
        </div>
      </main>

      <NewAnalysisDialog
        loading={busy === "analysis"}
        onClose={() => setDialogOpen(false)}
        onSubmit={createAnalysis}
        open={dialogOpen}
      />
    </div>
  );
}
