// TollGate native macOS host: a lean AppKit WKWebView wrapper around the local
// TollGate dashboard, plus the fixed five-product family switch via
// ~/.local/bin/kirabridge. This host has no budget/stop/provider rights; it only
// renders the local dashboard and relays catalog-id-only switch requests.
import Cocoa
import WebKit
import Darwin

let FAMILY_PRODUCT_IDS = ["kirabridge", "threaddesk", "4allpass", "tollgate", "agent-authority"]

/// Bounded outcome returned to the web layer. Mirrors FamilySwitch.Outcome.
func resolveOutcome(_ outcome: FamilySwitch.Outcome) -> String { outcome.rawValue }

/// Find a free loopback TCP port by binding to 127.0.0.1:0 and reading it back.
func findFreeLoopbackPort() -> Int32 {
    let sock = socket(AF_INET, SOCK_STREAM, 0)
    guard sock >= 0 else { return 8787 }
    defer { close(sock) }
    var addr = sockaddr_in()
    addr.sin_family = sa_family_t(AF_INET)
    addr.sin_port = 0
    addr.sin_addr.s_addr = inet_addr("127.0.0.1")
    let bound = withUnsafePointer(to: &addr) { ptr in
        ptr.withMemoryRebound(to: sockaddr.self, capacity: 1) { sap in
            Darwin.bind(sock, sap, socklen_t(MemoryLayout<sockaddr_in>.size))
        }
    }
    guard bound == 0 else { return 8787 }
    var len = socklen_t(MemoryLayout<sockaddr_in>.size)
    let got = withUnsafeMutablePointer(to: &addr) { ptr in
        ptr.withMemoryRebound(to: sockaddr.self, capacity: 1) { sap in
            Darwin.getsockname(sock, sap, &len)
        }
    }
    guard got == 0 else { return 8787 }
    return Int32(UInt16(bigEndian: addr.sin_port))
}

/// Resolve the TollGate server command. Prefers the bundled backend source plus
/// an existing python runtime (independent of the dev worktree), then an
/// installed launcher, then any python3 with an installed tollgate. The host
/// never installs or overwrites anything.
func candidatePython() -> String? {
    let candidates = [
        "/usr/local/bin/python3.11",    // Homebrew Intel
        "/opt/homebrew/bin/python3.11", // Homebrew Apple Silicon
        "/usr/local/bin/python3",
        "/usr/bin/python3",
    ]
    for path in candidates where FileManager.default.isExecutableFile(atPath: path) {
        return path
    }
    return nil
}

func bundledBackendSrc() -> URL? {
    guard let resource = Bundle.main.resourceURL else { return nil }
    let src = resource.appendingPathComponent("backend/src")
    var isDir: ObjCBool = false
    if FileManager.default.fileExists(atPath: src.appendingPathComponent("tollgate").path,
                                      isDirectory: &isDir), isDir.boolValue {
        return src
    }
    return nil
}

func resolveServeCommand() -> (String, [String], [String: String])? {
    // 1. Bundled backend source + an existing python runtime (no dev-WT dependency).
    if let src = bundledBackendSrc(), let py = candidatePython() {
        return (py, ["-m", "tollgate", "serve"], ["PYTHONPATH": src.path])
    }
    // 2. Existing installed launcher.
    let launcher = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".local/bin/tollgate")
    if FileManager.default.isExecutableFile(atPath: launcher.path) {
        return (launcher.path, ["serve"], [:])
    }
    // 3. Any python3 with an installed tollgate (best-effort).
    if let py = candidatePython() {
        return (py, ["-m", "tollgate", "serve"], [:])
    }
    return nil
}

final class TollGateHost: NSObject, NSApplicationDelegate, WKUIDelegate, WKNavigationDelegate, WKScriptMessageHandler {
    var window: NSWindow!
    var webView: WKWebView!
    var backend: Process?
    var backendPort: Int32 = 8787
    let contentController = WKUserContentController()

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        buildMenu()

        let configuration = WKWebViewConfiguration()
        configuration.userContentController = contentController
        contentController.add(self, name: "familySwitch")
        configuration.websiteDataStore = .default()
        configuration.applicationNameForUserAgent = "TollGateDesktop"

