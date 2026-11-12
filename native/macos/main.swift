// Native display host. No budget, stop, provider or OS-permission grants.
import Cocoa
@preconcurrency import WebKit
import Darwin

@MainActor
final class TollGateHost: NSObject, NSApplicationDelegate, WKUIDelegate, WKNavigationDelegate, WKScriptMessageHandler, NSWindowDelegate {
    var window: NSWindow!
    var webView: WKWebView!
    var backend: Process?
    var origin: DashboardOrigin?
    var documentGeneration = 0
    var terminating = false
    let familyGate = FamilySwitchGate()
    let contentController = WKUserContentController()
    var english: Bool { Locale.preferredLanguages.first?.hasPrefix("de") != true }
    func text(_ de: String, _ en: String) -> String { english ? en : de }

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        let menu = NSMenu(), item = NSMenuItem(), appMenu = NSMenu()
        menu.addItem(item)
        appMenu.addItem(withTitle: text("TollGate beenden", "Quit TollGate"), action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        item.submenu = appMenu; NSApp.mainMenu = menu
        let configuration = WKWebViewConfiguration()
        configuration.userContentController = contentController
        contentController.add(self, name: "familySwitch")
        configuration.websiteDataStore = .nonPersistent()
        configuration.applicationNameForUserAgent = "TollGateDesktop"
        webView = WKWebView(frame: .zero, configuration: configuration)
        webView.uiDelegate = self; webView.navigationDelegate = self
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 800, height: 600),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.setFrame(NSRect(x: 0, y: 0, width: 1360, height: 780), display: false)
        window.title = "TollGate"; window.minSize = NSSize(width: 820, height: 620)
        window.contentView = webView; window.isReleasedWhenClosed = false; window.delegate = self
        window.center(); window.makeKeyAndOrderFront(nil)
        Task { await startBackendAndLoad() }
        NSApp.activate(ignoringOtherApps: true)
    }

    func startBackendAndLoad() async {
        guard let resources = Bundle.main.resourceURL,
              let runtime = try? String(contentsOf: resources.appendingPathComponent("runtime-python.txt"), encoding: .utf8)
                .trimmingCharacters(in: .whitespacesAndNewlines),
              runtime.hasPrefix("/"), FileManager.default.isExecutableFile(atPath: runtime) else {
            loadErrorPage(text("Konfiguriertes Python fehlt. Siehe native/macos/README.md.", "Configured Python is missing. See native/macos/README.md.")); return
        }
        let script = resources.appendingPathComponent("backend/backend_host.py").path
        guard let checked = await NativeIPC.run(executable: URL(fileURLWithPath: runtime), arguments: ["-I", "-B", script, "--check"], timeout: 5),
              checked.confirmed, checked.status == 0 else {
            loadErrorPage(text("Python-Abhängigkeiten fehlen; kein automatischer Installationsversuch.", "Python dependencies are missing; no automatic installation attempted.")); return
        }
        guard !terminating else { return }
        do {
            let listener = try ReservedLoopback(), process = Process(), nonce = UUID().uuidString
            process.executableURL = URL(fileURLWithPath: runtime)
            process.arguments = ["-I", "-B", script, "--serve-inherited"]
            var environment = ProcessInfo.processInfo.environment
            environment["TOLLGATE_NATIVE_NONCE"] = nonce
            process.environment = environment
            process.standardInput = listener.handle
            process.standardOutput = FileHandle.nullDevice; process.standardError = FileHandle.nullDevice
            try process.run()
            try? listener.handle.close()
            backend = process
            let boundOrigin = DashboardOrigin(port: listener.port)
            let configuration = URLSessionConfiguration.ephemeral
            configuration.timeoutIntervalForRequest = 0.5; configuration.timeoutIntervalForResource = 0.5
            let session = URLSession(configuration: configuration)
            defer { session.invalidateAndCancel() }
            let deadline = ProcessInfo.processInfo.systemUptime + 12
            let readyURL = URL(string: "http://127.0.0.1:\(listener.port)/_native/ready")!
            while !terminating && process.isRunning && ProcessInfo.processInfo.systemUptime < deadline {
                if let (data, response) = try? await session.data(from: readyURL), data.count <= 4096,
                   response.url == readyURL, (response as? HTTPURLResponse)?.statusCode == 200,
                   let value = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
                   value["nonce"] as? String == nonce, value["pid"] as? Int32 == process.processIdentifier,
                   !terminating, process.isRunning {
                    origin = boundOrigin
                    webView.load(URLRequest(url: URL(string: "http://127.0.0.1:\(listener.port)/dashboard")!))
                    return
                }
                try? await Task.sleep(nanoseconds: 100_000_000)
            }
            // Only the exact child we started, never another agent/server/group.
            if process.isRunning { process.terminate() }
            loadErrorPage(text("Eigenes Backend nicht bestätigt.", "Owned backend could not be confirmed."))
        } catch {
            loadErrorPage(text("Backend konnte nicht gestartet werden.", "Backend could not be started."))
        }
    }
    func loadErrorPage(_ text: String) {
        origin = nil
        // All messages above are fixed native strings, never provider/user data.
        webView.loadHTMLString("<meta charset='utf-8'><p>\(text)</p>", baseURL: nil)
    }

    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        guard controller === contentController, message.webView === webView, message.name == "familySwitch",
              backend?.isRunning == true, let origin,
              origin.permitsMessage(mainFrame: message.frameInfo.isMainFrame,
                scheme: message.frameInfo.securityOrigin.protocol, host: message.frameInfo.securityOrigin.host,
                port: message.frameInfo.securityOrigin.port, frameURL: message.frameInfo.request.url, documentURL: webView.url),
              let body = message.body as? [String: Any], Set(body.keys) == ["requestId", "appId"],
              let requestId = body["requestId"] as? String,
              requestId.range(of: "^[A-Za-z0-9_-]{1,128}$", options: .regularExpression) != nil,
              let appId = body["appId"] as? String, FamilySwitch.isValidTarget(appId) else { return }
        switch familyGate.begin(requestId) {
        case .duplicate: return // do not resolve/overwrite the original in-flight request
        case .busy: resolve(requestId, outcome: .failed); return
        case .unknown: resolve(requestId, outcome: .uncertain); return
        case .started: break
        }
        let generation = documentGeneration
        Task {
            let result = await NativeIPC.switchTarget(appId, sourcePid: ProcessInfo.processInfo.processIdentifier)
            familyGate.finish(result)
            // Never deliver a former document's receipt into its replacement.
            guard generation == documentGeneration, backend?.isRunning == true,
                  origin.permits(webView.url) else { return }
            resolve(requestId, outcome: result)
        }
    }
    func resolve(_ requestId: String, outcome: FamilySwitch.Outcome) {
        guard let id = FamilySwitch.jsonString(requestId), let result = FamilySwitch.jsonString(outcome.rawValue) else { return }
        webView.evaluateJavaScript("window.__tgFamilySwitchResolve && window.__tgFamilySwitchResolve(\(id), \(result));", completionHandler: nil)
    }
    func webView(_ view: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if view === webView, origin == nil, action.request.url?.absoluteString == "about:blank" {
            decisionHandler(.allow); return
        }
        guard view === webView, backend?.isRunning == true, let origin, action.targetFrame != nil,
              origin.permits(action.request.url) else { decisionHandler(.cancel); return }
        decisionHandler(.allow)
    }
    func webView(_ view: WKWebView, decidePolicyFor response: WKNavigationResponse, decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        if view === webView, origin == nil, response.response.url?.absoluteString == "about:blank" {
            decisionHandler(.allow); return
        }
        guard view === webView, backend?.isRunning == true, let origin, origin.permits(response.response.url) else {
            decisionHandler(.cancel); return
        }
        decisionHandler(.allow)
    }
    func webView(_ view: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
        if view === webView { documentGeneration += 1 }
    }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        window?.makeKeyAndOrderFront(nil); return true
    }
    func windowShouldClose(_ sender: NSWindow) -> Bool { sender.orderOut(nil); return false }
    func applicationWillTerminate(_ notification: Notification) {
        terminating = true; origin = nil
        if let backend, backend.isRunning { backend.terminate() }
    }
}

MainActor.assumeIsolated {
    let host = TollGateHost()
    let app = NSApplication.shared
    app.delegate = host
    withExtendedLifetime(host) { app.run() }
}
