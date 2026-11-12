import Foundation
import Darwin

// Reserve the listener until Process has inherited it as stdin (fd 0). There is
// no find-free-port/close/rebind interval and no adoption of another server.
final class ReservedLoopback {
    let handle: FileHandle
    let port: Int
    init() throws {
        let fd = socket(AF_INET, SOCK_STREAM, 0)
        guard fd >= 0 else { throw NSError(domain: "TollGateListener", code: 1) }
        var address = sockaddr_in()
        address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        address.sin_family = sa_family_t(AF_INET)
        address.sin_addr.s_addr = inet_addr("127.0.0.1")
        let bound = withUnsafePointer(to: &address) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { Darwin.bind(fd, $0, socklen_t(MemoryLayout<sockaddr_in>.size)) }
        }
        var length = socklen_t(MemoryLayout<sockaddr_in>.size)
        let named = withUnsafeMutablePointer(to: &address) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { getsockname(fd, $0, &length) }
        }
        guard bound == 0, named == 0, listen(fd, 128) == 0 else {
            close(fd); throw NSError(domain: "TollGateListener", code: 2)
        }
        port = Int(UInt16(bigEndian: address.sin_port))
        handle = FileHandle(fileDescriptor: fd, closeOnDealloc: true)
    }
}
