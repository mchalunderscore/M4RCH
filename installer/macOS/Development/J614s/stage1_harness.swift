// Read-only harness for the real NativeBootChain.swift stage-1 implementation.
import CryptoKit
import Foundation

// The complete production file refers to payload APIs not used by this test.
// Match the production safeRelative implementation used by fillStage1.
enum NativeHandoffEvidence {
  static func safeRelative(_ path: String) -> Bool {
    !path.isEmpty && path.utf8.count <= 4096 && !path.hasPrefix("/") && !path.contains("\0")
      && !path.contains("\\")
      && path.split(separator: "/", omittingEmptySubsequences: false)
        .allSatisfy { !$0.isEmpty && $0 != "." && $0 != ".." }
  }
}

enum NativeHandoffValidationError: Error {
  case changedContent
  case unsafePath
}

enum NativePayloadPreflight {
  static func target(_ data: Data) throws -> [String: Any] {
    fatalError("Payload admission is outside the stage-1 harness")
  }
}

@main
struct Stage1Harness {
  static func main() throws {
    guard CommandLine.arguments.count == 2 else {
      throw NSError(domain: "Stage1Harness", code: 1)
    }
    let input = try Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1]))
    let hash = SHA256.hash(data: input).map { String(format: "%02x", $0) }.joined()
    precondition(
      hash == "c352def73ab145b1cb2d9f9a74785dc36641b480ff53b7f795403391f68fca0f",
      "Unexpected stage-1 input")
    let oldUUID = "5fdb35c6-3a66-416d-8358-6555fd99fcc5"
    let newUUID = "11111111-2222-4333-8444-555555555555"
    let newPath = "m1n1/boot.bin"
    try NativeBootChain.validateInstalledStage1(input, uuid: oldUUID, path: "boot.bin")
    let output = try NativeBootChain.fillStage1(
      input, uuid: newUUID, path: newPath, windowMilliseconds: 0)
    try NativeBootChain.validateInstalledStage1(output, uuid: newUUID, path: newPath)
    let marker = Data("AURORA-S1-CFG01\0".utf8)
    guard let range = input.range(of: marker) else { fatalError("Missing marker") }
    let start = range.upperBound
    precondition(input.count == output.count)
    precondition(input.prefix(start) == output.prefix(start))
    precondition(input.suffix(from: start + 244) == output.suffix(from: start + 244))
    precondition(output.range(of: Data(oldUUID.utf8)) == nil, "Old UUID remains")
    var corrupt = output
    corrupt[start + 48] ^= 1
    do {
      try NativeBootChain.validateInstalledStage1(corrupt, uuid: newUUID, path: newPath)
      fatalError("Corrupted configuration accepted")
    } catch NativeBootChainError.invalidStage1 {}
    do {
      _ = try NativeBootChain.fillStage1(
        input, uuid: newUUID, path: "../boot.bin", windowMilliseconds: 0)
      fatalError("Unsafe path accepted")
    } catch NativeBootChainError.invalidStage1 {}
    print(
      "PASS: real NativeBootChain rewrote and validated the identified stage 1; negative checks passed"
    )
    print("This checks configuration bytes only; it does not enroll or boot the image.")
  }
}
