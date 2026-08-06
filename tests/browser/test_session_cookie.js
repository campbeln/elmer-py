/* Session-cookie management key: typed once, then remembered for the
 * rest of the browser session without re-prompting on later page loads. */
const { openPage, unlock, waitFor, sleep, CookieJar } = require("./_shared");

(async () => {
  let ok = true;
  const fail = (label) => { console.log("FAIL:", label); ok = false; };

  // -- part 1: unlocking manually sets a cookie --
  const jar = new CookieJar();
  {
    const { dom } = await openPage("/www/managetickets", { cookieJar: jar });
    const doc = dom.window.document;
    await unlock(dom.window);
    await waitFor(() => doc.querySelector(".tickets-table"), "ticket table");

    const cookies = await jar.getCookies("http://127.0.0.1:3001/www/managetickets/");
    const found = cookies.find((c) => c.key === "elmer_admin_key");
    console.log("cookie set after manual unlock:", !!found);
    if (!found) fail("cookie not set after unlock");
    else if (decodeURIComponent(found.value) !== "test-admin-key") {
      fail("cookie value does not match the entered key");
    }
    // Session cookie: no expiry, cleared when the browser closes.
    console.log("cookie has no Expires/Max-Age (session cookie):",
      found && found.expires === "Infinity");
    if (found && found.expires !== "Infinity") fail("cookie should be a session cookie");
    dom.window.close();
  }

  // -- part 2: a fresh "page load" sharing that same cookie jar skips
  //    the prompt entirely and goes straight to data --
  {
    const { dom, errors } = await openPage("/www/managetickets", { cookieJar: jar });
    const doc = dom.window.document;
    await waitFor(() => doc.querySelector(".tickets-table") || doc.querySelector(".gate"),
      "queue page settles");
    const gateShown = !!doc.querySelector(".gate");
    const rows = doc.querySelectorAll(".tickets-table tbody tr").length;
    console.log("second page load — gate shown:", gateShown, "| rows loaded:", rows);
    if (gateShown) fail("cookie should have skipped the prompt");
    if (rows < 1) fail("data should have loaded without re-prompting");
    if (errors.length) fail("script errors: " + errors.join("; "));
    dom.window.close();
  }

  // -- part 3: "Forget key" clears the cookie --
  {
    const { dom } = await openPage("/www/managetickets", { cookieJar: jar });
    const doc = dom.window.document;
    await waitFor(() => doc.querySelector(".tickets-table"), "ticket table (cookie still valid)");
    const forgetBtn = [...doc.querySelectorAll("button")]
      .find((b) => /forget key/i.test(b.textContent));
    console.log("forget-key control present:", !!forgetBtn);
    if (!forgetBtn) fail("forget-key control missing");
    else {
      forgetBtn.click();
      await sleep(100);
      const remaining = await jar.getCookies("http://127.0.0.1:3001/www/managetickets/");
      const stillThere = remaining.some((c) => c.key === "elmer_admin_key");
      console.log("cookie cleared after Forget key:", !stillThere);
      if (stillThere) fail("cookie should be cleared after Forget key");
    }
    dom.window.close();
  }

  console.log("RESULT:", ok ? "PASS" : "FAIL");
  process.exit(ok ? 0 : 1);
})().catch((e) => { console.error("HARNESS ERROR:", e.message); process.exit(2); });
