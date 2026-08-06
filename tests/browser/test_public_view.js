/* Public status page /www/view.html?id= — no key gate, status messages in
 * reverse date order, and NO reporter PII anywhere in the page. */
const { openPage, waitFor, sleep, api } = require("./_shared");

(async () => {
  const list = await api("/tickets/");
  const ticket = list.tickets.find((t) => t.priority === "P1");

  // Post two dated status messages so ordering is observable.
  await api("/tickets/" + ticket.id + "/status", {
    method: "POST",
    body: JSON.stringify({ status: "acknowledged", message: "First note." }),
  });
  await api("/tickets/" + ticket.id + "/status", {
    method: "POST",
    body: JSON.stringify({ status: "in_progress", message: "Second note." }),
  });

  const { dom, errors } = await openPage("/www/view.html?id=" + ticket.id);
  const doc = dom.window.document;
  await waitFor(() => doc.querySelectorAll(".update-entry").length >= 2,
    "status history");

  const gateAppeared = !!doc.querySelector(".gate");
  const text = doc.body.textContent;
  const first = doc.querySelectorAll(".update-entry")[0].textContent;
  const newestFirst = first.includes("Second note.");
  const leaksEmail = text.includes("ada-private@example.com");
  const leaksDescription = text.includes("Everything is down");

  console.log("gate shown:", gateAppeared);
  console.log("newest message first:", newestFirst);
  console.log("subject shown:", text.includes(ticket.subject));
  console.log("reporter email leaked:", leaksEmail);
  console.log("description leaked:", leaksDescription);
  console.log("script errors:", errors.length ? errors.join("; ") : "none");

  const pass = !gateAppeared && newestFirst && !leaksEmail
    && !leaksDescription && errors.length === 0;
  console.log("RESULT:", pass ? "PASS" : "FAIL");
  dom.window.close();
  process.exit(pass ? 0 : 1);
})().catch((e) => { console.error("HARNESS ERROR:", e.message); process.exit(2); });
