import Foundation
import Vision
import AppKit

// usage: ocr <image.png> -> prints TSV: text \t x \t y \t w \t h \t conf  (normalized, origin top-left)
let args = CommandLine.arguments
guard args.count >= 2, let img = NSImage(contentsOfFile: args[1]),
      let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    FileHandle.standardError.write("cannot load image\n".data(using: .utf8)!)
    exit(1)
}
let req = VNRecognizeTextRequest()
req.recognitionLevel = .accurate
req.usesLanguageCorrection = false
req.minimumTextHeight = 0.003
let handler = VNImageRequestHandler(cgImage: cg, options: [:])
do { try handler.perform([req]) } catch {
    FileHandle.standardError.write("vision failed: \(error)\n".data(using: .utf8)!)
    exit(2)
}
for o in (req.results ?? []) {
    guard let c = o.topCandidates(1).first else { continue }
    let b = o.boundingBox
    let line = String(format: "%@\t%.4f\t%.4f\t%.4f\t%.4f\t%.2f", c.string.replacingOccurrences(of: "\t", with: " "), b.minX, 1.0 - b.maxY, b.width, b.height, c.confidence)
    print(line)
}
