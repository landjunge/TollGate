// Family-switch CLI ABI — thin, testable wrapper around the fixed argv and the
// JSON result of `~/.local/bin/kirabridge`. Only the catalog id crosses the web
// boundary; the host supplies its own PID and the fixed argv. No URL, PID or
// token ever originates from the web layer.
import Foundation

enum FamilySwitch {
    enum Outcome: String { case focused, failed, uncertain, missing, opened }

    static let brokerRelativePath = ".local/bin/kirabridge"
    static let catalogIds = Set(["kirabridge", "threaddesk", "4allpass", "tollgate", "agent-authority"])

    static func brokerURL(home: URL = FileManager.default.homeDirectoryForCurrentUser) -> URL {
        home.appendingPathComponent(brokerRelativePath)
    }

    /// Fixed argv. The web layer contributes nothing but the catalog id.
    static func arguments(target: String, sourcePid: Int32) -> [String] {
        ["--principal", "local", "family", "switch", target,
         "--source-pid", String(sourcePid)]
    }

    static func isValidTarget(_ target: String) -> Bool {
        catalogIds.contains(target)
    }

    /// Parse the CLI result and map it to the bounded web outcome. A missing
    /// broker or a "missing" error is reported as `.missing`, never faked as a
    /// successful switch. Unknown JSON / unknown execution stays `.uncertain`.
    static func outcome(forJSON data: Data, target: String) -> Outcome {
        guard let value = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let success = value["success"] as? Bool else {
            return .uncertain
        }
        if success {
            guard let active = value["active_product"] as? String else { return .uncertain }
            return active == target ? .focused : .uncertain
        }
        let unknown = value["execution_outcome_unknown"] as? Bool ?? false
        if unknown { return .uncertain }
        let error = value["error"] as? [String: Any]
        let code = error?["code"] as? String ?? ""
        return code == "missing" ? .missing : .failed
    }

    /// Outcome for a spawn failure (broker not executable). Always `.missing`.
    static func missingBrokerOutcome() -> Outcome { .missing }
}
