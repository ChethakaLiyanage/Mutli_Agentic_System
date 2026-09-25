import { NavLink, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../context/auth-context";
import { NotificationBell } from "./NotificationBell";

export const AppLayout = () => {
  const { user, logout } = useAuth();
  const location = useLocation();
  const isCustomer = user?.role !== "admin";
  const isChat = isCustomer && location.pathname === "/claim-assistant";

  return (
    <div className={isChat ? "app-shell app-shell-chat" : "app-shell"}>
      <header className="app-header">
        <NavLink
          to={isCustomer ? "/claim-assistant" : "/admin-dashboard"}
          className="brand-lockup"
          style={{ textDecoration: "none" }}
        >
          <span className="brand-mark" aria-hidden="true">MI</span>
          <div>
            <p className="brand-name">
              {isCustomer ? "Motor Insurance Assistant" : "Motor Insurance"}
            </p>
            <p className="brand-subtitle">Claims &amp; policy support</p>
          </div>
        </NavLink>

        <div className="user-menu" style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          {isCustomer && <NotificationBell />}
          {isCustomer && (
            <NavLink
              to="/profile"
              className="profile-avatar-btn"
              aria-label="Your profile"
              title={user?.email ?? "Profile"}
            >
              <svg
                width="22"
                height="22"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <circle cx="12" cy="8" r="4" />
                <path d="M20 21a8 8 0 1 0-16 0" />
              </svg>
            </NavLink>
          )}
          {!isCustomer && (
            <div className="user-summary">
              <span className="user-email">{user?.email}</span>
              <span className="role-badge">{user?.role.replace("_", " ")}</span>
            </div>
          )}
          <button className="button button-secondary button-small" onClick={logout}>
            Log out
          </button>
        </div>
      </header>

      <main className={isCustomer ? "app-main app-main-chat" : "app-main"}>
        <Outlet />
      </main>
    </div>
  );
};
