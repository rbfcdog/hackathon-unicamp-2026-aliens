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

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_PREFIX}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let payload: FastApiError | null = null;
    try {
      payload = (await response.json()) as FastApiError;
    } catch {
      // Preserve the HTTP status when an upstream proxy returns a non-JSON body.
    }
    throw new Error(errorMessage(response.status, payload));
  }

  return (await response.json()) as T;
}
