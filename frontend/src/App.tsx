import { useEffect, useState } from "react";
import {
  api,
  type Action,
  type ControlWithStatus,
  type Framework,
  type FrameworkScore,
  type Gap,
  type M365Status,
  type Organization,
  type User,
} from "./api";

const MFA_KEYWORDS = ["multi-factor", "mfa", "conditional access"];
const isMfaControl = (c: ControlWithStatus) =>
  MFA_KEYWORDS.some((k) => c.description.toLowerCase().includes(k));

const STATUS_COLORS: Record<string, string> = {
  met: "#1a7f37",
  partial: "#9a6700",
  not_met: "#cf222e",
  not_applicable: "#6e7781",
  unscored: "#9198a1",
};

const SEVERITY_COLORS: Record<string, string> = {
  critical: "#a40e26",
  high: "#cf222e",
  medium: "#9a6700",
  low: "#6e7781",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className="badge"
      style={{ backgroundColor: STATUS_COLORS[status] ?? "#9198a1" }}
    >
      {status.replace("_", " ")}
    </span>
  );
}

function App() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [frameworks, setFrameworks] = useState<Framework[]>([]);
  const [orgId, setOrgId] = useState<string>("");
  const [frameworkId, setFrameworkId] = useState<string>("");
  const [score, setScore] = useState<FrameworkScore | null>(null);
  const [controls, setControls] = useState<ControlWithStatus[]>([]);
  const [gaps, setGaps] = useState<Gap[]>([]);
  const [actions, setActions] = useState<Action[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [m365Status, setM365Status] = useState<M365Status | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.listOrganizations(), api.listFrameworks()])
      .then(([orgs, fws]) => {
        setOrganizations(orgs);
        setFrameworks(fws);
        if (orgs.length) setOrgId(orgs[0].id);
        if (fws.length) setFrameworkId(fws[0].id);
      })
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!orgId) return;
    api.listUsers(orgId).then(setUsers).catch((e) => setError(String(e)));
    api.getM365Status(orgId).then(setM365Status).catch((e) => setError(String(e)));
  }, [orgId]);

  const refresh = () => {
    if (!orgId || !frameworkId) return;
    api.getFrameworkScore(frameworkId, orgId).then(setScore).catch((e) => setError(String(e)));
    api
      .listControlsWithStatus(frameworkId, orgId)
      .then(setControls)
      .catch((e) => setError(String(e)));
    api.listGaps(orgId).then(setGaps).catch((e) => setError(String(e)));
    api.listActions(orgId).then(setActions).catch((e) => setError(String(e)));
  };

  useEffect(refresh, [orgId, frameworkId]);

  const handleGapStatus = async (gapId: string, newStatus: string) => {
    await api.updateGapStatus(gapId, newStatus);
    refresh();
  };

  const adminUserId = users.find((u) => u.role === "admin")?.id ?? users[0]?.id;

  const handlePropose = async (gapId: string) => {
    await api.proposeAction(gapId);
    refresh();
  };

  const handleApprove = async (actionId: string) => {
    if (!adminUserId) return;
    await api.approveAction(actionId, adminUserId);
    refresh();
  };

  const handleReject = async (actionId: string) => {
    if (!adminUserId) return;
    await api.rejectAction(actionId, adminUserId);
    refresh();
  };

  const latestActionForGap = (gapId: string): Action | undefined => {
    const forGap = actions.filter((a) => a.gap_id === gapId);
    return (
      forGap.find((a) => a.status === "pending_approval") ??
      forGap[forGap.length - 1]
    );
  };

  const handleSyncM365 = async (controlId: string) => {
    setSyncMessage(null);
    setError(null);
    try {
      await api.syncM365Mfa(orgId, controlId);
      setSyncMessage("Synced live Conditional Access data from Microsoft 365.");
      api.getM365Status(orgId).then(setM365Status);
      refresh();
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  };

  return (
    <div className="page">
      <header>
        <h1>GRC Dashboard</h1>
        <div className="selectors">
          <label>
            Organization
            <select value={orgId} onChange={(e) => setOrgId(e.target.value)}>
              {organizations.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Framework
            <select
              value={frameworkId}
              onChange={(e) => setFrameworkId(e.target.value)}
            >
              {frameworks.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name} {f.version}
                </option>
              ))}
            </select>
          </label>
        </div>
      </header>

      {error && <p className="error">{error}</p>}
      {syncMessage && <p className="success">{syncMessage}</p>}

      <section className="integrations">
        <h2>Integrations</h2>
        <div className="integration-row">
          <span className="integration-name">Microsoft 365 / Entra ID</span>
          {m365Status?.configured ? (
            <span className="badge" style={{ backgroundColor: "#1a7f37" }}>
              configured
            </span>
          ) : (
            <span className="badge" style={{ backgroundColor: "#9198a1" }}>
              not configured
            </span>
          )}
          <span className="empty">
            {m365Status?.last_sync_at
              ? `Last synced ${new Date(m365Status.last_sync_at).toLocaleString()}`
              : "Never synced"}
          </span>
        </div>
        {!m365Status?.configured && (
          <p className="empty">
            Set M365_TENANT_ID, M365_CLIENT_ID, and M365_CLIENT_SECRET in backend/.env to enable.
          </p>
        )}
      </section>

      {score && (
        <section className="score-card">
          <div className="score-pct">{score.score_pct}%</div>
          <div className="score-breakdown">
            <span>{score.met} met</span>
            <span>{score.partial} partial</span>
            <span>{score.not_met} not met</span>
            <span>{score.not_applicable} n/a</span>
            <span>{score.unscored} unscored</span>
            <span>{score.total_controls} total controls</span>
          </div>
        </section>
      )}

      <section>
        <h2>Controls</h2>
        <table>
          <thead>
            <tr>
              <th>Ref</th>
              <th>Requirement</th>
              <th>Control</th>
              <th>Status</th>
              <th>Live source</th>
            </tr>
          </thead>
          <tbody>
            {controls.map((c) => (
              <tr key={c.id}>
                <td>{c.ref_code}</td>
                <td>{c.requirement_title}</td>
                <td>{c.description}</td>
                <td>
                  <StatusBadge status={c.status} />
                </td>
                <td>
                  {isMfaControl(c) && (
                    <button
                      disabled={!m365Status?.configured}
                      title={
                        m365Status?.configured
                          ? "Pull live Conditional Access policies from Microsoft Graph"
                          : "Configure M365 credentials in backend/.env first"
                      }
                      onClick={() => handleSyncM365(c.id)}
                    >
                      Sync from M365
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h2>Gaps &amp; Action Items</h2>
        {gaps.length === 0 ? (
          <p className="empty">No open gaps.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Severity</th>
                <th>Description</th>
                <th>Status</th>
                <th>Remediation</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {gaps.map((g) => {
                const action = latestActionForGap(g.id);
                return (
                  <tr key={g.id}>
                    <td>
                      <span
                        className="badge"
                        style={{ backgroundColor: SEVERITY_COLORS[g.severity] }}
                      >
                        {g.severity}
                      </span>
                    </td>
                    <td>{g.description}</td>
                    <td>{g.status}</td>
                    <td>
                      {action ? (
                        <div className="action-cell">
                          <code>
                            {action.adapter_type}.{action.action_type}
                          </code>
                          <span className={`badge action-status-${action.status}`}>
                            {action.status.replace("_", " ")}
                          </span>
                          {typeof action.parameters?.rationale === "string" && (
                            <p className="rationale">{action.parameters.rationale}</p>
                          )}
                        </div>
                      ) : (
                        <span className="empty">No proposal yet</span>
                      )}
                    </td>
                    <td>
                      {(g.status === "open" || g.status === "in_progress") && (
                        <>
                          {g.status === "open" && (
                            <button onClick={() => handleGapStatus(g.id, "in_progress")}>
                              Start
                            </button>
                          )}
                          <button onClick={() => handleGapStatus(g.id, "risk_accepted")}>
                            Accept risk
                          </button>
                          {(!action || action.status === "rejected" || action.status === "failed") && (
                            <button onClick={() => handlePropose(g.id)}>Propose fix</button>
                          )}
                          {action?.status === "pending_approval" && (
                            <>
                              <button onClick={() => handleApprove(action.id)}>
                                Approve &amp; execute
                              </button>
                              <button onClick={() => handleReject(action.id)}>Reject</button>
                            </>
                          )}
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

export default App;
