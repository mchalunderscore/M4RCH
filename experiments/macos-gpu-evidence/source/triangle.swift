import Foundation
import Metal
import CoreGraphics
import ImageIO

func writeJSON(_ value: Any, _ url: URL) throws {
    try JSONSerialization.data(withJSONObject: value, options: [.prettyPrinted, .sortedKeys]).write(to: url, options: .atomic)
}
func fail(_ text: String) -> NSError { NSError(domain: "M4RCHEvidence", code: 1, userInfo: [NSLocalizedDescriptionKey: text]) }
let output = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
let source = URL(fileURLWithPath: CommandLine.arguments[2])
func run() throws {
    guard let device = MTLCreateSystemDefaultDevice(), let queue = device.makeCommandQueue() else { throw fail("No Metal device/queue") }
    let library = try device.makeLibrary(source: String(contentsOf: source, encoding: .utf8), options: nil)
    let pipelineDesc = MTLRenderPipelineDescriptor()
    pipelineDesc.vertexFunction = library.makeFunction(name: "vertex_main")
    pipelineDesc.fragmentFunction = library.makeFunction(name: "fragment_main")
    pipelineDesc.colorAttachments[0].pixelFormat = .rgba8Unorm
    pipelineDesc.colorAttachments[0].isBlendingEnabled = false
    pipelineDesc.sampleCount = 1
    let pipeline = try device.makeRenderPipelineState(descriptor: pipelineDesc)
    let desc = MTLTextureDescriptor.texture2DDescriptor(pixelFormat: .rgba8Unorm, width: 64, height: 64, mipmapped: false)
    desc.usage = .renderTarget
    desc.storageMode = .private
    guard let texture = device.makeTexture(descriptor: desc), let buffer = device.makeBuffer(length: 16384, options: .storageModeShared) else { throw fail("Allocation failed") }
    texture.label = "64x64 RGBA8 triangle target"
    buffer.label = "CPU readback after completed blit"
    let pass = MTLRenderPassDescriptor()
    pass.colorAttachments[0].texture = texture
    pass.colorAttachments[0].loadAction = .clear
    pass.colorAttachments[0].storeAction = .store
    pass.colorAttachments[0].clearColor = MTLClearColorMake(0,0,0,1)
    func draw(_ readback: Bool) throws -> MTLCommandBuffer {
        guard let cb = queue.makeCommandBuffer(), let encoder = cb.makeRenderCommandEncoder(descriptor: pass) else { throw fail("Command allocation failed") }
        cb.label = "Single triangle, three vertices, no depth/MSAA/compute"
        encoder.setRenderPipelineState(pipeline)
        encoder.setViewport(MTLViewport(originX: 0, originY: 0, width: 64, height: 64, znear: 0, zfar: 1))
        encoder.setCullMode(.none)
        encoder.drawPrimitives(type: .triangle, vertexStart: 0, vertexCount: 3)
        encoder.endEncoding()
        if readback {
            guard let blit = cb.makeBlitCommandEncoder() else { throw fail("No blit encoder") }
            blit.copy(from: texture, sourceSlice: 0, sourceLevel: 0, sourceOrigin: MTLOrigin(x:0,y:0,z:0), sourceSize: MTLSize(width:64,height:64,depth:1), to: buffer, destinationOffset: 0, destinationBytesPerRow: 256, destinationBytesPerImage: 16384)
            blit.endEncoding()
        }
        cb.commit()
        cb.waitUntilCompleted()
        guard cb.status == .completed else { throw fail("GPU command failed: \(String(describing: cb.error))") }
        return cb
    }
    let capture = MTLCaptureManager.shared()
    var captureReport: [String: Any] = ["supported": capture.supportsDestination(.gpuTraceDocument), "requested": true]
    var capturing = false
    if capture.supportsDestination(.gpuTraceDocument) {
        let c = MTLCaptureDescriptor(); c.captureObject = queue; c.destination = .gpuTraceDocument
        c.outputURL = output.appendingPathComponent("triangle.gputrace")
        do { try capture.startCapture(with: c); capturing = true }
        catch { captureReport["error"] = String(describing: error) }
    } else { captureReport["reason"] = "Metal runtime reports gpuTraceDocument unsupported in this developer environment" }
    let first = try draw(true)
    if capturing { capture.stopCapture(); captureReport["created"] = FileManager.default.fileExists(atPath: output.appendingPathComponent("triangle.gputrace").path) }
    try writeJSON(captureReport, output.appendingPathComponent("metal-capture.json"))
    let pixels = Data(bytes: buffer.contents(), count: 16384)
    try pixels.write(to: output.appendingPathComponent("triangle.rgba"))
    let b = [UInt8](pixels)
    var inside = 0, outside = 0, mismatch = 0, unexpected = 0, colored = 0
    func matches(_ offset: Int, _ color: [Int]) -> Bool { (0..<4).allSatisfy { abs(Int(b[offset+$0])-color[$0]) <= 1 } }
    for y in 0..<64 { for x in 0..<64 {
        let px = 2*(Double(x)+0.5)/64-1, py = 1-2*(Double(y)+0.5)/64
        let wc = (py+0.75)/1.5, wb = ((px+0.75)/1.5)-wc/2, wa = 1-wb-wc
        let low = min(wa, min(wb,wc)), offset = (y*64+x)*4
        let fill = matches(offset,[255,64,0,255]), background = matches(offset,[0,0,0,255])
        if fill { colored += 1 }
        if !fill && !background { unexpected += 1 }
        if low > 0.04 { inside += 1; if !fill { mismatch += 1 } }
        if low < -0.04 { outside += 1; if !background { mismatch += 1 } }
    } }
    let verified = mismatch == 0 && unexpected == 0 && inside > 700 && outside > 2000 && colored > 900
    try writeJSON(["verified":verified,"interior_pixels_checked":inside,"exterior_pixels_checked":outside,"mismatches":mismatch,"unexpected_colors":unexpected,"colored_pixels":colored,"width":64,"height":64,"format":"RGBA8Unorm","bytes_per_row":256,"pixel_order":"top-left origin, row-major RGBA","interior_expected":[255,64,0,255],"background_expected":[0,0,0,255],"tolerance_per_channel":1,"barycentric_edge_exclusion":0.04,"gpu_command_status":"completed","gpu_start_time":first.gpuStartTime,"gpu_end_time":first.gpuEndTime], output.appendingPathComponent("verification.json"))
    guard verified else { throw fail("Triangle readback did not match independent CPU geometry/color checks") }
    guard let provider = CGDataProvider(data: pixels as CFData), let image = CGImage(width:64,height:64,bitsPerComponent:8,bitsPerPixel:32,bytesPerRow:256,space:CGColorSpaceCreateDeviceRGB(),bitmapInfo:CGBitmapInfo(rawValue: CGImageAlphaInfo.last.rawValue),provider:provider,decode:nil,shouldInterpolate:false,intent:.defaultIntent), let png = CGImageDestinationCreateWithURL(output.appendingPathComponent("triangle.png") as CFURL,"public.png" as CFString,1,nil) else { throw fail("PNG creation failed") }
    CGImageDestinationAddImage(png,image,nil)
    guard CGImageDestinationFinalize(png) else { throw fail("PNG write failed") }
    try writeJSON(["device":device.name,"registry_id":String(device.registryID),"unified_memory":device.hasUnifiedMemory,"sample_count":1,"color_format":"RGBA8Unorm","depth":false,"msaa":false,"compute":false,"vertices":[[-0.75,-0.75],[0.75,-0.75],[0.0,0.75]],"start_utc":ISO8601DateFormatter().string(from:Date()),"maximum_seconds":240], output.appendingPathComponent("workload.json"))
    try Data("ready\n".utf8).write(to:output.appendingPathComponent("ready"))
    let start=Date(); var draws=1; var last=Date.distantPast
    while Date().timeIntervalSince(start)<240 && !FileManager.default.fileExists(atPath:output.appendingPathComponent("stop").path) {
        try autoreleasepool { for _ in 0..<8 { _ = try draw(false); draws += 1 } }
        if Date().timeIntervalSince(last)>1 {
            try writeJSON(["draws_completed":draws,"elapsed_seconds":Date().timeIntervalSince(start),"utc":ISO8601DateFormatter().string(from:Date()),"running":true], output.appendingPathComponent("progress.json")); last=Date()
        }
        Thread.sleep(forTimeInterval:0.008)
    }
    _ = try draw(true)
    let final = Data(bytes:buffer.contents(),count:16384)
    try final.write(to:output.appendingPathComponent("triangle-final.rgba"))
    guard final == pixels else { throw fail("Final rendered target differs from initial verified pixels") }
    try writeJSON(["draws_completed":draws+1,"elapsed_seconds":Date().timeIntervalSince(start),"utc":ISO8601DateFormatter().string(from:Date()),"running":false,"final_readback_matches_initial":true], output.appendingPathComponent("progress.json"))
}
do { try run() } catch {
    try? writeJSON(["error":String(describing:error)],output.appendingPathComponent("failure.json"))
    fputs("\(error)\n",stderr); exit(1)
}
