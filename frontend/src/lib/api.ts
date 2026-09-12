const API_PREFIX = "/api/backend";

type FastApiError = {
  detail?: string | Array<{ loc?: Array<string | number>; msg?: string }>;
};

function errorMessage(status: number, payload: FastApiError | null): string {
  if (typeof payload?.detail === "string") {
    return payload.detail;
  }

  if (Array.isArray(payload?.detail)) {
    return payload.detail
      .map((item) => {
        const location = item.loc?.slice(1).join(".");
        return [location, item.msg].filter(Boolean).join(": ");
      })
      .join(" · ");
  }

  return `A API respondeu com status ${status}.`;
}

async function fetchApi<T>(
  prefix: string,
  path: string,
  init?: RequestInit,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${prefix}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...init?.headers,
      },
    });
  } catch {
    throw new Error("Não foi possível conectar à API.");
  }

  if (!response.ok) {
    let payload: FastApiError | null = null;
    try {
      payload = (await response.json()) as FastApiError;
    } catch {
      // Preserve the HTTP status when an upstream proxy returns a non-JSON body.
    }
    throw new Error(errorMessage(response.status, payload));
  }
  if (response.status === 204) return undefined as T;

  return (await response.json()) as T;
}

export function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  return fetchApi<T>(API_PREFIX, path, init);
}


export type SseMessage = {
  event: string;
  id: string | null;
  data: unknown;
};

function parseSseFrame(frame: string): SseMessage | null {
  let event = "message";
  let id: string | null = null;
  const dataLines: string[] = [];

  for (const line of frame.split("\n")) {
    if (!line || line.startsWith(":")) continue;
    const separator = line.indexOf(":");
    const field = separator === -1 ? line : line.slice(0, separator);
    const rawValue = separator === -1 ? "" : line.slice(separator + 1);
    const value = rawValue.startsWith(" ") ? rawValue.slice(1) : rawValue;
    if (field === "event") event = value;
    if (field === "id") id = value;
    if (field === "data") dataLines.push(value);
  }

  if (dataLines.length === 0) return null;
  const rawData = dataLines.join("\n");
  let data: unknown = rawData;
  try {
    data = JSON.parse(rawData);
  } catch {
    // Text data is valid SSE and remains available to the caller.
  }
  return { event, id, data };
}

export async function apiEventStream(
  path: string,
  body: unknown,
  onEvent: (message: SseMessage) => void | Promise<void>,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_PREFIX}${path}`, {
      method: "POST",
      headers: {
        Accept: "text/event-stream",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
      signal,
    });
  } catch {
    throw new Error("Não foi possível conectar à API.");
  }

  if (!response.ok) {
    let payload: FastApiError | null = null;
    try {
      payload = (await response.json()) as FastApiError;
    } catch {
      // Preserve the HTTP status when an upstream proxy returns a non-JSON body.
    }
    throw new Error(errorMessage(response.status, payload));
  }
  if (!response.headers.get("content-type")?.includes("text/event-stream")) {
    throw new Error("A API não iniciou o fluxo de eventos do chat.");
  }
  if (!response.body) {
    throw new Error("O navegador não recebeu o fluxo de eventos do chat.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done }).replaceAll("\r\n", "\n");
      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const message = parseSseFrame(buffer.slice(0, boundary));
        buffer = buffer.slice(boundary + 2);
        if (message) await onEvent(message);
        boundary = buffer.indexOf("\n\n");
      }
      if (done) break;
    }
    const lastMessage = parseSseFrame(buffer);
    if (lastMessage) await onEvent(lastMessage);
  } finally {
    reader.releaseLock();
  }
}
