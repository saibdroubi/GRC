// Must be host-aligned with the frontend origin (both "localhost") so the
// SameSite=Strict session cookie counts as same-site and is actually sent;
// "127.0.0.1" and "localhost" are different sites even on the same machine.
const BASE_URL = "http://localhost:8000";

export interface CurrentUser {
  id: string;
  name: string;
  email: string;
  role: string;
  organization_id: string;
  organization_name: string;
}

export interface Framework {
  id: string;
  name: string;
  version: string;
  status: string;
}

export interface FrameworkScore {
  framework_id: string;
  framework_name: string;
  framework_version: string;
  total_controls: number;
  met: number;
  partial: number;
  not_met: number;
  not_applicable: number;
  unscored: number;
  score_pct: number;
}

export interface ControlWithStatus {
  id: string;
  ref_code: string;
  requirement_title: string;
  description: string;
  status: string;
  confidence: number;
  gap_id: string | null;
  gap_severity: string | null;
  gap_status: string | null;
  gap_description: string | null;
}

export interface Gap {
  id: string;
  control_id: string;
  organization_id: string;
  severity: string;
  description: string;
  recommended_action: string | null;
  status: string;
}

export interface Action {
  id: string;
  gap_id: string;
  adapter_type: string;
  action_type: string;
  parameters: Record<string, unknown>;
  status: string;
  proposed_by: string;
  approved_by_user_id: string | null;
  executed_at: string | null;
  result: Record<string, unknown>;
}

export interface IntegrationStatus {
  type: string;
  display_name: string;
  configured: boolean;
  missing_fields: string[];
  status: string | null;
  last_sync_at: string | null;
}

export interface ChatSession {
  id: string;
  organization_id: string;
  user_id: string;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  tool_calls: Record<string, unknown>;
  created_at: string;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, { credentials: "include" });
  if (!res.ok) {
    const errBody = await res.json().catch(() => null);
    throw new Error(errBody?.detail ?? `${path} failed: ${res.status}`);
  }
  return res.json();
}

async function sendJson<T>(path: string, method: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    credentials: "include",
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const errBody = await res.json().catch(() => null);
    throw new Error(errBody?.detail ?? `${path} failed: ${res.status}`);
  }
  return res.json();
}

const postJson = <T>(path: string, body?: unknown) => sendJson<T>(path, "POST", body);

export const api = {
  signup: (organizationName: string, name: string, email: string, password: string) =>
    postJson<CurrentUser>("/auth/signup", {
      organization_name: organizationName,
      name,
      email,
      password,
    }),
  login: (email: string, password: string) => postJson<CurrentUser>("/auth/login", { email, password }),
  logout: () => postJson<{ status: string }>("/auth/logout"),
  getCurrentUser: () => getJson<CurrentUser>("/auth/me"),

  listFrameworks: () => getJson<Framework[]>("/frameworks"),
  getFrameworkScore: (frameworkId: string) =>
    getJson<FrameworkScore>(`/frameworks/${frameworkId}/score`),
  listControlsWithStatus: (frameworkId: string) =>
    getJson<ControlWithStatus[]>(`/frameworks/${frameworkId}/controls-with-status`),
  listGaps: () => getJson<Gap[]>("/gaps"),
  updateGapStatus: (gapId: string, newStatus: string) =>
    sendJson<Gap>(`/gaps/${gapId}?new_status=${newStatus}`, "PATCH"),
  listActions: () => getJson<Action[]>("/actions"),
  proposeAction: (gapId: string) => postJson<Action>(`/gaps/${gapId}/actions`),
  approveAction: (actionId: string) => postJson<Action>(`/actions/${actionId}/approve`),
  rejectAction: (actionId: string) => postJson<Action>(`/actions/${actionId}/reject`),
  listIntegrations: () => getJson<IntegrationStatus[]>("/integrations"),
  syncIntegrationEvidence: (type: string, controlId: string) =>
    postJson<unknown>(`/integrations/${type}/sync?control_id=${controlId}`),
  createChatSession: () => postJson<ChatSession>("/chat/sessions"),
  listChatSessions: () => getJson<ChatSession[]>("/chat/sessions"),
  listChatMessages: (sessionId: string) => getJson<ChatMessage[]>(`/chat/sessions/${sessionId}/messages`),
  postChatMessage: (sessionId: string, content: string) =>
    postJson<ChatMessage>(`/chat/sessions/${sessionId}/messages`, { content }),
};
