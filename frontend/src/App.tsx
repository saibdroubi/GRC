import { useEffect, useState } from "react";
import { api, type CurrentUser } from "./api";
import Dashboard from "./Dashboard";
import ChatPanel from "./ChatPanel";
import Login from "./Login";
import Signup from "./Signup";

function App() {
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [authView, setAuthView] = useState<"login" | "signup">("login");
  const [tab, setTab] = useState<"dashboard" | "chat">("dashboard");

  useEffect(() => {
    api
      .getCurrentUser()
      .then(setCurrentUser)
      .catch(() => setCurrentUser(null))
      .finally(() => setAuthChecked(true));
  }, []);

  const handleLogout = async () => {
    await api.logout();
    setCurrentUser(null);
    setAuthView("login");
  };

  if (!authChecked) return null;

  if (!currentUser) {
    return authView === "login" ? (
      <Login onAuthenticated={setCurrentUser} onSwitchToSignup={() => setAuthView("signup")} />
    ) : (
      <Signup onAuthenticated={setCurrentUser} onSwitchToLogin={() => setAuthView("login")} />
    );
  }

  return (
    <div className="page">
      <header>
        <h1>GRC Dashboard</h1>
        <div className="user-info">
          <span className="org-name">{currentUser.organization_name}</span>
          <span className="empty">
            {currentUser.name} ({currentUser.role})
          </span>
          <button onClick={handleLogout}>Log out</button>
        </div>
      </header>

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

      {tab === "dashboard" && <Dashboard />}
      {tab === "chat" && <ChatPanel />}
    </div>
  );
}

export default App;
