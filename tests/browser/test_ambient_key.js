/* When the environment injects a valid X-Admin-Key on every request (a
 * reverse proxy or header extension), the "Management key required"
 * prompt must never appear — the page verifies silently and loads data
 * directly. Also asserts the inverse: without injection, the gate shows. */
const { openPage, waitFor, sleep } = require("./_shared");

(async () => {
  // -- with ambient key: no gate, data loads --
  {
    const { dom, errors } = await openPage("/www/managetickets",
                                           { injectKey: true });
    const doc = dom.window.document;
    await waitFor(() => doc.querySelector(".tickets-table"), "ticket table");
    const gateAppeared = !!doc.querySelector(".gate");
    const rows = doc.querySelectorAll(".tickets-table tbody tr").length;
    console.log("ambient: gate shown:", gateAppeared, "| rows:", rows,
      "| errors:", errors.length ? errors.join("; ") : "none");
    dom.window.close();
    if (gateAppeared || rows < 1 || errors.length) {
      console.log("RESULT: FAIL");
      process.exit(1);
    }
  }

  // -- without ambient key: the gate still guards the page --
  {
    const { dom } = await openPage("/www/managetickets");
    const doc = dom.window.document;
    await waitFor(() => doc.querySelector(".gate"), "key gate");
    await sleep(200);
    const tableLeaked = !!doc.querySelector(".tickets-table");
    console.log("no key: gate shown: true | table leaked:", tableLeaked);
    dom.window.close();
    if (tableLeaked) { console.log("RESULT: FAIL"); process.exit(1); }
  }

  console.log("RESULT: PASS");
  process.exit(0);
})().catch((e) => { console.error("HARNESS ERROR:", e.message); process.exit(2); });
