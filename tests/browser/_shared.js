/* Shared plumbing for the browser harnesses.
 *
 * jsdom runs each page's actual scripts. The CDN script URLs are served
 * from local node_modules (pinned in package.json to the same versions the
 * pages load in production); everything else — the page HTML, shared.jsx
 * fetched by Babel over XHR, API calls via fetch — hits the real Elmer
 * server on :3001.
 */
const fs = require("fs");
const path = require("path");
const { JSDOM, ResourceLoader, VirtualConsole } = require("jsdom");
const { CookieJar } = require("tough-cookie");

const BASE = process.env.ELMER_BASE || "http://127.0.0.1:3001";
const ADMIN_KEY = process.env.TICKETS_ADMIN_KEY || "test-admin-key";

const CDN_MAP = {
  "react/18.2.0/umd/react.production.min.js":
    "node_modules/react/umd/react.production.min.js",
  "react-dom/18.2.0/umd/react-dom.production.min.js":
    "node_modules/react-dom/umd/react-dom.production.min.js",
  "babel-standalone/7.23.5/babel.min.js":
    "node_modules/@babel/standalone/babel.min.js",
};

class Loader extends ResourceLoader {
  fetch(url, options) {
    for (const [needle, local] of Object.entries(CDN_MAP)) {
      if (url.includes(needle)) {
        return Promise.resolve(
          fs.readFileSync(path.join(__dirname, local)));
      }
    }
    return super.fetch(url, options);
  }
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function waitFor(fn, label, timeoutMs = 12000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const value = fn();
    if (value) return value;
    await sleep(100);
  }
  throw new Error("TIMEOUT waiting for: " + label);
}

/* React tracks inputs through the native value setter; go through it so
 * the synthetic onChange fires. */
function setValue(window, element, value) {
  const proto = element.tagName === "SELECT"
    ? window.HTMLSelectElement.prototype
    : element.tagName === "TEXTAREA"
      ? window.HTMLTextAreaElement.prototype
      : window.HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, "value").set.call(element, value);
  element.dispatchEvent(new window.Event("input", { bubbles: true }));
  element.dispatchEvent(new window.Event("change", { bubbles: true }));
}

async function openPage(pathname, options = {}) {
  /* options.injectKey: add X-Admin-Key to every fetch the page makes,
   * simulating a reverse proxy or header-injecting extension.
   * options.cookieJar: a tough-cookie CookieJar pre-populated before the
   * page's own scripts run — the way to test "a cookie from a previous
   * page load is already present," since jsdom gives each JSDOM instance
   * an independent cookie jar unless one is supplied explicitly.
   *
   * jsdomErrors collects jsdom's own error stream. Two uses: it silences
   * harmless noise (e.g. blocked font CDNs in sandboxes), and it is the
   * only way to observe navigation — jsdom does not implement page
   * navigation, so a click that sets window.location.href surfaces as a
   * "Not implemented: navigation" jsdomError rather than a URL change. */
  const errors = [];
  const jsdomErrors = [];
  const virtualConsole = new VirtualConsole();
  virtualConsole.on("jsdomError", (e) =>
    jsdomErrors.push(String((e && e.message) || e)));
  const dom = await JSDOM.fromURL(BASE + pathname, {
    runScripts: "dangerously",
    resources: new Loader(),
    virtualConsole,
    cookieJar: options.cookieJar,
    pretendToBeVisual: true,
    beforeParse(window) {
      window.fetch = (input, init = {}) => {
        if (options.injectKey) {
          init = { ...init,
                   headers: { ...(init.headers || {}),
                              "X-Admin-Key": ADMIN_KEY } };
        }
        return fetch(new URL(String(input), BASE).href, init);
      };
      window.addEventListener("error", (e) =>
        errors.push(String(e.message || e.error)));
    },
  });
  return { dom, errors, jsdomErrors };
}

/* Drive the management key gate on any /www/managetickets page. */
async function unlock(window) {
  const doc = window.document;
  const input = await waitFor(
    () => doc.querySelector('.gate input[type="password"]'), "key gate");
  setValue(window, input, ADMIN_KEY);
  await sleep(120);
  [...doc.querySelectorAll("button")]
    .find((b) => /unlock/i.test(b.textContent)).click();
}

function api(pathname, options = {}) {
  return fetch(BASE + pathname, {
    ...options,
    headers: { "Content-Type": "application/json",
               "X-Admin-Key": ADMIN_KEY, ...(options.headers || {}) },
  }).then((r) => r.json());
}

module.exports = { BASE, ADMIN_KEY, Loader, CookieJar, sleep, waitFor, setValue,
                   openPage, unlock, api };
