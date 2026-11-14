#!/bin/zsh
# Compile the macOS Vision OCR helper (needs Xcode command line tools). Output: ./ocr
cd "${0:A:h}" && swiftc -O ocr.swift -o ocr && echo "built ${0:A:h}/ocr"
