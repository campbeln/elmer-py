/* View page (deep-linked lookup) and status page (lifecycle update),
 * verified end to end including persistence through Elmer to the DB. */
const { openPage, unlock, waitFor, setValue, sleep, api } = require("./_shared");

(async () => {
  const list = await api("/tickets/");
  const ticket = list.tickets.find((t) => t.priority === "P1");
  if (!ticket) throw new Error("stub DB has no P1 ticket");

  // -- view page --
  {
    const { dom, errors } = await openPage(
      "/www/managetickets/view/?id=" + ticket.id);
    const doc = dom.window.document;
    await unlock(dom.window);
    await waitFor(() => doc.querySelector(".detail"), "detail card");
    const ok = errors.length === 0
      && doc.body.textContent.includes(ticket.subject)
      && doc.body.textContent.includes(ticket.description.slice(0, 20));
    console.log("view page:", ok ? "PASS" : "FAIL",
      errors.length ? "(" + errors.join("; ") + ")" : "");
    dom.window.close();
    if (!ok) process.exit(1);
  }

  // -- status page --
  {
    const { dom, errors } = await openPage(
      "/www/managetickets/status/?id=" + ticket.id);
    const w = dom.window, doc = w.document;
    await unlock(w);
    await waitFor(() => doc.body.textContent.includes(ticket.subject),
      "context card");
    setValue(w, doc.querySelector("select"), "in_progress");
    setValue(w, doc.querySelector("textarea"),
             "Harness note: engineer assigned.");
    await sleep(120);
    [...doc.querySelectorAll("button")]
      .find((b) => /update status/i.test(b.textContent)).click();
    await waitFor(() => doc.querySelector(".success-line"), "success line");
    console.log("status page:", errors.length === 0 ? "PASS" : "FAIL");
    dom.window.close();
    if (errors.length) process.exit(1);
  }

  // -- the message now shows in the view page's history --
  {
    const { dom, errors } = await openPage(
      "/www/managetickets/view/?id=" + ticket.id);
    const doc = dom.window.document;
    await unlock(dom.window);
    await waitFor(() => doc.querySelector(".update-entry"), "history entry");
    const shows = doc.body.textContent
      .includes("Harness note: engineer assigned.");
    console.log("history on view page:",
      shows && errors.length === 0 ? "PASS" : "FAIL");
    dom.window.close();
    if (!shows || errors.length) process.exit(1);
  }

  const after = await api("/tickets/" + ticket.id);
  const pass = after.ticket.status === "in_progress";
  console.log("persisted status:", after.ticket.status);
  console.log("RESULT:", pass ? "PASS" : "FAIL");
  process.exit(pass ? 0 : 1);
})().catch((e) => { console.error("HARNESS ERROR:", e.message); process.exit(2); });
