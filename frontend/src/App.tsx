import { useEffect, useState } from "react";
import {
  api,
  type ControlWithStatus,
  type Framework,
  type FrameworkScore,
  type Gap,
  type Organization,
} from "./api";

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
  const [error, setError] = useState<string | null>(null);

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

  const refresh = () => {
    if (!orgId || !frameworkId) return;
    api.getFrameworkScore(frameworkId, orgId).then(setScore).catch((e) => setError(String(e)));
    api
      .listControlsWithStatus(frameworkId, orgId)
      .then(setControls)
      .catch((e) => setError(String(e)));
    api.listGaps(orgId).then(setGaps).catch((e) => setError(String(e)));
  };

  useEffect(refresh, [orgId, frameworkId]);

  const handleGapStatus = async (gapId: string, newStatus: string) => {
    await api.updateGapStatus(gapId, newStatus);
    refresh();
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
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {gaps.map((g) => (
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
                    {g.status === "open" && (
                      <>
                        <button onClick={() => handleGapStatus(g.id, "in_progress")}>
                          Start
                        </button>
                        <button onClick={() => handleGapStatus(g.id, "risk_accepted")}>
                          Accept risk
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

export default App;
