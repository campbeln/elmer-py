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

  // The success state must hand the reporter their public tracking link.
  const link = doc.querySelector(".success .track-link");
  const expectedPath = "/www/view.html?id=" + id;
  const linkOk = !!link
    && link.getAttribute("href").endsWith(expectedPath)
    && link.textContent.includes(expectedPath);
  console.log("tracking link shown:", linkOk,
    link ? "(" + link.getAttribute("href") + ")" : "(missing)");

  // …and that link must actually work, key-free.
  const publicRes = await fetch(
    "http://127.0.0.1:3001/tickets/" + id + "/public");
  console.log("tracking target resolves:", publicRes.status === 200);

  const pass = errors.length === 0 && check.ticket
    && check.ticket.priority === "P2" && linkOk && publicRes.status === 200;
  console.log("script errors:", errors.length ? errors.join("; ") : "none");
  console.log("persisted priority:", check.ticket && check.ticket.priority);
  console.log("RESULT:", pass ? "PASS" : "FAIL");
  dom.window.close();
  process.exit(pass ? 0 : 1);
})().catch((e) => { console.error("HARNESS ERROR:", e.message); process.exit(2); });
