/* Static checks for responsive/layout requirements that jsdom cannot
 * verify by rendering (it has no layout engine, so CSS wrapping and
 * media-query evaluation aren't observable there). These instead assert
 * the actual CSS/markup rules exist — a source-level guard against the
 * behavior regressing, complementing (not replacing) the script-
 * execution checks the other harnesses do. */
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..", "..");
const read = (rel) => fs.readFileSync(path.join(ROOT, rel), "utf8");

(async () => {
  let ok = true;
  const fail = (label) => { console.log("FAIL:", label); ok = false; };
  const check = (label, cond) => { console.log((cond ? "ok  " : "FAIL") + " " + label); if (!cond) ok = false; };

  const sharedCss = read("app/www/managetickets/shared.css");
  const ticketsHtml = read("app/www/tickets.html");
  const viewHtml = read("app/www/view.html");
  const queueHtml = read("app/www/managetickets/index.html");

  // -- Status column must not word-wrap --
  check("status-badge has white-space:nowrap",
    /\.status-badge\s*{[^}]*white-space:\s*nowrap/.test(sharedCss));
  check("queue table has a dedicated col-status nowrap rule",
    /col-status[^{]*{[^}]*white-space:\s*nowrap/.test(sharedCss));
  check("queue Status header carries the col-status class",
    /SortableTh label="Status"[^>]*className="col-status"/.test(queueHtml));

  // -- Responsive: viewport meta tag on every /www page --
  for (const [name, html] of [["tickets.html", ticketsHtml], ["view.html", viewHtml],
                              ["managetickets/index.html", queueHtml]]) {
    check(name + " has a responsive viewport meta tag",
      /<meta name="viewport" content="width=device-width, initial-scale=1"/.test(html));
  }

  // -- Responsive: mobile media queries present where expected --
  check("shared.css has a max-width:640px mobile block",
    /@media \(max-width:\s*640px\)/.test(sharedCss));
  check("shared.css .filters-single has its own mobile breakpoint",
    /\.filters-single\s*{[^}]*}\s*\n@media \(max-width:\s*480px\)\s*{\s*\.filters-single/.test(sharedCss));
  check("tickets.html has its own mobile media query block",
    /@media \(max-width:\s*640px\)/.test(ticketsHtml));

  // -- Regression guard: the inline gridTemplateColumns override that
  //    defeats a later media query (inline styles always win regardless
  //    of viewport) must not reappear on the single-input lookup forms. --
  for (const [name, html] of [
    ["view.html", viewHtml],
    ["managetickets/view/index.html", read("app/www/managetickets/view/index.html")],
  ]) {
    check(name + " does not use the inline gridTemplateColumns override anti-pattern",
      !/className="filters"\s+style=\{\{\s*gridTemplateColumns/.test(html));
  }

  // -- table-scroll wrapper present for the queue table on narrow viewports --
  check("queue table is wrapped for horizontal scroll on mobile",
    /<div className="table-scroll">/.test(queueHtml));
  check("shared.css defines .table-scroll", /\.table-scroll\s*{/.test(sharedCss));

  // -- reporter note must be a genuinely distinct, bright color, not
  //    reused from any status badge (previously shared the same violet
  //    as the "in_progress" status, undermining "stands out") --
  const reporterColorMatch = sharedCss.match(/--reporter:\s*(#[0-9a-fA-F]{3,6})/);
  check("shared.css defines a dedicated --reporter color variable", !!reporterColorMatch);
  if (reporterColorMatch) {
    const reporterColor = reporterColorMatch[1].toLowerCase();
    const statusColors = [...sharedCss.matchAll(
      /\.status-badge\[data-s="[a-z_]+"\]\s*{[^}]*color:\s*(?:var\(([a-z0-9-]+)\)|(#[0-9a-fA-F]{3,6}))/g,
    )].map((m) => {
      if (m[2]) return m[2].toLowerCase();
      const varMatch = sharedCss.match(new RegExp(m[1] + ":\\s*(#[0-9a-fA-F]{3,6})"));
      return varMatch ? varMatch[1].toLowerCase() : null;
    }).filter(Boolean);
    check("--reporter color is not reused by any status badge",
      !statusColors.includes(reporterColor));
    check("author-tag actually uses the --reporter variable",
      /\.author-tag\s*{[^}]*var\(--reporter\)/.test(sharedCss));
  }

  console.log("RESULT:", ok ? "PASS" : "FAIL");
  process.exit(ok ? 0 : 1);
})();
