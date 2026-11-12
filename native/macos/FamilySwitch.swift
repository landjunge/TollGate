// Catalog-ID-only native bridge. Shared with the executable, no-GUI fixture.
import Foundation
import CoreFoundation
#if canImport(Darwin)
import Darwin
#else
import Glibc
#endif

enum FamilySwitch {
    enum Outcome: String { case focused, failed, uncertain, missing }
    static let catalogIds = Set(["kirabridge", "threaddesk", "4allpass", "tollgate", "agent-authority"])
    static func brokerURL(home: URL = FileManager.default.homeDirectoryForCurrentUser) -> URL {
        home.appendingPathComponent(".local/bin/kirabridge")
    }
    static func arguments(target: String, sourcePid: Int32) -> [String] {
        ["--principal", "local", "family", "switch", target, "--source-pid", String(sourcePid)]
    }
    static func isValidTarget(_ target: String) -> Bool { catalogIds.contains(target) }
    static func bool(_ value: Any?) -> Bool? {
        guard let number = value as? NSNumber, CFGetTypeID(number) == CFBooleanGetTypeID() else { return nil }
        return number.boolValue
    }
    static func number(_ value: Any?) -> Double? {
        guard let number = value as? NSNumber, CFGetTypeID(number) != CFBooleanGetTypeID(),
              number.doubleValue.isFinite else { return nil }
        return number.doubleValue
    }
    static func outcome(forJSON data: Data, target: String, exitStatus: Int32) -> Outcome {
        guard data.count <= 65536, isValidTarget(target),
              let value = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
              let success = bool(value["success"]) else { return .uncertain }
        if let unknown = value["execution_outcome_unknown"], bool(unknown) != false { return .uncertain }
        if success {
            guard exitStatus == 0, value["error"] == nil,
                  value["active_product"] as? String == target,
                  let count = value["visible_family_windows"] as? NSNumber,
                  CFGetTypeID(count) != CFBooleanGetTypeID(),
                  !["d", "f"].contains(String(cString: count.objCType)), count.intValue == 1,
                  let bounds = value["actual_outer_bounds"] as? [String: Any],
                  ["x", "y", "width", "height"].allSatisfy({ number(bounds[$0]) != nil }),
                  number(bounds["width"])! > 0, number(bounds["height"])! > 0 else { return .uncertain }
            return .focused
        }
        // A known rejection needs both the broker's exit code and explicit
        // no-UNKNOWN receipt. Missing/contradictory evidence never enables retry.
        guard exitStatus == 2, bool(value["execution_outcome_unknown"]) == false,
              let error = value["error"] as? [String: Any],
              let code = error["code"] as? String, !code.isEmpty else { return .uncertain }
        return .failed
    }
    static func jsonString(_ text: String) -> String? {
        guard let data = try? JSONSerialization.data(withJSONObject: [text]) else { return nil }
        return String(data: data.dropFirst().dropLast(), encoding: .utf8)
    }
}

struct DashboardOrigin {
    let port: Int
    func permits(_ url: URL?) -> Bool {
        guard let url, let parts = URLComponents(url: url, resolvingAgainstBaseURL: false) else { return false }
        return parts.scheme == "http" && parts.host == "127.0.0.1" && parts.port == port &&
            parts.user == nil && parts.password == nil
    }
    func permitsMessage(mainFrame: Bool, scheme: String, host: String, port: Int,
                        frameURL: URL?, documentURL: URL?) -> Bool {
        mainFrame && scheme == "http" && host == "127.0.0.1" && port == self.port &&
            permits(frameURL) && permits(documentURL)
    }
}

@MainActor
final class FamilySwitchGate {
    private(set) var inFlight = false
    private(set) var uncertain = false
    enum Admission { case started, duplicate, busy, unknown }
    private var seen = Set<String>()
    func begin(_ requestID: String) -> Admission {
        guard !seen.contains(requestID) else { return .duplicate }
        guard !uncertain && seen.count < 1024 else { return .unknown }
        seen.insert(requestID)
        guard !inFlight else { return .busy }
        inFlight = true
        return .started
    }
    func finish(_ result: FamilySwitch.Outcome) {
        inFlight = false
        if result == .uncertain { uncertain = true }
    }
}

