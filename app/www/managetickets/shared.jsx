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

(() => {
// All declarations live inside this IIFE: babel-standalone runs
// each text/babel script in the GLOBAL scope (it injects a plain
// <script> element), so top-level const/function declarations from
// different scripts collide. Only window.Manage escapes this scope.
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

/* Fetch wrapper: attaches the management key, normalises error shapes.
 * When adminKey is empty/null, the header is OMITTED — so an environment
 * that injects X-Admin-Key itself (reverse proxy, header extension,
 * embedding tool) supplies it in transit instead. */
async function api(path, adminKey, opts = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(opts.headers || {}),
  };
  if (adminKey) headers["X-Admin-Key"] = adminKey;
  const res = await fetch(path, { ...opts, headers });
  let data = null;
  try { data = await res.json(); } catch (e) { /* non-JSON body */ }
  return { ok: res.ok, status: res.status, data };
}

/*
 * KeyGate — the page's content only renders once the management key has
 * been verified against POST /tickets/manage/verify. The key lives in
 * component state only: nothing is written to storage, so closing or
 * refreshing the page requires re-entry. That is deliberate.
 *
 * Before prompting, the gate probes verify with NO key attached. Browsers
 * can't add custom headers themselves, but a reverse proxy, header
 * extension, or embedding tool that injects a valid X-Admin-Key onto
 * requests will make that probe succeed — in which case the prompt is
 * skipped entirely and every later API call also omits the header,
 * letting the same injection authenticate it in transit.
 *
 * Key state: null = probing, "" = ambient header verified (omit ours),
 * non-empty string = key the person typed.
 */
function KeyGate({ children }) {
  const [key, setKey] = useState(null);
  const [probing, setProbing] = useState(true);
  const [entered, setEntered] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    api("/tickets/manage/verify", null, { method: "POST" })
      .then((res) => { if (res.ok) setKey(""); })
      .catch(() => {})
      .finally(() => setProbing(false));
  }, []);

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

  if (probing) {
    return <p className="empty">Checking access…</p>;
  }

  if (key === null) {
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

/* Small inline-SVG icons for row actions (view / edit) — no icon library
 * dependency, consistent with the rest of this zero-build page set.
 * `title` renders a native tooltip; callers still supply aria-label on
 * the wrapping button for screen readers. */
function IconEye({ title = "View", ...rest }) {
  return (
    <svg viewBox="0 0 20 20" width="15" height="15" fill="none"
         stroke="currentColor" strokeWidth="1.6" aria-hidden="true" {...rest}>
      <title>{title}</title>
      <path d="M1.5 10S4.7 4.2 10 4.2 18.5 10 18.5 10 15.3 15.8 10 15.8 1.5 10 1.5 10Z"
            strokeLinejoin="round" strokeLinecap="round" />
      <circle cx="10" cy="10" r="2.4" />
    </svg>
  );
}

function IconPencil({ title = "Edit", ...rest }) {
  return (
    <svg viewBox="0 0 20 20" width="15" height="15" fill="none"
         stroke="currentColor" strokeWidth="1.6" aria-hidden="true" {...rest}>
      <title>{title}</title>
      <path d="M13.3 3.3a1.5 1.5 0 0 1 2.1 0l1.3 1.3a1.5 1.5 0 0 1 0 2.1L6 17.4l-4 .6.6-4 10.7-10.7Z"
            strokeLinejoin="round" strokeLinecap="round" />
      <path d="M11.6 5 15 8.4" strokeLinecap="round" />
    </svg>
  );
}

function fmtDate(iso) {
  if (!iso) return "";
  try { return new Date(iso).toLocaleString(); } catch (e) { return iso; }
}

/* Status history timeline (newest first — the API already orders desc). */
function UpdatesList({ updates }) {
  if (!updates || !updates.length) {
    return <p className="empty" style={{ textAlign: "left", padding: "8px 0" }}>
      No status updates yet.
    </p>;
  }
  return (
    <div className="updates">
      {updates.map((u, i) => (
        <div className="update-entry" key={u.id || i}>
          <div className="head">
            <StatusBadge status={u.status} />
            <span className="when">{fmtDate(u.created_at)}</span>
          </div>
          {u.message
            ? <div className="msg">{u.message}</div>
            : <div className="no-msg">No message with this update.</div>}
        </div>
      ))}
    </div>
  );
}

window.Manage = {
  useBranding, Brand, Nav, KeyGate, api, SevBadge, StatusBadge, SEV_COLORS,
  fmtDate, UpdatesList, IconEye, IconPencil,
};
})();
