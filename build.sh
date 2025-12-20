#!/bin/bash
# Build script for Linux/macOS
echo "Building Claude Agent Manager..."
python3 build.py "$@"
if [ $? -eq 0 ]; then
    echo ""
    echo "Build successful! Executable is in dist/"
else
    echo ""
    echo "Build failed!"
    exit 1
fi
