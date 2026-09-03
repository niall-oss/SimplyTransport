#!/usr/bin/env bash
# Download the latest TFI static GTFS zip into gtfs_data/TFI/.
# Does not import. After this:
#   echo y | litestar importgtfs
set -euo pipefail

URL="https://www.transportforireland.ie/transitData/Data/GTFS_Realtime.zip"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST_DIR="$REPO_ROOT/gtfs_data/TFI"
DOWNLOAD_DIR="$DEST_DIR/gtfs_checker"
ZIP_PATH="$DOWNLOAD_DIR/GTFS_Realtime.zip"

FORCE_OPERATION=false
if [[ "${1:-}" == "-f" ]]; then
    FORCE_OPERATION=true
    echo "Force unzip even if agency.txt is unchanged"
    echo
fi

mkdir -p "$DOWNLOAD_DIR"

if command -v wget >/dev/null 2>&1; then
    wget -nv -N "$URL" -P "$DOWNLOAD_DIR"
elif command -v curl >/dev/null 2>&1; then
    if [[ -f "$ZIP_PATH" ]]; then
        curl -fL -z "$ZIP_PATH" -o "$ZIP_PATH" "$URL"
    else
        curl -fL -o "$ZIP_PATH" "$URL"
    fi
else
    echo "Need wget or curl on PATH" >&2
    exit 1
fi

if [[ ! -f "$ZIP_PATH" ]]; then
    echo "Download failed: $ZIP_PATH not found" >&2
    exit 1
fi

unzip -j -o "$ZIP_PATH" agency.txt -d "$DOWNLOAD_DIR"

if [[ ! -f "$DEST_DIR/agency.txt" ]] || [[ "$FORCE_OPERATION" == true ]]; then
    unzip -o "$ZIP_PATH" -d "$DEST_DIR"
elif [[ "$(stat -c %y "$DOWNLOAD_DIR/agency.txt")" > "$(stat -c %y "$DEST_DIR/agency.txt")" ]]; then
    unzip -o "$ZIP_PATH" -d "$DEST_DIR"
else
    echo "Local gtfs_data/TFI/agency.txt is already up to date. Pass -f to unzip anyway."
    exit 0
fi

echo
echo "GTFS files are in $DEST_DIR"
echo "Import with: echo y | litestar importgtfs"
