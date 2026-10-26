import Foundation
import CoreGraphics
func mode(_ m:CGDisplayMode)->[String:Any] {
    ["id":m.ioDisplayModeID,"logical_width":m.width,"logical_height":m.height,"framebuffer_pixel_width":m.pixelWidth,"framebuffer_pixel_height":m.pixelHeight,"reported_refresh_hz":m.refreshRate,"io_flags":m.ioFlags,"usable_for_desktop":m.isUsableForDesktopGUI(),"scale_x":Double(m.pixelWidth)/Double(m.width),"scale_y":Double(m.pixelHeight)/Double(m.height)]
}
var ids=[CGDirectDisplayID](repeating:0,count:32),count:UInt32=0
let status=CGGetOnlineDisplayList(32,&ids,&count)
guard status == .success else { fputs("Display enumeration failed\n",stderr);exit(1) }
var displays=[[String:Any]]()
for id in ids.prefix(Int(count)) {
    let bounds=CGDisplayBounds(id), mm=CGDisplayScreenSize(id)
    var d:[String:Any] = ["id":id,"built_in":CGDisplayIsBuiltin(id) != 0,"active":CGDisplayIsActive(id) != 0,"main":CGDisplayIsMain(id) != 0,"vendor":CGDisplayVendorNumber(id),"model":CGDisplayModelNumber(id),"rotation_degrees":CGDisplayRotation(id),"physical_size_mm":["width":mm.width,"height":mm.height],"desktop_bounds":["x":bounds.origin.x,"y":bounds.origin.y,"width":bounds.width,"height":bounds.height],"current_framebuffer_pixel_width":CGDisplayPixelsWide(id),"current_framebuffer_pixel_height":CGDisplayPixelsHigh(id)]
    if let m=CGDisplayCopyDisplayMode(id) {d["current_mode"]=mode(m)}
    let options=[kCGDisplayShowDuplicateLowResolutionModes:true] as CFDictionary
    if let modes=CGDisplayCopyAllDisplayModes(id,options) as? [CGDisplayMode] {d["available_modes"]=modes.map(mode)}
    displays.append(d)
}
let result:[String:Any] = ["utc":ISO8601DateFormatter().string(from:Date()),"displays":displays,"interpretation":"CoreGraphics mode pixel dimensions describe framebuffer backing, not independently measured physical panel pixels. Reported 0 Hz is unspecified/variable; it is not evidence of 0 Hz or a fixed maximum. Compare physical-panel information in system_profiler and IORegistry captures. No mode was changed."]
let data=try JSONSerialization.data(withJSONObject:result,options:[.prettyPrinted,.sortedKeys]);FileHandle.standardOutput.write(data)
