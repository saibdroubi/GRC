import { useEffect, useState } from "react";
import {
  api,
  type Action,
  type ControlWithStatus,
  type Framework,
  type FrameworkScore,
  type Gap,
  type IntegrationStatus,
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
    <span className="badge" style={{ backgroundColor: STATUS_COLORS[status] ?? "#9198a1" }}>
      {status.replace("_", " ")}
    </span>
  );
}

export default function Dashboard({ orgId }: { orgId: string }) {
  const [frameworks, setFrameworks] = useState<Framework[]>([]);
  const [frameworkId, setFrameworkId] = useState<string>("");
  const [score, setScore] = useState<FrameworkScore | null>(null);
  const [controls, setControls] = useState<ControlWithStatus[]>([]);
  const [gaps, setGaps] = useState<Gap[]>([]);
  const [actions, setActions] = useState<Action[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [integrations, setIntegrations] = useState<IntegrationStatus[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);

  useEffect(() => {
    api.listFrameworks().then((fws) => {
      setFrameworks(fws);
      if (fws.length) setFrameworkId(fws[0].id);
    }).catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!orgId) return;
    api.listUsers(orgId).then(setUsers).catch((e) => setError(String(e)));
    api.listIntegrations(orgId).then(setIntegrations).catch((e) => setError(String(e)));
  }, [orgId]);

  const refresh = () => {
    if (!orgId || !frameworkId) return;
    api.getFrameworkScore(frameworkId, orgId).then(setScore).catch((e) => setError(String(e)));
    api.listControlsWithStatus(frameworkId, orgId).then(setControls).catch((e) => setError(String(e)));
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
    return forGap.find((a) => a.status === "pending_approval") ?? forGap[forGap.length - 1];
  };

  const m365 = integrations.find((i) => i.type === "m365");

  const handleSyncM365 = async (controlId: string) => {
    setSyncMessage(null);
    setError(null);
    try {
      await api.syncIntegrationEvidence(orgId, "m365", controlId);
      setSyncMessage("Synced live Conditional Access data from Microsoft 365.");
      api.listIntegrations(orgId).then(setIntegrations);
      refresh();
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  };

  return (
    <>
      <div className="selectors" style={{ marginBottom: 16 }}>
        <label>
          Framework
          <select value={frameworkId} onChange={(e) => setFrameworkId(e.target.value)}>
            {frameworks.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name} {f.version}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error && <p className="error">{error}</p>}
      {syncMessage && <p className="success">{syncMessage}</p>}

      <section className="integrations">
        <h2>Integrations</h2>
        {integrations.map((i) => (
          <div className="integration-row" key={i.type}>
            <span className="integration-name">{i.display_name}</span>
            <span
              className="badge"
              style={{ backgroundColor: i.configured ? "#1a7f37" : "#9198a1" }}
            >
              {i.configured ? "configured" : "not configured"}
            </span>
            <span className="empty">
              {i.last_sync_at ? `Last synced ${new Date(i.last_sync_at).toLocaleString()}` : "Never synced"}
            </span>
          </div>
        ))}
        <p className="empty">
          Configure these via the Chat tab — e.g. "let's integrate our Nessus scanner" — or
          directly through the API.
        </p>
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
                      disabled={!m365?.configured}
                      title={
                        m365?.configured
                          ? "Pull live Conditional Access policies from Microsoft Graph"
                          : "Configure M365 via the Chat tab first"
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
                      <span className="badge" style={{ backgroundColor: SEVERITY_COLORS[g.severity] }}>
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
                            <button onClick={() => handleGapStatus(g.id, "in_progress")}>Start</button>
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
    </>
  );
}