// A bounded native subprocess, never called on the main thread. Drain BOTH
// pipes while the owned child runs; no EOF wait on pipes retained by descendants.
// A timeout kills only this invocation, never the broker's persistent helper or
// any GUI/process group. Its possibly admitted effect remains UNKNOWN.
enum NativeIPC {
    struct Result { let data: Data; let status: Int32; let confirmed: Bool }
    static func run(executable: URL, arguments: [String], timeout: TimeInterval = 30.5,
                    limit: Int = 65536) async -> Result? {
        guard timeout.isFinite, timeout > 0, timeout <= 30.5, limit > 0, limit <= 65536 else { return nil }
        return await Task.detached(priority: .userInitiated) {
            let process = Process(), output = Pipe(), errors = Pipe()
            process.executableURL = executable; process.arguments = arguments
            process.standardInput = FileHandle.nullDevice
            process.standardOutput = output; process.standardError = errors
            do { try process.run() } catch { return nil }
            try? output.fileHandleForWriting.close(); try? errors.fileHandleForWriting.close()
            defer { try? output.fileHandleForReading.close(); try? errors.fileHandleForReading.close() }
            let out = output.fileHandleForReading.fileDescriptor, err = errors.fileHandleForReading.fileDescriptor
            var data = Data(), errorData = Data()
            var valid = fcntl(out, F_SETFL, O_NONBLOCK) == 0 && fcntl(err, F_SETFL, O_NONBLOCK) == 0
            let deadline = ProcessInfo.processInfo.systemUptime + timeout
            while valid {
                valid = drain(out, into: &data, limit: limit) && drain(err, into: &errorData, limit: limit)
                if !valid || !process.isRunning { break }
                if ProcessInfo.processInfo.systemUptime >= deadline { valid = false; break }
                usleep(5_000)
            }
            if process.isRunning {
                process.terminate()
                let stop = ProcessInfo.processInfo.systemUptime + 0.1
                while process.isRunning && ProcessInfo.processInfo.systemUptime < stop { usleep(5_000) }
                if process.isRunning { kill(process.processIdentifier, SIGKILL) }
                let killed = ProcessInfo.processInfo.systemUptime + 0.1
                while process.isRunning && ProcessInfo.processInfo.systemUptime < killed { usleep(5_000) }
                if process.isRunning {
                    // Cleanup is unconfirmed; never wait without a bound or
                    // inspect a termination status while the child is alive.
                    return Result(data: data, status: -999, confirmed: false)
                }
            }
            let complete = drain(out, into: &data, limit: limit) && drain(err, into: &errorData, limit: limit)
            return Result(data: data, status: process.terminationStatus, confirmed: valid && complete && process.terminationReason == .exit)
        }.value
    }
    private static func drain(_ fd: Int32, into data: inout Data, limit: Int) -> Bool {
        var buffer = [UInt8](repeating: 0, count: 4096)
        while data.count <= limit {
            let count = read(fd, &buffer, buffer.count)
            if count > 0 { data.append(contentsOf: buffer.prefix(count)); continue }
            if count == 0 || errno == EAGAIN || errno == EWOULDBLOCK { return true }
            if errno == EINTR { continue }
            return false
        }
        return false
    }
    static func switchTarget(_ target: String, sourcePid: Int32) async -> FamilySwitch.Outcome {
        guard FamilySwitch.isValidTarget(target) else { return .failed }
        guard let result = await run(executable: FamilySwitch.brokerURL(),
                                    arguments: FamilySwitch.arguments(target: target, sourcePid: sourcePid)) else { return .missing }
        guard result.confirmed else { return .uncertain }
        return FamilySwitch.outcome(forJSON: result.data, target: target, exitStatus: result.status)
    }
}
