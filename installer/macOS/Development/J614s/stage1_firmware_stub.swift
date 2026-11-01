// Test-only module needed to compile the unchanged NativeBootChain.swift file.
// The stage-1 harness does not call archive APIs.
import Foundation

public struct IPSWArchive {
  public struct Member {
    public let name: String
    public let isDirectory: Bool
    public let sizeBytes: Int
  }
  public let members: [Member] = []
  public func read(_ member: Member, maximumBytes: Int) async throws -> Data {
    fatalError("Archive access is outside the stage-1 harness")
  }
}
