#!/bin/bash
cd "$(dirname "$0")"
echo "Dang build WebAssembly bang pygbag..."
pygbag --disable-sound-format-error --build client
echo "Build hoan tat tai thu muc client/build/web"
