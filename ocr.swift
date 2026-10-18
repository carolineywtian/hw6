// Problem 5: read the text a person can see in a screenshot, using Apple's Vision OCR (the engine
// behind Live Text). Prints one recognized line per output line, top to bottom.
//
//   swift ocr.swift output/person_view/p01_bluehen_quote.png

import AppKit
import Vision

guard CommandLine.arguments.count == 2,
      let image = NSImage(contentsOfFile: CommandLine.arguments[1]),
      let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    FileHandle.standardError.write("usage: swift ocr.swift <image.png>\n".data(using: .utf8)!)
    exit(1)
}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false  // keep codes like CC-HD-006 exactly as drawn

try VNImageRequestHandler(cgImage: cgImage).perform([request])
let lines = (request.results ?? [])
    .sorted { $0.boundingBox.minY > $1.boundingBox.minY }  // Vision's origin is bottom-left
    .compactMap { $0.topCandidates(1).first?.string }
print(lines.joined(separator: "\n"))
