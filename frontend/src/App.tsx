import { useEffect, useState } from "react";
import { api, type Organization, type User } from "./api";
import Dashboard from "./Dashboard";
import ChatPanel from "./ChatPanel";

function App() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [orgId, setOrgId] = useState<string>("");
  const [users, setUsers] = useState<User[]>([]);
  const [tab, setTab] = useState<"dashboard" | "chat">("dashboard");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listOrganizations()
      .then((orgs) => {
        setOrganizations(orgs);
        if (orgs.length) setOrgId(orgs[0].id);
      })
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!orgId) return;
    api.listUsers(orgId).then(setUsers).catch((e) => setError(String(e)));
  }, [orgId]);

  const adminUserId = users.find((u) => u.role === "admin")?.id ?? users[0]?.id;

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
        </div>
      </header>

      {error && <p className="error">{error}</p>}

      <div className="tabs">
        <button
          className={tab === "dashboard" ? "tab-active" : ""}
          onClick={() => setTab("dashboard")}
        >
          Dashboard
        </button>
        <button className={tab === "chat" ? "tab-active" : ""} onClick={() => setTab("chat")}>
          Chat
        </button>
      </div>

      {tab === "dashboard" && orgId && <Dashboard orgId={orgId} />}
      {tab === "chat" && orgId && adminUserId && (
        <ChatPanel orgId={orgId} userId={adminUserId} />
      )}
    </div>
  );
}

export default App;
