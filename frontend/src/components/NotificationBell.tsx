import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { fetchNotifications, markNotificationRead } from "../api/notifications";
import type { NotificationItem } from "../types/notification";

export const NotificationBell = () => {
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  const loadNotifications = async () => {
    try {
      setLoading(true);
      const data = await fetchNotifications();
      setNotifications(data.notifications);
      setUnreadCount(data.unread_count);
    } catch {
      // Background notifications failure should not break layout
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadNotifications();
    const interval = setInterval(() => {
      void loadNotifications();
    }, 15000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleClickItem = async (item: NotificationItem) => {
    if (!item.is_read) {
      try {
        await markNotificationRead(item.id);
        setNotifications((prev) =>
          prev.map((n) => (n.id === item.id ? { ...n, is_read: true } : n)),
        );
        setUnreadCount((count) => Math.max(0, count - 1));
      } catch {
        // Continue navigation even if markRead fails
      }
    }
    setIsOpen(false);
    const needsDocuments =
      Boolean(item.workflow_id) &&
      (item.notification_type === "missing_documents" ||
        item.notification_type === "documents_required" ||
        item.notification_type === "more_information_required" ||
        /missing|required document|additional information/i.test(
          `${item.title} ${item.message}`,
        ));

    if (needsDocuments && item.workflow_id && item.claim_id) {
      navigate(
        `/dashboard/claims/${encodeURIComponent(item.claim_id)}?workflowId=${encodeURIComponent(item.workflow_id)}&action=upload-documents`,
      );
    } else if (needsDocuments && item.workflow_id) {
      navigate(
        `/claim-assistant?workflowId=${encodeURIComponent(item.workflow_id)}&action=upload-documents`,
      );
    } else if (item.claim_id) {
      navigate(`/dashboard/claims/${encodeURIComponent(item.claim_id)}`);
    }
  };

  return (
    <div className="relative inline-block text-left" ref={menuRef}>
      <button
        type="button"
        aria-label="Notifications"
        aria-expanded={isOpen}
        onClick={() => setIsOpen(!isOpen)}
        style={{
          position: "relative",
          background: "transparent",
          border: "1px solid #dbe5e5",
          borderRadius: "8px",
          padding: "6px 10px",
          cursor: "pointer",
          fontSize: "16px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <span>🔔</span>
        {unreadCount > 0 && (
          <span
            style={{
              position: "absolute",
              top: "-4px",
              right: "-4px",
              background: "#bd3e2b",
              color: "white",
              fontSize: "10px",
              fontWeight: "bold",
              borderRadius: "10px",
              padding: "1px 5px",
              lineHeight: 1,
            }}
          >
            {unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div
          style={{
            position: "absolute",
            right: 0,
            marginTop: "8px",
            width: "320px",
            backgroundColor: "white",
            border: "1px solid #dbe5e5",
            borderRadius: "10px",
            boxShadow: "0 8px 24px rgba(0,0,0,0.12)",
            zIndex: 100,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              padding: "10px 14px",
              borderBottom: "1px solid #edf1f1",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              backgroundColor: "#f9fbfb",
            }}
          >
            <span style={{ fontWeight: "bold", fontSize: "13px", color: "#142b3a" }}>
              Notifications
            </span>
            {unreadCount > 0 && (
              <span
                style={{
                  fontSize: "11px",
                  color: "#e86d45",
                  fontWeight: "600",
                }}
              >
                {unreadCount} new
              </span>
            )}
          </div>

          <div style={{ maxHeight: "360px", overflowY: "auto" }}>
            {loading && notifications.length === 0 ? (
              <div style={{ padding: "16px", textAlign: "center", color: "#788990", fontSize: "12px" }}>
                Checking for updates…
              </div>
            ) : notifications.length === 0 ? (
              <div style={{ padding: "20px", textAlign: "center", color: "#788990", fontSize: "12px" }}>
                No notifications yet.
              </div>
            ) : (
              notifications.map((n) => (
                <div
                  key={n.id}
                  onClick={() => void handleClickItem(n)}
                  style={{
                    padding: "12px 14px",
                    borderBottom: "1px solid #edf1f1",
                    cursor: "pointer",
                    backgroundColor: n.is_read ? "white" : "#fffaf7",
                    transition: "background 0.15s ease",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = n.is_read ? "#f5f8f8" : "#fff4ed";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = n.is_read ? "white" : "#fffaf7";
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                    <strong style={{ fontSize: "12px", color: n.is_read ? "#2b3b44" : "#bd3e2b" }}>
                      {n.title}
                    </strong>
                    {!n.is_read && (
                      <span
                        style={{
                          width: "6px",
                          height: "6px",
                          borderRadius: "50%",
                          backgroundColor: "#e86d45",
                          display: "inline-block",
                        }}
                      />
                    )}
                  </div>
                  <p style={{ margin: "4px 0 0 0", fontSize: "12px", color: "#526b75", lineHeight: 1.4 }}>
                    {n.message}
                  </p>
                  {n.created_at && (
                    <small style={{ fontSize: "10px", color: "#9aa8ac", marginTop: "4px", display: "block" }}>
                      {new Date(n.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </small>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};
