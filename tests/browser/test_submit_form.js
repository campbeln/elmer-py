/* Public submission form: renders, severity cards work, ticket persists. */
const { openPage, waitFor, setValue, sleep, api } = require("./_shared");

(async () => {
  const { dom, errors } = await openPage("/www/tickets.html");
  const w = dom.window, doc = w.document;
  await waitFor(() => doc.querySelector("form"), "form renders");

  const inputs = doc.querySelectorAll("input");
  setValue(w, inputs[0], "Harness User");
  setValue(w, inputs[1], "harness@example.com");
  setValue(w, inputs[3], "Harness-submitted ticket");
  setValue(w, doc.querySelector("textarea"), "Submitted by test_submit_form.js");
  [...doc.querySelectorAll(".sev")]
    .find((b) => b.textContent.includes("P2")).click();
  await sleep(120);
  [...doc.querySelectorAll("button")]
    .find((b) => /submit ticket/i.test(b.textContent)).click();

  await waitFor(() => doc.querySelector(".success"), "success state");
  const id = doc.querySelector(".success .id").textContent.trim();
  const check = await api("/tickets/" + id);
  const pass = errors.length === 0 && check.ticket
    && check.ticket.priority === "P2";
  console.log("script errors:", errors.length ? errors.join("; ") : "none");
  console.log("brand:", doc.querySelector(".brand") === null
    ? "(success state)" : doc.querySelector(".brand .word").textContent);
  console.log("persisted priority:", check.ticket && check.ticket.priority);
  console.log("RESULT:", pass ? "PASS" : "FAIL");
  dom.window.close();
  process.exit(pass ? 0 : 1);
})().catch((e) => { console.error("HARNESS ERROR:", e.message); process.exit(2); });
