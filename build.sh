#!/bin/bash
set -e

PROTO_SRC="Patronobuf/python/patronobuf/agents_pb2.py"
DEST_DIR="."

echo "[*] Copying agents_pb2.py to project directory..."
cp "$PROTO_SRC" "$DEST_DIR"/patronobuf.py

echo "[*] Syncing rye environment..."
rye sync

echo "[*] Building project with rye..."
rye build

echo "[✓] Done."
