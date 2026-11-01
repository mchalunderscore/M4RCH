#if os(macOS)
  import Foundation
  import AuroraFirmware
  import XCTest

  @testable import AuroraAppleInstallerTrustCore

  final class NativeExperimentalHardwareTests: XCTestCase {
    func testInstalledJ614sPayloadWhenRequested() async throws {
      guard ProcessInfo.processInfo.environment["M4RCH_INSTALLED_PAYLOAD"] == "1" else {
        throw XCTSkip("Installed payload inspection not requested")
      }
      let dir = URL(fileURLWithPath: "/Applications/Aurora Installer.app/Contents/Resources/Artifacts")
      let payload = ProcessInfo.processInfo.environment["M4RCH_PAYLOAD_PATH"]
        .map { URL(fileURLWithPath: $0) } ?? dir.appendingPathComponent("j614s-development-unsigned.zip")
      let metadata = try Data(contentsOf: dir.appendingPathComponent("j614s-metadata.json"))
      let owner: uid_t = ProcessInfo.processInfo.environment["M4RCH_PAYLOAD_PATH"] == nil ? 0 : getuid()
      let archive = try await IPSWArchive.open(NativePayloadRangeReader(payload, owner: owner))
      try await NativePayloadPreflight.validate(metadata: metadata, payloadName: payload.lastPathComponent, archive: archive)
      let facts = try NativeFirmwareSelection.Facts.live()
      let assessment = try NativeExperimentalHardware.assess(
        "apple,j614s", hardware: facts.hardware, policy: NativeInspectionPolicy.sealed(),
        metadata: NativeInstallationMetadata(data: metadata), level: .fullSend)
      let boot = try await NativeExperimentalBootChain.admit(
        metadata: metadata, archive: archive, assessment: assessment)
      XCTAssertEqual(boot.stage2, .own(member: "esp/m1n1/boot-j614s.bin"))
    }
    func testLiveJ614sInstallationSnapshotWhenRequested() throws {
      guard ProcessInfo.processInfo.environment["M4RCH_LIVE_SNAPSHOT"] == "1" else {
        throw XCTSkip("Live disk inspection not requested")
      }
      let disks = MacRemovalDiskOperator()
      XCTAssertEqual(try disks.targetType().lowercased(), "j614s")
      let snapshot = try disks.snapshot(maximumPartitions: 4096)
      XCTAssertFalse(snapshot.partitions.isEmpty)
      XCTAssertThrowsError(try disks.snapshot()) { error in
        XCTAssertEqual((error as? RemovalFailure)?.message, "Removal is not supported on this Mac model.")
      }
    }
    func testBuiltDeveloperProfileWhenProvided() throws {
      guard let path = ProcessInfo.processInfo.environment["M4RCH_PROFILE_PATH"] else {
        throw XCTSkip("No built developer profile supplied")
      }
      let configuration = try InstallerReleaseConfigurationLocator().load(
        from: URL(fileURLWithPath: path))
      let documents = try XCTUnwrap(configuration.sealedCatalogDocuments)
      var previous: AcceptedCatalogIdentity?
      if let oldPath = ProcessInfo.processInfo.environment["M4RCH_PREVIOUS_CATALOG"] {
        let data = try Data(contentsOf: URL(fileURLWithPath: oldPath))
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        let sequence = try XCTUnwrap(json["sequence"] as? UInt64)
        previous = try AcceptedCatalogIdentity(sequence: sequence, payloadDigest: SHA256Digest(hashing: data).rawValue)
      }
      let catalog = try AppleInstallerTrustCore().validateSupportCatalog(
        payload: documents.payload, signature: documents.signature,
        trustRoot: configuration.trustRoot, now: Date(), previouslyAccepted: previous)
      guard case .admitted(let record) = catalog.experimentalAdmission(for: "apple,j614s") else {
        return XCTFail("The developer catalog did not admit J614s")
      }
      XCTAssertEqual(record.installationProfile, "arch-minimal")
      XCTAssertEqual(record.payloadDigest, ProcessInfo.processInfo.environment["M4RCH_PAYLOAD_SHA"])
    }
    func testRetainedJ614sStage2WhenProvided() throws {
      guard let path = ProcessInfo.processInfo.environment["M4RCH_STAGE2_PATH"] else {
        throw XCTSkip("No retained J614s stage 2 supplied")
      }
      let data = try Data(contentsOf: URL(fileURLWithPath: path))
      let trees = NativeExperimentalHardware.deviceTrees(inStage2: data)
      XCTAssertTrue(trees.contains { $0.contains("apple,j614s") && $0.contains("apple,t6040") })
      XCTAssertEqual(
        NativeExperimentalHardware.stage2Source(
          deviceIdentifier: "apple,j614s", chipID: 0x6040,
          boardFiles: ["esp/m1n1/boot-j614s.bin": trees]),
        .own(member: "esp/m1n1/boot-j614s.bin"))
    }
    private let mac27 = NativeInspectionHardware(
      chipID: 0x6040, bootVersion: "mBoot-20457.1.29", macOSVersion: "27.0",
      recoveryVersion: "26.1.0.0.0,0")

    private func payload() throws -> NativeInstallationMetadata {
      try NativeInstallationMetadata(
        data: Data(
          #"{"os_list":[{"omarchy_target":"apple-silicon-full-os","default_os_name":"Fixture","partitions":[{"size":"1GiB"}]}]}"#
            .utf8))
    }

    func testSupportedMacsAreNeverOffered() throws {
      let policy = try NativeInspectionPolicy.sealed()
      let m2 = NativeInspectionHardware(
        chipID: 0x8112, bootVersion: "iBoot-13822.61.10", macOSVersion: "26.0",
        recoveryVersion: "25.1.354.0.0,0")
      XCTAssertEqual(
        NativeExperimentalHardware.refusal("apple,j413", hardware: m2, policy: policy), .supported)
      XCTAssertEqual(
        NativeExperimentalHardware.refusal("apple,j616s", hardware: mac27, policy: policy),
        .supported)
    }

    func testTheM1ProFamilyIsSupportedSoNeverExperimental() throws {
      let policy = try NativeInspectionPolicy.sealed()
      let t6000 = NativeInspectionHardware(
        chipID: 0x6000, bootVersion: "iBoot-13822.61.10", macOSVersion: "26.0",
        recoveryVersion: "25.1.354.0.0,0")
      for device in ["apple,j316s", "apple,j314s"] {
        XCTAssertEqual(
          NativeExperimentalHardware.refusal(device, hardware: t6000, policy: policy), .supported,
          device)
      }
    }

    func testAnUnknownBoardOnAKnownChipIsOfferedWithWarnings() throws {
      let policy = try NativeInspectionPolicy.sealed()
      XCTAssertNil(
        NativeExperimentalHardware.refusal("apple,j614s", hardware: mac27, policy: policy))
      let assessment = try NativeExperimentalHardware.assess(
        "apple,j614s", hardware: mac27, policy: policy, metadata: payload(), level: .fullSend)
      XCTAssertEqual(assessment.firmwareVersion, "26.6.2")
      XCTAssertTrue(assessment.policy.supports("apple,j614s", hardware: mac27))
      XCTAssertFalse(policy.supports("apple,j614s", hardware: mac27))
      XCTAssertTrue(assessment.warnings.contains { $0.contains("not listed for this board") })
      let selected = try NativeFirmwareSelection.choose(
        deviceIdentifier: "apple,j614s",
        facts: .init(deviceIdentifier: "apple,j614s", hardware: mac27), metadata: payload(),
        policy: assessment.policy, experimental: true)
      XCTAssertEqual(selected.version, "26.6.2")
      XCTAssertThrowsError(
        try NativeFirmwareSelection.choose(
          deviceIdentifier: "apple,j614s",
          facts: .init(deviceIdentifier: "apple,j614s", hardware: mac27), metadata: payload(),
          policy: assessment.policy))
    }

    func testAnUnknownChipGetsTheNewestStubItsFirmwareAccepts() throws {
      let policy = try NativeInspectionPolicy.sealed()
      let unknown = NativeInspectionHardware(
        chipID: 0x9001, bootVersion: "mBoot-20457.1.29", macOSVersion: "27.0",
        recoveryVersion: "26.1.0.0.0,0")
      let assessment = try NativeExperimentalHardware.assess(
        "apple,j999", hardware: unknown, policy: policy, metadata: payload(),
        level: .bootloaderOnly)
      XCTAssertEqual(assessment.firmwareVersion, "26.6.2")
      XCTAssertEqual(assessment.policy.chipMinimum["36865"], "26.6.2")
      let old = NativeInspectionHardware(
        chipID: 0x9001, bootVersion: "iBoot-1", macOSVersion: "11.0",
        recoveryVersion: "20.1.0.0.0,0")
      XCTAssertThrowsError(
        try NativeExperimentalHardware.assess(
          "apple,j999", hardware: old, policy: policy, metadata: payload(), level: .fullSend))
    }

    func testStageTwoPrefersOwnThenSameChipThenNone() {
      let files = [
        "esp/m1n1/boot-j616s.bin": [["apple,j616s", "apple,t6040", "apple,arm-platform"]],
        "esp/m1n1/boot-j773s.bin": [["apple,j773s", "apple,t6040", "apple,arm-platform"]],
        "esp/m1n1/boot-j413.bin": [["apple,j413", "apple,t8112", "apple,arm-platform"]],
      ]
      XCTAssertEqual(
        NativeExperimentalHardware.stage2Source(
          deviceIdentifier: "apple,j614s", chipID: 0x6040, boardFiles: files),
        .sibling(board: "j616s", member: "esp/m1n1/boot-j616s.bin"))
      XCTAssertEqual(
        NativeExperimentalHardware.stage2Source(
          deviceIdentifier: "apple,j413", chipID: 0x8112, boardFiles: files),
        .own(member: "esp/m1n1/boot-j413.bin"))
      XCTAssertEqual(
        NativeExperimentalHardware.stage2Source(
          deviceIdentifier: "apple,j999", chipID: 0x9001, boardFiles: files), .none)
    }

    func testRetargetNamesThisBoardFirstAndKeepsTheTree() throws {
      let tree = Self.fdt(["apple,j616s", "apple,t6040", "apple,arm-platform"])
      var stage2 = Data("aura".utf8) + Data("STACKBOT".utf8)
      stage2 += tree
      stage2 += Data([0x1f, 0x8b, 0x08, 0])
      let retargeted = try NativeExperimentalHardware.retarget(
        stage2: stage2, sibling: "j616s", deviceIdentifier: "apple,j614s")
      XCTAssertEqual(
        NativeExperimentalHardware.deviceTrees(inStage2: retargeted),
        [["apple,j614s", "apple,j616s", "apple,t6040", "apple,arm-platform"]])
      XCTAssertTrue(retargeted.suffix(4).elementsEqual([0x1f, 0x8b, 0x08, 0]))
      XCTAssertThrowsError(
        try NativeExperimentalHardware.retarget(
          stage2: stage2, sibling: "j413", deviceIdentifier: "apple,j614s"))
    }

    func testTheRecordAndReportSayExperimental() throws {
      let policy = try NativeInspectionPolicy.sealed()
      let assessment = try NativeExperimentalHardware.assess(
        "apple,j614s", hardware: mac27, policy: policy, metadata: payload(),
        level: .bootloaderOnly)
      let record =
        try JSONSerialization.jsonObject(
          with: NativeExperimentalHardware.record(
            assessment, stage2: .sibling(board: "j616s", member: "esp/m1n1/boot-j616s.bin"),
            stage1Bytes: 1, stage1SHA256: nil)) as! [String: Any]
      XCTAssertEqual(record["experimental"] as? Bool, true)
      XCTAssertEqual(record["level"] as? String, "bootloader-only")
      XCTAssertEqual(record["proxy_marker"] as? Bool, true)
      let facts = ExperimentalBringUpFacts(
        model: "Fixture", deviceIdentifier: "apple,j614s", chipID: 0x6040, systemBoot: "b",
        systemMacOS: "27.0", stubBoot: nil, stubMacOS: nil, level: .bootloaderOnly,
        stage2: "sibling", stage1: nil, warnings: ["w"])
      XCTAssertTrue(facts.report.contains("aura-proxy"))
      XCTAssertTrue(facts.report.contains("Nothing in this report was sent anywhere."))
    }

    /// A one-node tree with only a root compatible property.
    static func fdt(_ compatible: [String]) -> Data {
      func be(_ value: Int) -> [UInt8] {
        (0..<4).map { UInt8(truncatingIfNeeded: value >> (24 - 8 * $0)) }
      }
      let strings = Array("compatible\0".utf8)
      var value: [UInt8] = compatible.flatMap { Array($0.utf8) + [0] }
      let length = value.count
      value += [UInt8](repeating: 0, count: (4 - value.count % 4) % 4)
      var body = be(1) + [UInt8](repeating: 0, count: 4)
      body += be(3) + be(length) + be(0) + value + be(2) + be(9)
      let reserve = [UInt8](repeating: 0, count: 16)
      let structOffset = 40 + reserve.count
      let total = structOffset + body.count + strings.count
      let header =
        be(0xd00d_feed) + be(total) + be(structOffset) + be(structOffset + body.count) + be(40)
        + be(17) + be(16) + be(0) + be(strings.count) + be(body.count)
      return Data(header + reserve + body + strings)
    }
  }
#endif
