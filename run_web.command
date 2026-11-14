#!/bin/bash
cd "$(dirname "$0")/client/build/web"
echo "Dang khoi chay ban Web (WebAssembly / Pygbag) tai http://localhost:8088..."
python3 -m http.server 8088 &
SERVER_PID=$!
sleep 1
open "http://localhost:8088"
echo "Da mo trinh duyet! Nhan Ctrl+C de dung."
wait $SERVER_PID
