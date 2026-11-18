#!/bin/bash
# Finder opens .command files in Terminal. Keep failures visible there.
set -euo pipefail
trap 'status=$?; if [ "$status" -ne 0 ] && [ -t 0 ]; then read -r -p "Press Return to close…" _reply; fi' EXIT

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

if [ "$(/usr/bin/uname -s)" != "Darwin" ]; then
    echo "This launcher requires macOS." >&2
    exit 1
fi

candidates=("$PWD/.runtime/bin/python")
for name in python3.11 python3 python; do
    candidate="$(command -v "$name" || true)"
    if [ -n "$candidate" ]; then candidates+=("$candidate"); fi
done
candidates+=(
    /opt/homebrew/bin/python3.11
    /usr/local/bin/python3.11
    /Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11
)

for candidate in "${candidates[@]}"; do
    if [ -x "$candidate" ] && "$candidate" -c \
        'import platform, struct, sys; assert sys.version_info[:2] == (3, 11); assert struct.calcsize("P") == 8; assert platform.machine().lower() == "arm64"' \
        >/dev/null 2>&1; then
        "$candidate" -B -m modules.macos_launcher "$@"
        exit $?
    fi
done

echo "Diaphragm requires Apple Silicon and arm64 Python 3.11." >&2
echo "Install Python 3.11 from python.org, or run: brew install python@3.11" >&2
echo "Then run launch.command again. Existing environments were left untouched." >&2
exit 1
