#!/usr/bin/env bash
set -euo pipefail

LIGHTPANDA_VERSION="nightly"
BASE_URL="https://github.com/lightpanda-io/browser/releases/download/${LIGHTPANDA_VERSION}"
DEST="/usr/local/bin/lightpanda"

if [ $# -ge 2 ]; then
    OS="$1"
    case "$2" in
        amd64|x86_64)  ARCH="x86_64-${OS}" ;;
        arm64|aarch64) ARCH="aarch64-${OS}" ;;
        *)
            echo "Unsupported architecture: $2"
            exit 1
            ;;
    esac
elif [ $# -ge 1 ]; then
    ARCH="$1"
else
    OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
    case "$(uname -m)" in
        x86_64|amd64)  ARCH="x86_64-${OS}" ;;
        aarch64|arm64) ARCH="aarch64-${OS}" ;;
        *)
            echo "Unsupported architecture: $(uname -m)"
            exit 1
            ;;
    esac
fi

BINARY="lightpanda-${ARCH}"
DOWNLOAD_URL="${BASE_URL}/${BINARY}"

echo "Downloading Lightpanda (${BINARY})..."
echo "  URL: ${DOWNLOAD_URL}"
echo "  Dest: ${DEST}"

if command -v curl &> /dev/null; then
    curl -fL --progress-bar -o "${DEST}" "${DOWNLOAD_URL}"
elif command -v wget &> /dev/null; then
    wget -q --show-progress -O "${DEST}" "${DOWNLOAD_URL}"
else
    echo "Error: curl or wget is required."
    exit 1
fi

chmod +x "${DEST}"

echo "Lightpanda installed successfully."
"${DEST}" version 2>/dev/null || true
