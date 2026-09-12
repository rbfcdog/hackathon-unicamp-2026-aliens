"use client";

import {
  Bot,
  ChevronDown,
  FilePlus2,
  FileSearch,
  FileText,
  FolderOpen,
  MessageSquarePlus,
  Plus,
  ScanSearch,
  Send,
  Trash2,
  X,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { AnalysisResultPanel } from "./analysis-result";
import { apiEventStream, apiFetch } from "@/lib/api";
import { DOCUMENT_LABELS } from "@/lib/legal-documents";
import type {
  ChatHistoryResponse,
  ChatMessage,
  ChatSession,
  ChatStreamEvent,
  DocumentType,
  ProcessDocument,
  ProcessDocumentListResponse,
  ReviewResponse,
} from "@/lib/types";

type ActivityItem = {
  id: string;
  label: string;
  detail: string;
  status: "active" | "complete" | "error";
};

type Props = {
  caseNumber: string;
  defaultQuestion: string;
  isDraft: boolean;
};
type WorkspaceArtifact =
  | { kind: "document"; document: ProcessDocument }
  | { kind: "review" };

const DOCUMENT_TYPES: Array<{ value: DocumentType; label: string }> = [
  { value: "case_record", label: "Autos do processo" },
  { value: "contract", label: "Contrato" },
  { value: "bank_statement", label: "Extrato bancário" },
  { value: "credit_proof", label: "Comprovante de crédito" },
  { value: "dossier", label: "Dossiê" },
  { value: "debt_evolution", label: "Evolução da dívida" },
  { value: "referenced_report", label: "Laudo referenciado" },
  { value: "other", label: "Outro documento" },
];

function formatSize(sizeBytes: number) {
  if (sizeBytes < 1024 * 1024) return `${Math.ceil(sizeBytes / 1024)} KB`;
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
}


type ChatEventMap = {
  [Event in ChatStreamEvent as Event["event"]]: Event["data"];
};

function eventData<Name extends keyof ChatEventMap>(
  event: ChatStreamEvent,
  name: Name,
): ChatEventMap[Name] | null {
  if (event.event !== name) return null;
  return event.data as ChatEventMap[Name];
}

export function ProcessChat({ caseNumber, defaultQuestion, isDraft }: Props) {
  const fileInputId = useId();
  const documentsMenuId = useId();
  const transcriptRef = useRef<HTMLDivElement>(null);
  const streamAbortRef = useRef<AbortController | null>(null);
  const tokenQueueRef = useRef("");
  const tokenFrameRef = useRef<number | null>(null);
  const tokenDrainResolversRef = useRef<Array<() => void>>([]);
  const tokenFlushRef = useRef<() => void>(() => undefined);
  const [documents, setDocuments] = useState<ProcessDocument[]>([]);
  const [session, setSession] = useState<ChatSession | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [message, setMessage] = useState("");
  const [streamingText, setStreamingText] = useState("");
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [streaming, setStreaming] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dropActive, setDropActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [documentType, setDocumentType] = useState<DocumentType>("other");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [documentsOpen, setDocumentsOpen] = useState(false);
  const dragDepthRef = useRef(0);
  const [artifact, setArtifact] = useState<WorkspaceArtifact | null>(null);
  const [reviewQuestion, setReviewQuestion] = useState(defaultQuestion);
  const [review, setReview] = useState<ReviewResponse | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const flushTokenQueue = useCallback(() => {
    const queued = tokenQueueRef.current;
    if (!queued) {
      tokenFrameRef.current = null;
      const resolvers = tokenDrainResolversRef.current.splice(0);
      resolvers.forEach((resolve) => resolve());
      return;
    }

    const charactersPerFrame =
      queued.length > 600 ? 20 : queued.length > 240 ? 12 : queued.length > 80 ? 6 : 2;
    const nextText = queued.slice(0, charactersPerFrame);
    tokenQueueRef.current = queued.slice(charactersPerFrame);
    setStreamingText((current) => current + nextText);
    tokenFrameRef.current = window.requestAnimationFrame(() => tokenFlushRef.current());
  }, []);

  useEffect(() => {
    tokenFlushRef.current = flushTokenQueue;
  }, [flushTokenQueue]);

  const enqueueToken = useCallback((text: string) => {
    tokenQueueRef.current += text;
    if (tokenFrameRef.current === null) {
      tokenFrameRef.current = window.requestAnimationFrame(flushTokenQueue);
    }
  }, [flushTokenQueue]);

  function waitForTokenDrain(): Promise<void> {
    if (!tokenQueueRef.current && tokenFrameRef.current === null) {
      return Promise.resolve();
    }
    const { promise, resolve } = Promise.withResolvers<void>();
    tokenDrainResolversRef.current.push(resolve);
    return promise;
  }

  const resetTokenStream = useCallback(() => {
    tokenQueueRef.current = "";
    if (tokenFrameRef.current !== null) {
      window.cancelAnimationFrame(tokenFrameRef.current);
      tokenFrameRef.current = null;
    }
    const resolvers = tokenDrainResolversRef.current.splice(0);
    resolvers.forEach((resolve) => resolve());
  }, []);


  const processPath = `/v1/processes/${encodeURIComponent(caseNumber)}`;

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const tokenDrainResolvers = tokenDrainResolversRef.current;
    streamAbortRef.current?.abort();

    async function load() {
      try {
        const [documentResponse, sessions] = await Promise.all([
          apiFetch<ProcessDocumentListResponse>(`${processPath}/documents`, {
            signal: controller.signal,
          }),
          apiFetch<ChatSession[]>(`${processPath}/chats`, {
            signal: controller.signal,
          }),
        ]);
        const currentSession =
          sessions[0] ??
          (await apiFetch<ChatSession>(`${processPath}/chats`, {
            method: "POST",
            signal: controller.signal,
          }));
        const history = await apiFetch<ChatHistoryResponse>(
          `${processPath}/chats/${currentSession.id}`,
          { signal: controller.signal },
        );
        if (!active) return;
        setDocuments(documentResponse.documents);
        setSession(currentSession);
        setMessages(history.messages);
      } catch (caught: unknown) {
        if (!active || (caught instanceof DOMException && caught.name === "AbortError")) {
          return;
        }
        setError(
          caught instanceof Error
            ? caught.message
            : "Não foi possível abrir o assistente deste processo.",
        );
      } finally {
        if (active) setLoading(false);
      }
    }

    void load();
    return () => {
      active = false;
      controller.abort();
      streamAbortRef.current?.abort();
      tokenQueueRef.current = "";
      if (tokenFrameRef.current !== null) {
        window.cancelAnimationFrame(tokenFrameRef.current);
        tokenFrameRef.current = null;
      }
      const resolvers = tokenDrainResolvers.splice(0);
      resolvers.forEach((resolve) => resolve());
    };
  }, [caseNumber, processPath]);

  useEffect(() => {
    transcriptRef.current?.scrollTo({
      top: transcriptRef.current.scrollHeight,
      behavior: streaming ? "smooth" : "auto",
    });
  }, [messages, streamingText, activity, streaming]);

  const refreshDocuments = useCallback(async () => {
    const response = await apiFetch<ProcessDocumentListResponse>(
      `${processPath}/documents`,
    );
    setDocuments(response.documents);
  }, [processPath]);

  async function startNewChat() {
    streamAbortRef.current?.abort();
    resetTokenStream();
    setError(null);
    setLoading(true);
    try {
      const created = await apiFetch<ChatSession>(`${processPath}/chats`, {
        method: "POST",
      });
      setSession(created);
      setMessages([]);
      setActivity([]);
      setStreamingText("");
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Não foi possível iniciar uma nova conversa.",
      );
    } finally {
      setLoading(false);
    }
  }

  const uploadFile = useCallback(async (selectedFile: File) => {
    const supportedFile = /\.(pdf|csv)$/i.test(selectedFile.name);
    if (!supportedFile) {
      setError("Envie um arquivo PDF ou CSV.");
      return;
    }

    setUploading(true);
    setError(null);
    const form = new FormData();
    form.append("file", selectedFile);
    form.append("document_type", documentType);
    try {
      const uploaded = await apiFetch<ProcessDocument>(`${processPath}/documents`, {
        method: "POST",
        body: form,
      });
      await refreshDocuments();
      setFile(null);
      setUploadOpen(false);
      setArtifact({ kind: "document", document: uploaded });
      const input = document.getElementById(fileInputId) as HTMLInputElement | null;
      if (input) input.value = "";
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "O documento não pôde ser enviado.",
      );
    } finally {
      setUploading(false);
    }
  }, [documentType, fileInputId, processPath, refreshDocuments]);

  async function uploadDocument(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (file) await uploadFile(file);
  }

  useEffect(() => {
    function hasFiles(event: DragEvent) {
      return event.dataTransfer?.types.includes("Files") ?? false;
    }

    function handleDragEnter(event: DragEvent) {
      if (!hasFiles(event)) return;
      event.preventDefault();
      dragDepthRef.current += 1;
      setDropActive(true);
    }

    function handleDragLeave(event: DragEvent) {
      if (!hasFiles(event)) return;
      dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
      if (dragDepthRef.current === 0) setDropActive(false);
    }

    function handleDragOver(event: DragEvent) {
      const dataTransfer = event.dataTransfer;
      if (!hasFiles(event) || !dataTransfer) return;
      event.preventDefault();
      dataTransfer.dropEffect = "copy";
    }

    function handleDrop(event: DragEvent) {
      const dataTransfer = event.dataTransfer;
      if (!hasFiles(event) || !dataTransfer) return;
      event.preventDefault();
      dragDepthRef.current = 0;
      setDropActive(false);
      if (streaming) {
        setError("Espere a resposta atual terminar antes de anexar um documento.");
        return;
      }
      const droppedFile = Array.from(dataTransfer.files).find((candidate) =>
        /\.(pdf|csv)$/i.test(candidate.name),
      );
      if (!droppedFile) {
        setError("Envie um arquivo PDF ou CSV.");
        return;
      }
      void uploadFile(droppedFile);
    }

    window.addEventListener("dragenter", handleDragEnter);
    window.addEventListener("dragleave", handleDragLeave);
    window.addEventListener("dragover", handleDragOver);
    window.addEventListener("drop", handleDrop);
    return () => {
      window.removeEventListener("dragenter", handleDragEnter);
      window.removeEventListener("dragleave", handleDragLeave);
      window.removeEventListener("dragover", handleDragOver);
      window.removeEventListener("drop", handleDrop);
    };
  }, [streaming, uploadFile]);

  async function deleteDocument(document: ProcessDocument) {
    if (!document.id) return;
    const confirmed = window.confirm(
      `Remover “${document.original_filename}” deste processo?`,
    );
    if (!confirmed) return;
    setError(null);
    try {
      await apiFetch<void>(`${processPath}/documents/${document.id}`, {
        method: "DELETE",
      });
      setDocuments((current) => current.filter((item) => item.id !== document.id));
      if (
        artifact?.kind === "document" &&
        artifact.document.path === document.path
      ) {
        setArtifact(null);
      }
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "O documento não pôde ser removido.",
      );
    }
  }

  async function runReview() {
    const question = reviewQuestion.trim();
    if (question.length < 10 || documents.length === 0) return;
    setReviewing(true);
    setError(null);
    try {
      const response = await apiFetch<ReviewResponse>("/v1/judge/reviews", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          case_number: caseNumber,
          question,
          documents: documents.map((document) => ({
            path: document.path,
            document_type: document.document_type,
          })),
        }),
      });
      setReview(response);
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "A revisão documental não pôde ser concluída.",
      );
    } finally {
      setReviewing(false);
    }
  }

  const sendMessage = useCallback(async (content = message) => {
    const cleanMessage = content.trim();
    if (!cleanMessage || !session || streaming) return;

    const controller = new AbortController();
    const streamResult: { complete: ChatEventMap["complete"] | null } = {
      complete: null,
    };
    streamAbortRef.current = controller;
    const optimisticMessage: ChatMessage = {
      id: crypto.randomUUID(),
      session_id: session.id,
      role: "user",
      content: cleanMessage,
      document_paths: [],
      trace_id: null,
      created_at: new Date().toISOString(),
    };
    setMessages((current) => [...current, optimisticMessage]);
    setMessage("");
    setError(null);
    setActivity([]);
    resetTokenStream();
    setStreamingText("");
    setStreaming(true);

    try {
      await apiEventStream(
        `${processPath}/chats/${session.id}/messages/stream`,
        { message: cleanMessage },
        ({ event, data }) => {
          const streamEvent = { event, data } as ChatStreamEvent;
          const ready = eventData(streamEvent, "ready");
          if (ready) {
            setActivity([
              {
                id: `ready-${ready.trace_id}`,
                label: "Fluxo conectado",
                detail: `${ready.document_count} documento(s) no escopo`,
                status: "complete",
              },
            ]);
            return;
          }

          const toolStart = eventData(streamEvent, "tool_start");
          if (toolStart) {
            setActivity((current) => [
              ...current,
              {
                id: `${toolStart.tool}-${toolStart.document_path}-${current.length}`,
                label: "Consultando fonte",
                detail: toolStart.document_path || toolStart.tool,
                status: "active",
              },
            ]);
            return;
          }

          const toolEnd = eventData(streamEvent, "tool_end");
          if (toolEnd) {
            setActivity((current) => {
              const next = [...current];
              const index = next.findLastIndex(
                (item) =>
                  item.status === "active" &&
                  (!toolEnd.document_path || item.detail === toolEnd.document_path),
              );
              if (index >= 0) {
                next[index] = {
                  ...next[index],
                  status: toolEnd.status === "error" ? "error" : "complete",
                };
              }
              return next;
            });
            return;
          }

          const token = eventData(streamEvent, "token");
          if (token) {
            enqueueToken(token.text);
            return;
          }

          const complete = eventData(streamEvent, "complete");
          if (complete) {
            streamResult.complete = complete;
            return;
          }

          const streamError = eventData(streamEvent, "error");
          if (streamError) throw new Error(streamError.message);
        },
        controller.signal,
      );
      await waitForTokenDrain();
      const completed = streamResult.complete;
      if (!completed) {
        throw new Error("O servidor encerrou o fluxo sem concluir a resposta.");
      }
      setMessages((current) => [...current, completed.message]);
      setStreamingText("");
      setActivity((current) =>
        current.map((item) =>
          item.status === "active" ? { ...item, status: "complete" } : item,
        ),
      );
    } catch (caught: unknown) {
      resetTokenStream();
      setStreamingText("");
      if (!(caught instanceof DOMException && caught.name === "AbortError")) {
        setError(
          caught instanceof Error
            ? caught.message
            : "O assistente não concluiu a resposta.",
        );
      }
    } finally {
      if (streamAbortRef.current === controller) streamAbortRef.current = null;
      setStreaming(false);
    }
  }, [
    enqueueToken,
    message,
    processPath,
    resetTokenStream,
    session,
    streaming,
  ]);


  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage();
    }
  }

  const openedDocument = artifact?.kind === "document" ? artifact.document : null;
  const openedDocumentUrl = openedDocument
    ? `/api/backend${processPath}/documents/content?document_path=${encodeURIComponent(openedDocument.path)}`
    : null;

  return (
    <div className={`process-chat-shell${artifact ? " artifact-open" : ""}`}>
      <aside className="workspace-explorer" aria-labelledby="workspace-files-title">
        <header className="workspace-explorer-heading">
          <div>
            <span className="section-kicker">Caso atual</span>
            <h2 id="workspace-files-title">Arquivos</h2>
          </div>
          <button
            aria-label="Adicionar documento"
            className={uploadOpen ? "active" : ""}
            onClick={() => setUploadOpen((current) => !current)}
            type="button"
          >
            <Plus size={16} />
          </button>
        </header>

        <nav className="workspace-tree" aria-label="Arquivos do processo">
          <button
            className={`workspace-tree-item review${artifact?.kind === "review" ? " selected" : ""}`}
            disabled={documents.length === 0}
            onClick={() => setArtifact({ kind: "review" })}
            type="button"
          >
            <ScanSearch size={16} />
            <span>Revisão estratégica</span>
          </button>

          <button
            aria-controls={documentsMenuId}
            aria-expanded={documentsOpen}
            className="workspace-folder-toggle"
            onClick={() => setDocumentsOpen((current) => !current)}
            type="button"
          >
            <ChevronDown className={documentsOpen ? "expanded" : ""} size={14} />
            <FolderOpen size={16} />
            <strong>Documentos</strong>
            <span>{documents.length}</span>
          </button>

          {documentsOpen && (
            <div className="workspace-document-list" id={documentsMenuId}>
              {documents.map((document) => (
                <div className="workspace-document-row" key={document.path}>
                  <button
                    className="workspace-document-open"
                    onClick={() => setArtifact({ kind: "document", document })}
                    title={document.original_filename}
                    type="button"
                  >
                    <FileText size={15} />
                    <span>{document.original_filename}</span>
                  </button>
                  {document.source === "upload" && (
                    <button
                      aria-label={`Remover ${document.original_filename}`}
                      className="workspace-document-delete"
                      disabled={streaming}
                      onClick={() => void deleteDocument(document)}
                      type="button"
                    >
                      <Trash2 size={13} />
                    </button>
                  )}
                </div>
              ))}
              {!loading && documents.length === 0 && (
                <div className="workspace-tree-empty">
                  <FileSearch size={18} />
                  <span>Nenhum documento</span>
                </div>
              )}
            </div>
          )}
        </nav>

        {uploadOpen && (
          <form className="workspace-upload" onSubmit={uploadDocument}>
            <div className="workspace-upload-heading">
              <strong>Novo documento</strong>
              <button
                aria-label="Fechar formulário"
                onClick={() => setUploadOpen(false)}
                type="button"
              >
                <X size={14} />
              </button>
            </div>
            <label htmlFor="process-document-type">Classificação</label>
            <select
              id="process-document-type"
              disabled={uploading || streaming}
              onChange={(event) => setDocumentType(event.target.value as DocumentType)}
              value={documentType}
            >
              {DOCUMENT_TYPES.map((type) => (
                <option key={type.value} value={type.value}>{type.label}</option>
              ))}
            </select>
            <label className="workspace-file-picker" htmlFor={fileInputId}>
              <FilePlus2 size={15} />
              <span>{file ? file.name : "Escolher PDF ou CSV"}</span>
            </label>
            <input
              accept=".pdf,.csv,application/pdf,text/csv"
              className="sr-only"
              disabled={uploading || streaming}
              id={fileInputId}
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              type="file"
            />
            <button
              className="primary-button workspace-upload-submit"
              disabled={!file || uploading || streaming}
              type="submit"
            >
              {uploading ? <span className="spinner" /> : <FilePlus2 size={14} />}
              {uploading ? "Enviando" : "Adicionar"}
            </button>
          </form>
        )}

        <footer className="workspace-explorer-footer">
          <span>{documents.length} arquivo(s)</span>
          <span>{formatSize(documents.reduce((total, item) => total + item.size_bytes, 0))}</span>
        </footer>
      </aside>

      <section className="chat-panel" aria-labelledby="chat-title">
        <header className="chat-panel-heading">
          <div>
            <span className="section-kicker">
              {isDraft ? "Nova conversa" : "Assistente documental"}
            </span>
            <h2 id="chat-title">
              {isDraft ? "Como posso ajudar?" : "Conversa do processo"}
            </h2>
          </div>
          <button
            className="quiet-button"
            disabled={loading || streaming}
            onClick={() => void startNewChat()}
            type="button"
          >
            <MessageSquarePlus size={15} /> Nova conversa
          </button>
        </header>

        <div className="chat-transcript" ref={transcriptRef} aria-live="polite">
          {loading ? (
            <div className="chat-empty"><span className="spinner" /> Abrindo histórico</div>
          ) : messages.length === 0 && !streamingText ? (
            <div className="chat-empty">
              <Bot size={26} />
              <strong>{isDraft ? "Comece por aqui" : "Pergunte sobre os autos"}</strong>
              <p>
                {isDraft
                  ? "Converse normalmente. Anexe documentos quando quiser uma resposta fundamentada nos autos."
                  : "O assistente consulta somente os documentos deste processo e identifica cada fonte usada."}
              </p>
            </div>
          ) : null}

          {messages.map((item) => (
            <article className={`chat-message ${item.role}`} key={item.id}>
              <span>{item.role === "user" ? "Você" : "Assistente"}</span>
              <p>{item.content.replaceAll("**", "").replaceAll("`", "")}</p>
              {item.role === "assistant" && item.document_paths.length > 0 && (
                <footer>{item.document_paths.length} fonte(s) consultada(s)</footer>
              )}
            </article>
          ))}

          {streamingText && (
            <article className="chat-message assistant streaming">
              <span>Assistente</span>
              <p>{streamingText.replaceAll("**", "").replaceAll("`", "")}</p>
            </article>
          )}
        </div>

        <div className="chat-activity" aria-live="polite">
          {activity.slice(-4).map((item) => (
            <div className={`activity-row ${item.status}`} key={item.id}>
              <i aria-hidden="true" />
              <span>{item.label}</span>
              <small title={item.detail}>{item.detail}</small>
            </div>
          ))}
        </div>

        <div className="chat-composer">
          <label className="sr-only" htmlFor="process-chat-message">Mensagem</label>
          <textarea
            id="process-chat-message"
            disabled={loading || streaming}
            maxLength={8000}
            onChange={(event) => setMessage(event.target.value)}
            onKeyDown={handleComposerKeyDown}
            placeholder={
              isDraft
                ? "Escreva sua pergunta ou descreva o que aconteceu…"
                : "Pergunte sobre fatos, valores ou contradições dos documentos…"
            }
            value={message}
          />
          <button
            aria-label="Enviar mensagem"
            disabled={
              loading ||
              streaming ||
              !session ||
              message.trim().length === 0
            }
            onClick={() => void sendMessage()}
            type="button"
          >
            {streaming ? <span className="spinner" /> : <Send size={17} />}
          </button>
          <small>Enter para enviar · Shift + Enter para nova linha</small>
        </div>
      </section>

      {artifact && (
        <aside className="artifact-panel" aria-labelledby="artifact-title">
          <header className="artifact-panel-heading">
            <div>
              {artifact.kind === "review" ? <ScanSearch size={17} /> : <FileText size={17} />}
              <span>
                <small>{artifact.kind === "review" ? "Revisão" : "Documento"}</small>
                <strong id="artifact-title">
                  {artifact.kind === "review"
                    ? "Revisão estratégica"
                    : artifact.document.original_filename}
                </strong>
              </span>
            </div>
            <button
              aria-label="Fechar painel"
              onClick={() => setArtifact(null)}
              type="button"
            >
              <X size={17} />
            </button>
          </header>

          {artifact.kind === "document" && openedDocumentUrl ? (
            <div className="artifact-document">
              <iframe
                src={openedDocumentUrl}
                title={`Visualização de ${artifact.document.original_filename}`}
              />
              <footer>
                <span>{DOCUMENT_LABELS[artifact.document.document_type]}</span>
                <span>{formatSize(artifact.document.size_bytes)}</span>
              </footer>
            </div>
          ) : (
            <div className="artifact-review">
              <section className="review-command">
                <label htmlFor="review-question">Questão para revisão</label>
                <textarea
                  disabled={reviewing}
                  id="review-question"
                  maxLength={2000}
                  onChange={(event) => setReviewQuestion(event.target.value)}
                  rows={4}
                  value={reviewQuestion}
                />
                <button
                  className="primary-button"
                  disabled={
                    reviewing ||
                    documents.length === 0 ||
                    reviewQuestion.trim().length < 10
                  }
                  onClick={() => void runReview()}
                  type="button"
                >
                  {reviewing ? <span className="spinner" /> : <ScanSearch size={15} />}
                  {reviewing ? "Revisando autos" : review ? "Executar nova revisão" : "Revisar documentos"}
                </button>
              </section>
              {review ? (
                <AnalysisResultPanel review={review} />
              ) : (
                <div className="artifact-empty">
                  <ScanSearch size={26} />
                  <strong>Revisão documental isolada</strong>
                  <p>Os documentos da pasta serão enviados ao fluxo real de revisão jurídica.</p>
                </div>
              )}
            </div>
          )}
        </aside>
      )}

      {error && <div className="inline-error chat-error" role="alert">{error}</div>}
      {dropActive && (
        <div className="workspace-file-drop" role="status">
          <FilePlus2 aria-hidden="true" size={28} />
          <strong>Solte para anexar ao chat</strong>
          <span>O documento será enviado para este processo.</span>
        </div>
      )}
    </div>
  );
}
