import { useEffect, useState } from "react";

/*
 * Support ticket form — bltz.ai-styled preview.
 *
 * This is the same component that ships in the Elmer project at
 * app/www/tickets.html. There it POSTs to the /tickets API; in this
 * preview, if the API is unreachable it falls back to a simulated
 * submission so the full flow can be exercised.
 */

const API_BASE = "/tickets";

const DEFAULT_PRIORITIES = [
  {
    code: "P1",
    label: "Critical",
    description:
      "Complete production service outage, active security incident, data loss, or failure of core production functionality with material business impact and no reasonable workaround.",
  },
  {
    code: "P2",
    label: "High",
    description:
      "Major degradation of core functionality or partial loss of production service that materially impacts use of the Platform.",
  },
  {
    code: "P3",
    label: "Medium",
    description:
      "Non-critical issue with limited impact, minor degradation, or issue where a reasonable workaround is available.",
  },
  {
    code: "P4",
    label: "Low / Request",
    description:
      "General inquiry, cosmetic issue, documentation question, enhancement request, or other issue with no material operational impact.",
  },
];

const SEV_COLORS = { P1: "#FF4D5E", P2: "#FF9F45", P3: "#F5C542", P4: "#8B93A8" };

const css = `
  @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@500&display=swap');

  .bz-root {
    --bg: #060609; --panel: #0C0C12; --panel2: #101018; --line: #1E1E2A;
    --text: #EDEEF3; --muted: #8B8FA3;
    --violet: #7C5CFF; --violet-deep: #5A3DF0; --bolt: #FFD84D; --r: 10px;
    min-height: 100vh; background: var(--bg); color: var(--text);
    font: 15px/1.6 "Inter", system-ui, sans-serif;
    background-image:
      radial-gradient(ellipse 60% 40% at 50% -10%, rgba(124,92,255,.14), transparent 70%),
      linear-gradient(rgba(255,255,255,.025) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255,255,255,.025) 1px, transparent 1px);
    background-size: auto, 44px 44px, 44px 44px;
  }
  .bz-wrap { max-width: 780px; margin: 0 auto; padding: 48px 20px 96px; }

  .bz-brand { display: flex; align-items: center; gap: 10px; margin-bottom: 44px; }
  .bz-brand .bolt { color: var(--bolt); font-size: 20px; transform: skewX(-8deg); }
  .bz-brand .word { font-family: "Space Grotesk", sans-serif; font-weight: 700; letter-spacing: .14em; font-size: 17px; }
  .bz-brand .div { color: var(--line); }
  .bz-brand .area { color: var(--muted); letter-spacing: .22em; font-size: 12px; text-transform: uppercase; }

  .bz-eyebrow { font-family: "JetBrains Mono", monospace; font-size: 11px; letter-spacing: .28em; color: var(--violet); text-transform: uppercase; margin: 0 0 14px; }
  .bz-h1 { font-family: "Space Grotesk", sans-serif; font-weight: 700; font-size: clamp(30px, 5vw, 42px); line-height: 1.12; letter-spacing: -.01em; margin: 0 0 12px; }
  .bz-lede { color: var(--muted); max-width: 56ch; margin: 0 0 40px; }

  .bz-form { display: grid; gap: 26px; }
  .bz-row { display: grid; gap: 26px; grid-template-columns: 1fr 1fr; }
  @media (max-width: 640px) { .bz-row { grid-template-columns: 1fr; } }

  .bz-tag { display: block; font-size: 12px; font-weight: 600; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); margin-bottom: 8px; }
  .bz-input, .bz-area {
    width: 100%; box-sizing: border-box; background: var(--panel); color: var(--text);
    border: 1px solid var(--line); border-radius: var(--r); padding: 12px 14px;
    font: inherit; transition: border-color .15s, box-shadow .15s;
  }
  .bz-input::placeholder, .bz-area::placeholder { color: #565B70; }
  .bz-input:focus-visible, .bz-area:focus-visible {
    outline: none; border-color: var(--violet); box-shadow: 0 0 0 3px rgba(124,92,255,.22);
  }
  .bz-area { min-height: 150px; resize: vertical; }

  .bz-sev-grid { display: grid; gap: 12px; grid-template-columns: 1fr 1fr; }
  @media (max-width: 640px) { .bz-sev-grid { grid-template-columns: 1fr; } }
  .bz-sev {
    position: relative; text-align: left; cursor: pointer; width: 100%;
    background: var(--panel); border: 1px solid var(--line); border-radius: var(--r);
    padding: 14px 16px 14px 22px; color: var(--text); font: inherit;
    transition: border-color .15s, background .15s, box-shadow .15s;
  }
  .bz-sev::before {
    content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
    border-radius: var(--r) 0 0 var(--r); background: var(--sev); opacity: .85;
  }
  .bz-sev:hover { background: var(--panel2); }
  .bz-sev[aria-pressed="true"] {
    border-color: var(--sev); background: var(--panel2);
    box-shadow: 0 0 0 1px var(--sev), 0 0 24px -8px var(--sev);
  }
  .bz-sev:focus-visible { outline: 2px solid var(--violet); outline-offset: 2px; }
  .bz-sev .head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 4px; }
  .bz-sev .code { font-family: "JetBrains Mono", monospace; font-size: 13px; font-weight: 500; color: var(--sev); letter-spacing: .06em; }
  .bz-sev .name { font-family: "Space Grotesk", sans-serif; font-weight: 500; font-size: 15px; }
  .bz-sev .desc { color: var(--muted); font-size: 13px; line-height: 1.5; display: block; }

  .bz-actions { display: flex; align-items: center; gap: 18px; margin-top: 4px; flex-wrap: wrap; }
  .bz-submit {
    font: 600 15px "Space Grotesk", sans-serif; letter-spacing: .02em; color: #fff;
    background: linear-gradient(135deg, var(--violet), var(--violet-deep));
    border: 0; border-radius: var(--r); padding: 13px 26px; cursor: pointer;
    box-shadow: 0 8px 28px -10px rgba(124,92,255,.65);
    transition: transform .12s, box-shadow .12s, opacity .12s;
  }
  .bz-submit:hover { transform: translateY(-1px); box-shadow: 0 12px 32px -10px rgba(124,92,255,.8); }
  .bz-submit:disabled { opacity: .55; cursor: default; transform: none; }
  .bz-submit .arrow { color: var(--bolt); margin-left: 8px; }
  .bz-hint { color: var(--muted); font-size: 13px; }

  .bz-error {
    border: 1px solid rgba(255,77,94,.4); background: rgba(255,77,94,.08);
    border-radius: var(--r); padding: 14px 16px; color: #FFB4BC; font-size: 14px;
  }
  .bz-error ul { margin: 6px 0 0 18px; }

  .bz-success {
    border: 1px solid rgba(124,92,255,.45); background: rgba(124,92,255,.07);
    border-radius: var(--r); padding: 28px;
  }
  .bz-success h2 { font-family: "Space Grotesk", sans-serif; margin: 0 0 8px; }
  .bz-success .id { font-family: "JetBrains Mono", monospace; font-size: 13px; color: var(--bolt); word-break: break-all; }
  .bz-success p { color: var(--muted); margin: 10px 0 0; }
  .bz-success .demo-note { font-size: 12px; color: #565B70; margin-top: 14px; }
  .bz-again {
    margin-top: 18px; background: none; border: 1px solid var(--line); color: var(--text);
    border-radius: var(--r); padding: 10px 18px; font: 500 14px "Inter", sans-serif; cursor: pointer;
  }
  .bz-again:hover { border-color: var(--violet); }

  @media (prefers-reduced-motion: reduce) { .bz-root * { transition: none !important; } }
`;

