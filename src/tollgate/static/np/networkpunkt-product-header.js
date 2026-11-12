/* Shared five-product host adapter. No discovery, launch commands or peer probing. */
import {mountAppBar} from "./networkpunkt-appbar.js";
import {APP_CATALOG} from "./networkpunkt-appbar-catalog.js";

const hosts = new WeakMap();

export function mountProductHeader(element, {selfId, locale = "de", selfRoute = "/", readSelf,
  openTarget, targets = {}, navigate = url => element.ownerDocument.defaultView.location.assign(url)} = {}) {
  if (!APP_CATALOG.some(app => app.id === selfId)) throw new TypeError("Unknown host product");
  hosts.get(element)?.destroy();
  const doc = element.ownerDocument, win = doc.defaultView;
  let language = locale === "en" ? "en" : "de", stopped = false, active = null, sequence = 0;
  const epoch = `surface-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const expected = {appId:selfId, connectionRef:"same-origin-host", peerRef:selfId, peerEpoch:epoch};
  const dialog = doc.createElement("dialog"); dialog.className = "np-appbar-dialog";
  let returnFocus = null;
  dialog.addEventListener("keydown", event => event.stopPropagation());
  dialog.addEventListener("close", () => {
    // Native modal close already restores focus synchronously. Its later close
    // event must not steal focus back after the user has pressed Tab again.
    if (dialog.open) return;
    const target = returnFocus; returnFocus = null;
    const active = doc.activeElement;
    if (target?.isConnected && (active === doc.body || active === dialog || dialog.contains(active))) target.focus();
  });
  doc.body.append(dialog);
  function missing(appId) {
    returnFocus = doc.activeElement;
    const app = APP_CATALOG.find(entry => entry.id === appId);
    const title = doc.createElement("h2"); title.id = `${epoch}-title`; title.textContent = app.name[language];
    const explanation = doc.createElement("p");
    explanation.textContent = language === "de"
      ? "Kein Produktziel eingerichtet. Öffne die eigenständige App über ihren vorhandenen Starter. Verbindung und Version sind hier noch nicht bestätigt."
      : "No product target configured. Open the independent app using its existing launcher. Connection and version have not been confirmed here.";
    const close = doc.createElement("button"); close.type = "button"; close.textContent = language === "de" ? "Schließen" : "Close";
    close.addEventListener("click", () => dialog.close());
    dialog.replaceChildren(title, explanation, close); dialog.setAttribute("aria-labelledby", title.id);
    if (!dialog.open) dialog.showModal();
  }
  function route(value, own = false) {
    if (typeof value !== "string" || value.length > 2048) return null;
    try {
      const url = new URL(value, win.location.href);
      if (own && value.startsWith("/") && !value.startsWith("//")) return url.href;
      return ["http:", "https:"].includes(url.protocol) && !url.username && !url.password ? url.href : null;
    } catch { return null; }
  }
  const bar = mountAppBar(element, {selfId, locale:language, peers:{[selfId]:expected},
    // Native broker: 30 s plus 1 s for host dispatch/receipt delivery. Status TTLs stay separate.
    openTimeoutMs:typeof openTarget === "function" ? 31000 : 2000,
    onOpen:async ({appId, actionId}) => {
      if (typeof openTarget === "function") {
        // Only a catalog ID crosses the host boundary; never a URL, argv or PID.
        const outcome = await openTarget(appId);
        return {actionId, outcome:["opened", "focused", "missing", "failed", "uncertain"].includes(outcome) ? outcome : "uncertain"};
      }
      const url = route(appId === selfId ? selfRoute : targets[appId], appId === selfId);
      if (!url) { missing(appId); return {actionId, outcome:"missing"}; }
      if (appId === selfId && new URL(url).pathname === win.location.pathname) {
        const main = doc.querySelector("main, [role=main]") || doc.body;
        main.setAttribute("tabindex", "-1"); main.focus();
        return {actionId, outcome:"focused"};
      }
      await navigate(url, appId);
      return {actionId, outcome:"opened"};
    }});
  async function refresh() {
    if (stopped || doc.hidden || active || typeof readSelf !== "function") return;
    const ticket = bar.begin(selfId), controller = new AbortController(); active = controller;
    const deadline = win.setTimeout(() => { controller.abort(); if (active === controller) active = null; bar.fail(selfId, ticket, "unknown"); }, 1900);
    try {
      const value = await readSelf({signal:controller.signal});
      if (!stopped && !controller.signal.aborted) bar.receive(selfId, ticket, {
        v:1, ...expected, seq:++sequence, state:value.state, ttlMs:10000,
        ...(value.version ? {version:value.version} : {})
      });
    } catch (error) {
      if (!stopped && !controller.signal.aborted) bar.fail(selfId, ticket, error?.name === "TypeError" ? "unknown" : "error");
    } finally {
      win.clearTimeout(deadline);
      if (active === controller) active = null;
    }
  }
  const visibility = () => { active?.abort(); active = null; if (!doc.hidden) refresh(); };
  doc.addEventListener("visibilitychange", visibility);
  const interval = win.setInterval(refresh, 4000); refresh();
  const languageObserver = new win.MutationObserver(() => {
    language = doc.documentElement.lang === "en" ? "en" : "de";
    bar.setLocale(language);
    if (dialog.open) dialog.close();
  });
  languageObserver.observe(doc.documentElement, {attributes:true, attributeFilter:["lang"]});
  const api = Object.freeze({bar, refresh, setLocale(value) { language = value === "en" ? "en" : "de"; bar.setLocale(language); if (dialog.open) dialog.close(); },
    destroy() { if (stopped) return; stopped = true; hosts.delete(element); active?.abort(); win.clearInterval(interval); languageObserver.disconnect(); doc.removeEventListener("visibilitychange", visibility); bar.destroy(); dialog.remove(); }});
  hosts.set(element, api); return api;
}
