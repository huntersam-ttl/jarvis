// Jarvis API client. Talks to the backend via Next.js rewrites (same origin)
// so the browser never sees the backend URL or any secrets.

import type {
  ChatRequest,
  ChatResponse,
  HealthResponse,
  ProviderList,
  ProviderModelList,
  SystemStatus,
} from "@/types/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // ignore parse error
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<HealthResponse>("/health"),
  systemStatus: () => request<SystemStatus>("/api/system/status"),
  providers: () => request<ProviderList>("/api/providers"),
  openrouterModels: () =>
    request<ProviderModelList>("/api/providers/openrouter/models"),
  chat: (body: ChatRequest) =>
    request<ChatResponse>("/api/chat", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
