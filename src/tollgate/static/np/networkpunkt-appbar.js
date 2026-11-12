/* NetzwerkPunkt appbar 1.2.1 — portable DOM renderer, no transport or host launch. */
import { APPBAR_VERSION, APP_ORDER, createElapsed, createPeerState } from "./networkpunkt-appbar-state.js";
import { APP_CATALOG } from "./networkpunkt-appbar-catalog.js";
export { APPBAR_VERSION };
const mounts = new WeakMap();
let mounted = 0;
const COPY = {
  de: { bar: "Verbundene Apps", open: "Öffnen oder fokussieren", confirmed: "Verbunden", busy: "Beschäftigt", versionUnknown: "Version unbekannt", version: "Version", self: "Diese Oberfläche",
    connecting: "Verbindet …", disconnected: "Nicht verbunden", unknown: "Status unbekannt",
    error: "Verbindungsfehler · Verbindung prüfen", unlocked: "Tresor entsperrt", locked: "Tresor gesperrt",
    vaultUnknown: "Tresorstatus unbekannt", opening: "App wird geöffnet …",
    opened: "App geöffnet, Verbindung fehlt", focused: "App fokussiert, Verbindung unbestätigt",
    failed: "Öffnen fehlgeschlagen · Ziel prüfen und erneut versuchen",
    missing: "Öffnen nicht verfügbar · App-Ziel einrichten",
    uncertain: "Öffnung unklar · App prüfen, nicht erneut starten", unconfigured: "Statusanzeige nicht eingerichtet" },
  en: { bar: "Connected apps", open: "Open or focus", confirmed: "Connected", busy: "Busy", versionUnknown: "Version unknown", version: "Version", self: "This interface",
    connecting: "Connecting …", disconnected: "Not connected", unknown: "Status unknown",
    error: "Connection error · Check connection", unlocked: "Vault unlocked", locked: "Vault locked",
    vaultUnknown: "Vault status unknown", opening: "Opening app …",
    opened: "App opened, connection missing", focused: "App focused, connection unconfirmed",
    failed: "Opening failed · Check target and retry", missing: "Opening unavailable · Configure app target",
    uncertain: "Opening outcome unknown · Check app, do not restart", unconfigured: "Status display not configured" },
};
function catalogEntries(catalog) {
  if (!Array.isArray(catalog) || catalog.length > APP_ORDER.length) throw new TypeError("Invalid app catalog");
  const seen = new Set();
  return catalog.map(entry => {
    if (!APP_ORDER.includes(entry.id) || seen.has(entry.id) || !/^[a-z0-9-]+\.png$/.test(entry.icon)
      || (entry.color !== null && !/^#[0-9a-f]{6}$/i.test(entry.color)) || ![entry.name?.de, entry.name?.en].every(x => typeof x === "string" && x.length > 0 && x.length <= 80)
      || !Array.isArray(entry.routes) || !entry.routes.every(x => x === "host-adapter")) throw new TypeError("Invalid app catalog entry");
    seen.add(entry.id);
    if (entry.art && (!Array.isArray(entry.art) || entry.art.length !== 4 || !entry.art.every(x => Number.isFinite(x) && x >= 0 && x <= 256) || entry.art[2] < 1 || entry.art[3] < 1 || entry.art[0] + entry.art[2] > 256 || entry.art[1] + entry.art[3] > 256)) throw new TypeError("Invalid original asset viewport");
    return { art:entry.art, id: entry.id, name: { de: entry.name.de, en: entry.name.en }, icon: entry.icon, color: entry.color };
  }).sort((a, b) => APP_ORDER.indexOf(a.id) - APP_ORDER.indexOf(b.id));
}

export function mountAppBar(element, { catalog = APP_CATALOG, peers = {}, colors = {}, locale = "de", onOpen, selfId = null,
  clock = () => performance.now(), wallClock = () => Date.now() } = {}) {
  mounts.get(element)?.destroy();
  const doc = element.ownerDocument, win = doc.defaultView, mountId = ++mounted;
  const entries = catalogEntries(catalog), items = new Map();
  let destroyed = false, language = locale === "en" ? "en" : "de", lastAnnouncement = "";
  const root = doc.createElement("nav"); root.className = "np-appbar";
  root.dataset.version = APPBAR_VERSION;
  const live = doc.createElement("span"); live.className = "np-appbar-sr";
  live.setAttribute("role", "status"); live.setAttribute("aria-live", "polite"); live.setAttribute("aria-atomic", "true");
  for (const entry of entries) {
    const configured = colors[entry.id];
    if (configured && (!/^#[0-9a-f]{6}$/i.test(configured.value) || typeof configured.sourceRef !== "string"
      || configured.sourceRef.length < 1 || configured.sourceRef.length > 256)) throw new TypeError("Invalid configured tool color");
    const color = configured?.value ?? entry.color;
    if (peers[entry.id] && peers[entry.id].appId !== entry.id) throw new TypeError("Peer app mismatch");
    const peer = peers[entry.id] ? createPeerState(peers[entry.id], { clock, wallClock }) : null;
    const wrapper = doc.createElement("span"); wrapper.className = "np-appbar-item";
    const button = doc.createElement("button"); button.type = "button"; button.className = "np-appbar-button";
    button.dataset.appId = entry.id;
    const ring = doc.createElement("span"); ring.className = "np-appbar-ring";
    if (color) ring.style.setProperty("--np-appbar-color", color);
    const image = doc.createElement("img"); image.alt = ""; image.width = image.height = 24;
    image.src = new URL(entry.icon, import.meta.url).href;
    const art = doc.createElement("span"); art.className = "np-appbar-art";
    if (entry.art) {
      const [x, y, width, height] = entry.art, scale = 32 / Math.max(width, height);
      art.style.width = `${width * scale}px`; art.style.height = `${height * scale}px`;
      image.style.width = image.style.height = `${256 * scale}px`;
      image.style.left = `${-x * scale}px`; image.style.top = `${-y * scale}px`;
    }
    art.append(image); ring.append(art);
    const version = doc.createElement("span"); version.className = "np-appbar-version"; version.setAttribute("aria-hidden", "true");
    button.append(ring, version);
    const tooltip = doc.createElement("span"); tooltip.className = "np-appbar-tooltip";
    tooltip.id = `np-appbar-tip-${mountId}-${entry.id}`; tooltip.setAttribute("role", "tooltip"); tooltip.hidden = true;
    button.setAttribute("aria-describedby", tooltip.id);
    const show = () => { tooltip.hidden = false; positionTooltip(tooltip); };
    const hide = () => { tooltip.hidden = true; };
    button.addEventListener("focus", show); button.addEventListener("blur", hide);
    button.addEventListener("mouseenter", show); wrapper.addEventListener("mouseleave", hide);
    button.addEventListener("keydown", event => { if (event.key === "Escape") { hide(); event.preventDefault(); } });
    const item = { entry, peer, color, wrapper, button, ring, tooltip, version, open: null, lastOpen: null, abort: null, serial: 0 };
    button.addEventListener("click", () => open(item));
    wrapper.append(button, tooltip); root.append(wrapper); items.set(entry.id, item);
  }
  root.append(live); element.append(root);
  function positionTooltip(tooltip) {
    if (tooltip.hidden) return;
    tooltip.style.left = "0px";
    const bounds = tooltip.getBoundingClientRect(), width = doc.documentElement.clientWidth;
    const left = Math.max(4, Math.min(bounds.left, width - bounds.width - 4));
    tooltip.style.left = `${left - bounds.left}px`;
  }
  function paint() {
    if (destroyed) return;
    const text = COPY[language], announcements = [];
    root.setAttribute("aria-label", text.bar); root.lang = language;
    for (const item of items.values()) {
      const observed = item.peer?.snapshot();
      const state = item.color && observed ? observed : { state: "unknown", vault: "unknown", pulse: false };
      const cooldown = item.lastOpen?.();
      if (cooldown !== undefined && !Number.isFinite(cooldown)) {
        if (item.open) item.open.state = "uncertain";
        item.abort?.abort();
      } else if (cooldown >= 600) item.lastOpen = null;
      if (item.open?.state === "opening" && item.open.age() >= 2000) {
        item.open.state = "uncertain"; item.abort?.abort();
      }
      item.ring.dataset.connected = String(["confirmed", "busy"].includes(state.state));
      item.ring.dataset.state = state.state;
      item.button.dataset.state = state.state;
      item.version.textContent = state.version ? `v${state.version}` : "v?";
      item.ring.dataset.pulse = String(state.pulse);
      const vault = item.entry.id === "4allpass" && state.state === "confirmed"
        ? ` · ${text[state.vault === "unknown" ? "vaultUnknown" : state.vault]}` : "";
      let status = text[state.state] + vault;
      if (item.entry.id === selfId) status += ` · ${text.self}`;
      status += ` · ${state.version ? `${text.version} ${state.version}` : text.versionUnknown}`;
      if (!item.color) status += ` · ${text.unconfigured}`;
      if (typeof onOpen !== "function") status += ` · ${text.missing}`;
      else if (item.open && !(["opened", "focused"].includes(item.open.state) && state.state === "confirmed")) status += ` · ${text[item.open.state]}`;
      const label = `${item.entry.name[language]} · ${status}`;
      item.tooltip.textContent = label;
      positionTooltip(item.tooltip);
      item.button.setAttribute("aria-label", `${label} · ${text.open}`);
      item.button.setAttribute("aria-disabled", String(typeof onOpen !== "function" || ["opening", "uncertain"].includes(item.open?.state)));
      item.button.dataset.error = String(state.state === "error" || ["failed", "uncertain"].includes(item.open?.state));
      announcements.push(label);
    }
    const announcement = announcements.join("; ");
    if (announcement !== lastAnnouncement) { live.textContent = announcement; lastAnnouncement = announcement; }
  }
  async function open(item) {
    paint();
    if (destroyed || typeof onOpen !== "function" || ["opening", "uncertain"].includes(item.open?.state) || item.lastOpen) return;
    item.lastOpen = createElapsed(clock, wallClock); item.abort = new AbortController();
    const actionId = `np-appbar-${Date.now()}-${mountId}-${++item.serial}`;
    item.open = { state: "opening", age: item.lastOpen, actionId }; paint();
    try {
      const result = await onOpen({ appId: item.entry.id, actionId, signal: item.abort.signal });
      paint(); // enforce the deadline before accepting a late completion
      if (destroyed || item.open?.actionId !== actionId || item.open.state !== "opening") return;
      item.open.state = result?.actionId === actionId && ["opened", "focused", "failed", "missing"].includes(result.outcome) ? result.outcome : "uncertain";
    } catch { if (!destroyed && item.open?.actionId === actionId && item.open.state === "opening") item.open.state = "uncertain"; }
    paint();
  }
  function invalidate() { for (const item of items.values()) item.peer?.invalidate(); paint(); }
  doc.addEventListener("visibilitychange", invalidate); win.addEventListener("pagehide", invalidate);
  win.addEventListener("resize", paint);
  const timer = win.setInterval(paint, 250);
  const api = Object.freeze({
    begin(appId) { if (destroyed) return null; const ticket = items.get(appId)?.peer?.begin() ?? null; paint(); return ticket; },
    receive(appId, ticket, observation) { if (destroyed) return false; const accepted = items.get(appId)?.peer?.receive(ticket, observation) ?? false; paint(); return accepted; },
    fail(appId, ticket, state) { if (destroyed) return false; const accepted = items.get(appId)?.peer?.fail(ticket, state) ?? false; paint(); return accepted; },
    reset(appId, expected) { if (destroyed) return; if (expected.appId !== appId) throw new TypeError("Peer app mismatch");
      const item = items.get(appId); if (item) { if (item.peer) item.peer.reset(expected); else item.peer = createPeerState(expected, {clock,wallClock}); } paint(); },
    // Only after the host checked an unknown opening outcome; never automatic retry.
    clearOpen(appId) { const item = items.get(appId); if (item) {
      item.abort?.abort();
      // Invalid time cannot satisfy a minimum wait: host recovery starts it anew.
      if (item.lastOpen && !Number.isFinite(item.lastOpen())) item.lastOpen = createElapsed(clock, wallClock);
      item.open = null; paint();
    } },
    setLocale(value) { language = value === "en" ? "en" : "de"; paint(); },
    refresh: paint,
    destroy() { if (destroyed) return; destroyed = true; win.clearInterval(timer); doc.removeEventListener("visibilitychange", invalidate);
      win.removeEventListener("resize", paint);
      win.removeEventListener("pagehide", invalidate); for (const item of items.values()) { item.peer?.invalidate(); item.abort?.abort(); }
      root.remove(); mounts.delete(element); },
  });
  mounts.set(element, api); paint(); return api;
}
