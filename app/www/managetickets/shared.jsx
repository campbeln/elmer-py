/*
 * Shared components for the /www/managetickets pages.
 * Loaded via <script type="text/babel" src="/www/managetickets/shared.jsx">
 * after React and before each page's own script.
 *
 * Exposes on window.Manage:
 *   useBranding()   — branding from /tickets/meta/priorities (default CNRZ)
 *   Brand           — wordmark header
 *   Nav             — tab navigation between the three pages
 *   KeyGate         — blocks the page until X-Admin-Key verifies
 *   api(path, key, opts) — fetch wrapper that attaches the key header
 *   SevBadge, StatusBadge, SEV_COLORS, fmtDate
 */

const { useEffect, useState } = React;

const SEV_COLORS = { P1: "var(--p1)", P2: "var(--p2)", P3: "var(--p3)", P4: "var(--p4)" };

const DEFAULT_BRANDING = { name: "CNRZ", area: "Support" };

function useBranding() {
  const [branding, setBranding] = useState(DEFAULT_BRANDING);
  useEffect(() => {
    fetch("/tickets/meta/priorities")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d && d.branding && d.branding.name) setBranding(d.branding); })
      .catch(() => {});
  }, []);
  return branding;
}

function Brand({ branding, page }) {
  return (
    <header className="brand">
      <span className="bolt" aria-hidden="true">⚡</span>
      <span className="word">{branding.name}</span>
      <span className="div">/</span>
      <span className="area">{branding.area || "Support"}{page ? " · " + page : ""}</span>
    </header>
  );
}

function Nav({ current }) {
  const tabs = [
    { id: "queue", label: "Queue", href: "/www/managetickets/" },
    { id: "view", label: "Look up", href: "/www/managetickets/view/" },
    { id: "status", label: "Update status", href: "/www/managetickets/status/" },
  ];
  return (
    <nav className="manage-nav" aria-label="Ticket management">
      {tabs.map((t) => (
        <a key={t.id} href={t.href} aria-current={t.id === current ? "page" : undefined}>
          {t.label}
        </a>
      ))}
    </nav>
  );
}

/* Fetch wrapper: attaches the management key, normalises error shapes. */
async function api(path, adminKey, opts = {}) {
  const res = await fetch(path, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Key": adminKey,
      ...(opts.headers || {}),
    },
  });
  let data = null;
  try { data = await res.json(); } catch (e) { /* non-JSON body */ }
  return { ok: res.ok, status: res.status, data };
}

/*
 * KeyGate — the page's content only renders once the management key has
 * been verified against POST /tickets/manage/verify. The key lives in
 * component state only: nothing is written to storage, so closing or
 * refreshing the page requires re-entry. That is deliberate.
 */
function KeyGate({ children }) {
  const [key, setKey] = useState("");
  const [entered, setEntered] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function verify(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api("/tickets/manage/verify", entered, { method: "POST" });
      if (res.ok) {
        setKey(entered);
      } else if (res.status === 503) {
        setError("Management is not enabled on the server — TICKETS_ADMIN_KEY is unset.");
      } else {
        setError("That key was not accepted.");
      }
    } catch (err) {
      setError("The API is unreachable. Check that the server is running.");
    } finally {
      setBusy(false);
    }
  }

  if (!key) {
    return (
      <div className="gate">
        <h2>Management key required</h2>
        <p>
          This console is restricted. Enter the management key configured on
          the server (TICKETS_ADMIN_KEY) to continue.
        </p>
        <form onSubmit={verify}>
          <label>
            <span className="tag">Management key</span>
            <input
              type="password"
              value={entered}
              onChange={(e) => setEntered(e.target.value)}
              placeholder="••••••••••••"
              autoFocus
            />
          </label>
          {error && <div className="error" role="alert">{error}</div>}
          <div>
            <button className="btn" type="submit" disabled={busy || !entered}>
              {busy ? "Checking…" : "Unlock"}<span className="arrow">→</span>
            </button>
          </div>
          <p className="note">
            The key is held in memory only and sent as a request header —
            never stored, never placed in the URL.
          </p>
        </form>
      </div>
    );
  }

  return children(key);
}

function SevBadge({ code }) {
  return <span className="sev-badge" style={{ "--sev": SEV_COLORS[code] || "var(--p4)" }}>{code}</span>;
}

function StatusBadge({ status }) {
  return <span className="status-badge" data-s={status}>{String(status || "").replace("_", " ")}</span>;
}

function fmtDate(iso) {
  if (!iso) return "";
  try { return new Date(iso).toLocaleString(); } catch (e) { return iso; }
}

window.Manage = {
  useBranding, Brand, Nav, KeyGate, api, SevBadge, StatusBadge, SEV_COLORS, fmtDate,
};