export default function TicketForm() {
  const [priorities, setPriorities] = useState(DEFAULT_PRIORITIES);
  const [form, setForm] = useState({
    name: "", email: "", company: "", subject: "", description: "", priority: "P4",
  });
  const [errors, setErrors] = useState(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null); // { ticket, demo }

  useEffect(() => {
    fetch(API_BASE + "/meta/priorities")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d && d.priorities) setPriorities(d.priorities); })
      .catch(() => {});
  }, []);

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  function validateLocally() {
    const out = [];
    if (!form.name.trim()) out.push("'name' is required.");
    if (!form.email.trim()) out.push("'email' is required.");
    else if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email))
      out.push("'email' must be a valid email address.");
    if (!form.subject.trim()) out.push("'subject' is required.");
    if (!form.description.trim()) out.push("'description' is required.");
    return out;
  }

  async function submit(e) {
    e.preventDefault();
    setErrors(null);
    setBusy(true);
    try {
      const res = await fetch(API_BASE + "/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setResult({ ticket: data.ticket, demo: false });
      } else {
        setErrors({
          message: data.error || "The ticket could not be submitted.",
          details: Array.isArray(data.details) ? data.details : null,
        });
      }
    } catch {
      // Preview fallback: no API behind this artifact, so simulate the
      // submission after running the same validation the server applies.
      const problems = validateLocally();
      if (problems.length) {
        setErrors({ message: "Ticket validation failed.", details: problems });
      } else {
        setResult({
          ticket: {
            id: crypto.randomUUID(),
            priority: form.priority,
            email: form.email,
          },
          demo: true,
        });
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bz-root">
      <style>{css}</style>
      <div className="bz-wrap">
        {result ? (
          <div className="bz-success" role="status">
            <h2>Ticket received</h2>
            <div className="id">{result.ticket.id}</div>
            <p>
              Priority {result.ticket.priority} —{" "}
              {result.ticket.priority === "P1"
                ? "our team triages critical incidents immediately."
                : "our team triages tickets in severity order."}{" "}
              A confirmation is on its way to {result.ticket.email}.
            </p>
            {result.demo && (
              <p className="demo-note">
                Preview mode: no API is attached to this artifact, so this
                submission was simulated. Deployed via Elmer, it writes to Supabase.
              </p>
            )}
            <button
              className="bz-again"
              onClick={() => {
                setResult(null);
                setForm({ ...form, subject: "", description: "" });
              }}
            >
              Submit another ticket
            </button>
          </div>
        ) : (
          <>
            <header className="bz-brand">
              <span className="bolt" aria-hidden="true">⚡</span>
              <span className="word">BLTZ</span>
              <span className="div">/</span>
              <span className="area">Support</span>
            </header>

            <p className="bz-eyebrow">Runtime support · severity triage</p>
            <h1 className="bz-h1">Report an issue.<br />We fix it, fast.</h1>
            <p className="bz-lede">
              Tell us what broke and how badly. Severity sets the response path,
              so pick the level that matches your operational impact.
            </p>

            <form className="bz-form" onSubmit={submit} noValidate>
              <div className="bz-row">
                <label>
                  <span className="bz-tag">Name</span>
                  <input className="bz-input" value={form.name} onChange={set("name")}
                         placeholder="Ada Lovelace" maxLength={200} />
                </label>
                <label>
                  <span className="bz-tag">Work email</span>
                  <input className="bz-input" type="email" value={form.email}
                         onChange={set("email")} placeholder="ada@company.com" />
                </label>
              </div>

              <label>
                <span className="bz-tag">Company <span style={{ opacity: 0.5 }}>(optional)</span></span>
                <input className="bz-input" value={form.company} onChange={set("company")}
                       placeholder="Analytical Engines, Inc." maxLength={200} />
              </label>

              <label>
                <span className="bz-tag">Subject</span>
                <input className="bz-input" value={form.subject} onChange={set("subject")}
                       placeholder="One line: what's broken?" maxLength={300} />
              </label>

              <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
                <span className="bz-tag" style={{ marginBottom: 10 }}>Severity</span>
                <div className="bz-sev-grid" role="radiogroup" aria-label="Severity">
                  {priorities.map((p) => (
                    <button
                      type="button"
                      key={p.code}
                      className="bz-sev"
                      style={{ "--sev": SEV_COLORS[p.code] }}
                      aria-pressed={form.priority === p.code}
                      onClick={() => setForm({ ...form, priority: p.code })}
                    >
                      <span className="head">
                        <span className="code">{p.code}</span>
                        <span className="name">{p.label}</span>
                      </span>
                      <span className="desc">{p.description}</span>
                    </button>
                  ))}
                </div>
              </fieldset>

              <label>
                <span className="bz-tag">What happened</span>
                <textarea className="bz-area" value={form.description} onChange={set("description")}
                          placeholder="Timeline, error messages, affected systems, and anything you've already tried."
                          maxLength={10000} />
              </label>

              {errors && (
                <div className="bz-error" role="alert">
                  {errors.message}
                  {errors.details && (
                    <ul>{errors.details.map((d, i) => <li key={i}>{d}</li>)}</ul>
                  )}
                </div>
              )}

              <div className="bz-actions">
                <button className="bz-submit" type="submit" disabled={busy}>
                  {busy ? "Submitting…" : "Submit ticket"}
                  <span className="arrow">→</span>
                </button>
                <span className="bz-hint">P1 tickets page the on-call engineer.</span>
              </div>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
