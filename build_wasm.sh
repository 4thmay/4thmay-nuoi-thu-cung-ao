#!/bin/bash
cd "$(dirname "$0")"
echo "Dang build WebAssembly bang pygbag..."
pygbag --disable-sound-format-error --build client
if [ -f "custom_index.html" ]; then
    cp custom_index.html client/build/web/index.html
fi
echo "Build hoan tat tai thu muc client/build/web"
