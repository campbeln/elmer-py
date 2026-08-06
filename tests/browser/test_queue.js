/* Queue page: renders without script errors, gate unlocks, data loads.
 *
 * This test exists because of a real regression: babel-standalone runs
 * every text/babel script in the GLOBAL scope, so duplicate top-level
 * const declarations across shared.jsx and the page scripts threw
 * "Identifier 'useEffect' has already been declared" and the page
 * rendered nothing. Only script-executing tests catch that class of bug.
 */
const { openPage, unlock, waitFor } = require("./_shared");

(async () => {
  const { dom, errors } = await openPage("/www/managetickets");
  const doc = dom.window.document;

  await unlock(dom.window);
  await waitFor(() => doc.querySelector(".tickets-table"), "ticket table");

  const rows = doc.querySelectorAll(".tickets-table tbody tr");
  console.log("script errors:", errors.length ? errors.join("; ") : "none");
  console.log("queue rows:", rows.length);
  console.log("brand:", doc.querySelector(".brand .word").textContent);

  const pass = errors.length === 0 && rows.length >= 2;
  console.log("RESULT:", pass ? "PASS" : "FAIL");
  dom.window.close();
  process.exit(pass ? 0 : 1);
})().catch((e) => { console.error("HARNESS ERROR:", e.message); process.exit(2); });
