import Foundation

// Compile-only stubs for the metadata authentication path, which this harness
// never calls. The policy and its source are the real installer files.
struct StagedInstallerArtifact {
  struct Artifact {
    let role: String
    let expectedSizeBytes: UInt64
    let expectedDigest: String
  }
  let fileURL: URL
  let artifact: Artifact
}
struct SHA256Digest {
  let rawValue: String
  init(hashing: Data) { rawValue = "unused" }
}

@main
struct PolicyHarness {
  static func main() throws {
    let matching = NativeInspectionHardware(
      chipID: 0x6040, bootVersion: nil, macOSVersion: nil, recoveryVersion: nil)
    let other = NativeInspectionHardware(
      chipID: 0x6000, bootVersion: nil, macOSVersion: nil, recoveryVersion: nil)
    let sealed = try NativeInspectionPolicy.sealed()
    guard !sealed.supports("apple,j614s", hardware: matching) else {
      fatalError("sealed production policy unexpectedly admits J614s")
    }
    guard
      var json = try JSONSerialization.jsonObject(
        with: Data(NativeInspectionPolicySource.json.utf8))
        as? [String: Any], var devices = json["devices"] as? [String: Any]
    else { fatalError("invalid policy fixture") }
    devices["j614s"] = ["minimum": "26.6.2", "expert": false]
    json["devices"] = devices
    let candidate = try JSONDecoder().decode(
      NativeInspectionPolicy.self, from: JSONSerialization.data(withJSONObject: json))
    guard candidate.supports("apple,j614s", hardware: matching),
      !candidate.supports("apple,j614s", hardware: other)
    else { fatalError("candidate does not enforce J614s/T6040 pairing") }
    print("PASS: production policy refuses J614s; synthetic policy requires T6040")
    print("This does not authorize a catalog, change a disk or qualify a boot.")
  }
}
