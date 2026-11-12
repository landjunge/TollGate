import Foundation

@main
struct Fixture {
    @MainActor static func main() async throws {
        let args = CommandLine.arguments
        switch args[1] {
        case "receipt":
            let data = FileHandle.standardInput.readDataToEndOfFile()
            print(FamilySwitch.outcome(forJSON: data, target: args[2], exitStatus: Int32(args[3])!).rawValue)
        case "ipc", "ipc-diagnostic":
            let start = ProcessInfo.processInfo.systemUptime
            let result = await NativeIPC.run(executable: URL(fileURLWithPath: args[3]), arguments: Array(args.dropFirst(4)), timeout: Double(args[2])!)
            var value: [String: Any] = ["confirmed": result?.confirmed ?? false, "status": result?.status ?? -999,
                                       "text": String(decoding: result?.data ?? Data(), as: UTF8.self)]
            if args[1] == "ipc-diagnostic" {
                value["elapsed_ms"] = (ProcessInfo.processInfo.systemUptime - start) * 1000
            }
            print(String(decoding: try JSONSerialization.data(withJSONObject: value), as: UTF8.self))
        case "responsive":
            let gate = FamilySwitchGate()
            precondition(gate.begin("first") == .started)
            precondition(gate.begin("first") == .duplicate && gate.begin("busy") == .busy)
            var heartbeat = false
            Task { try? await Task.sleep(nanoseconds: 50_000_000); heartbeat = true }
            let result = await NativeIPC.run(executable: URL(fileURLWithPath: args[2]),
                                            arguments: ["-c", "import time; time.sleep(2.1); print('late')"], timeout: 3)
            precondition(heartbeat && result?.confirmed == true)
            gate.finish(.focused)
            precondition(gate.begin("first") == .duplicate)
            precondition(gate.begin("busy") == .duplicate)
            precondition(gate.begin("next") == .started) // explicit next user switch
            gate.finish(.uncertain)
            precondition(gate.begin("third") == .unknown) // UNKNOWN survives another request
            print("responsive late_receipt next_user_switch unknown_no_replay")
        case "origin":
            let origin = DashboardOrigin(port: 12345)
            let own = URL(string: "http://127.0.0.1:12345/dashboard?lang=de")!
            precondition(origin.permitsMessage(mainFrame: true, scheme: "http", host: "127.0.0.1", port: 12345, frameURL: own, documentURL: own))
            for url in ["http://127.0.0.1:12346/dashboard", "https://127.0.0.1:12345/dashboard", "http://localhost:12345/dashboard", "http://user@127.0.0.1:12345/dashboard", "file:///dashboard"] {
                let foreign = URL(string: url)!
                precondition(!origin.permits(foreign))
                precondition(!origin.permitsMessage(mainFrame: true, scheme: "http", host: "127.0.0.1", port: 12345, frameURL: foreign, documentURL: own))
                precondition(!origin.permitsMessage(mainFrame: true, scheme: "http", host: "127.0.0.1", port: 12345, frameURL: own, documentURL: foreign))
            }
            precondition(!origin.permitsMessage(mainFrame: false, scheme: "http", host: "127.0.0.1", port: 12345, frameURL: own, documentURL: own))
            precondition(!origin.permitsMessage(mainFrame: true, scheme: "http", host: "127.0.0.1", port: 1, frameURL: own, documentURL: own))
            let quoted = FamilySwitch.jsonString("quote\"\\\n ")!
            let decoded = try JSONSerialization.jsonObject(with: Data(("[" + quoted + "]").utf8)) as! [String]
            precondition(decoded == ["quote\"\\\n "])
            precondition(FamilySwitch.arguments(target: "tollgate", sourcePid: 123) == ["--principal", "local", "family", "switch", "tollgate", "--source-pid", "123"])
            print("origin frame port callback argv")
        #if canImport(Darwin)
        case "listener":
            let listener = try ReservedLoopback(), child = Process(), output = Pipe()
            child.executableURL = URL(fileURLWithPath: args[2])
            child.arguments = ["-c", "import socket; s=socket.fromfd(0,socket.AF_INET,socket.SOCK_STREAM); print(s.getsockname()[1],flush=True)"]
            child.standardInput = listener.handle; child.standardOutput = output; child.standardError = FileHandle.nullDevice
            try child.run(); try listener.handle.close(); child.waitUntilExit()
            let port = String(decoding: output.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines)
            precondition(child.terminationStatus == 0 && Int(port) == listener.port)
            print("inherited_owned_listener")
        #endif
        default: fatalError("Unknown fixture mode")
        }
    }
}
