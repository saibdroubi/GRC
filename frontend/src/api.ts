const BASE_URL = "http://127.0.0.1:8000";

export interface Organization {
  id: string;
  name: string;
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

export interface User {
  id: string;
  name: string;
  email: string;
  role: string;
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

export interface M365Status {
  configured: boolean;
  connection_id: string | null;
  status: string | null;
  last_sync_at: string | null;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  return res.json();
}

async function postJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, { method: "POST" });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `${path} failed: ${res.status}`);
  }
  return res.json();
}

export const api = {
  listOrganizations: () => getJson<Organization[]>("/organizations"),
  listFrameworks: () => getJson<Framework[]>("/frameworks"),
  getFrameworkScore: (frameworkId: string, organizationId: string) =>
    getJson<FrameworkScore>(
      `/frameworks/${frameworkId}/score?organization_id=${organizationId}`
    ),
  listControlsWithStatus: (frameworkId: string, organizationId: string) =>
    getJson<ControlWithStatus[]>(
      `/frameworks/${frameworkId}/controls-with-status?organization_id=${organizationId}`
    ),
  listGaps: (organizationId: string) =>
    getJson<Gap[]>(`/gaps?organization_id=${organizationId}`),
  updateGapStatus: async (gapId: string, newStatus: string) => {
    const res = await fetch(
      `${BASE_URL}/gaps/${gapId}?new_status=${newStatus}`,
      { method: "PATCH" }
    );
    if (!res.ok) throw new Error(`update gap failed: ${res.status}`);
    return res.json();
  },
  listUsers: (organizationId: string) =>
    getJson<User[]>(`/users?organization_id=${organizationId}`),
  listActions: (organizationId: string) =>
    getJson<Action[]>(`/actions?organization_id=${organizationId}`),
  proposeAction: (gapId: string) =>
    postJson<Action>(`/gaps/${gapId}/actions`),
  approveAction: (actionId: string, userId: string) =>
    postJson<Action>(`/actions/${actionId}/approve?user_id=${userId}`),
  rejectAction: (actionId: string, userId: string) =>
    postJson<Action>(`/actions/${actionId}/reject?user_id=${userId}`),
  getM365Status: (organizationId: string) =>
    getJson<M365Status>(`/integrations/m365/status?organization_id=${organizationId}`),
  syncM365Mfa: (organizationId: string, controlId: string) =>
    postJson<unknown>(
      `/integrations/m365/sync?organization_id=${organizationId}&control_id=${controlId}`
    ),
};