        webView = WKWebView(frame: .zero, configuration: configuration)
        webView.uiDelegate = self
        webView.navigationDelegate = self

        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 800, height: 600),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered, defer: false)
        // Outer bounds 1360×780 as the comparison start (frame, not content rect).
        window.setFrame(NSRect(x: 0, y: 0, width: 1360, height: 780), display: false)
        window.title = "TollGate"
        window.minSize = NSSize(width: 820, height: 620)
        window.contentView = webView
        window.isReleasedWhenClosed = false
        window.delegate = self
        window.center()
        window.makeKeyAndOrderFront(nil)

        startBackendAndLoad()
        NSApp.activate(ignoringOtherApps: true)
    }

    func buildMenu() {
        let menu = NSMenu()
        let item = NSMenuItem()
        menu.addItem(item)
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "TollGate beenden", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        item.submenu = appMenu
        NSApp.mainMenu = menu
    }

    // MARK: Backend (loopback only)

    func startBackendAndLoad() {
        // Reuse an already-running TollGate on the default port when healthy.
        backendPort = findFreeLoopbackPort()
        guard let (cmd, args, env) = resolveServeCommand() else {
            loadErrorPage("TollGate-Server nicht gefunden")
            return
        }
        let task = Process()
        task.executableURL = URL(fileURLWithPath: cmd)
        task.arguments = args
        var environment = ProcessInfo.processInfo.environment
        environment["HOST"] = "127.0.0.1"
        environment["PORT"] = String(backendPort)
        for (k, v) in env { environment[k] = v }
        task.environment = environment
        task.standardInput = FileHandle.nullDevice
        task.standardOutput = FileHandle.nullDevice
        task.standardError = FileHandle.nullDevice
        backend = task
        do { try task.run() } catch { loadErrorPage("TollGate-Server konnte nicht gestartet werden"); return }
        // Poll the local health endpoint, then load the dashboard.
        let port = backendPort
        DispatchQueue.global().async { [weak self] in
            self?.waitForHealth(port: port)
        }
    }

    func waitForHealth(port: Int32) {
        let url = URL(string: "http://127.0.0.1:\(port)/v1/health")!
        for _ in 0..<60 {
            if let data = try? Data(contentsOf: url), !data.isEmpty {
                DispatchQueue.main.async { [weak self] in
                    self?.loadDashboard(port: port)
                }
                return
            }
            usleep(200_000)
        }
        DispatchQueue.main.async { [weak self] in
            self?.loadErrorPage("TollGate-Server antwortet nicht")
        }
    }

    func loadDashboard(port: Int32) {
        let url = URL(string: "http://127.0.0.1:\(port)/dashboard")!
        webView.load(URLRequest(url: url))
    }

    func loadErrorPage(_ text: String) {
        webView.loadHTMLString("<meta charset='utf-8'><p>\(text)</p>", baseURL: nil)
    }

    // MARK: Family switch (catalog id only)

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.name == "familySwitch",
              let body = message.body as? [String: Any],
              let requestId = body["requestId"] as? String,
              let appId = body["appId"] as? String,
              FamilySwitch.isValidTarget(appId) else {
            return
        }
        let outcome = performFamilySwitch(target: appId)
        resolveWebRequest(requestId, outcome: resolveOutcome(outcome))
    }

    func performFamilySwitch(target: String) -> FamilySwitch.Outcome {
        let broker = FamilySwitch.brokerURL()
        guard FileManager.default.isExecutableFile(atPath: broker.path) else {
            return .missing
        }
        let process = Process()
        process.executableURL = broker
        process.arguments = FamilySwitch.arguments(target: target, sourcePid: ProcessInfo.processInfo.processIdentifier)
        process.standardInput = FileHandle.nullDevice
        let stdout = Pipe(); let stderr = Pipe()
        process.standardOutput = stdout; process.standardError = stderr
        do { try process.run(); process.waitUntilExit() }
        catch { return .missing }
        let data = stdout.fileHandleForReading.readDataToEndOfFile()
        return FamilySwitch.outcome(forJSON: data, target: target)
    }

    func resolveWebRequest(_ requestId: String, outcome: String) {
        let script = "window.__tgFamilySwitchResolve && window.__tgFamilySwitchResolve(\(json(requestId)), \(json(outcome)));"
        webView.evaluateJavaScript(script, completionHandler: nil)
    }

    func json(_ value: String) -> String {
        let data = try! JSONSerialization.data(withJSONObject: [value])
        return String(data: data.dropFirst().dropLast(), encoding: .utf8) ?? "\"\""
    }

    // MARK: Window lifecycle

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        window?.makeKeyAndOrderFront(nil)
        return true
    }

    func applicationWillTerminate(_ notification: Notification) {
        if let backend, backend.isRunning {
            backend.terminate()  // This exact child only, never a process group.
        }
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url,
              url.scheme == "http", url.host == "127.0.0.1",
              url.user == nil, url.password == nil else {
            decisionHandler(.cancel); return
        }
        decisionHandler(.allow)
    }
}

extension TollGateHost: NSWindowDelegate {
    func windowShouldClose(_ sender: NSWindow) -> Bool {
        // Close hides; the backend keeps running so a reopen is instant.
        sender.orderOut(nil)
        return false
    }
}

let host = TollGateHost()
let app = NSApplication.shared
app.delegate = host
app.run()
