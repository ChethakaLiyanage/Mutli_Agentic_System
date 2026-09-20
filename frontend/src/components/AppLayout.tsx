import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../context/auth-context";
import { NotificationBell } from "./NotificationBell";

export const AppLayout = () => {
  const { user, logout } = useAuth();

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true">MI</span>
          <div>
            <p className="brand-name">Motor Insurance</p>
            <p className="brand-subtitle">Claims &amp; policy support</p>
          </div>
        </div>

        <nav className="header-nav" aria-label="Primary navigation">
          {user?.role !== "admin" && <NavLink to="/dashboard">Dashboard</NavLink>}
          {user?.role !== "admin" && <NavLink to="/claim-assistant">Claim Assistant</NavLink>}
          {user?.role !== "admin" && <NavLink to="/dashboard/claims">My Claims</NavLink>}
        </nav>

        <div className="user-menu" style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          {user?.role !== "admin" && <NotificationBell />}
          <div className="user-summary">
            <span className="user-email">{user?.email}</span>
            <span className="role-badge">{user?.role.replace("_", " ")}</span>
          </div>
          <button className="button button-secondary button-small" onClick={logout}>
            Log out
          </button>
        </div>
      </header>

      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
};
