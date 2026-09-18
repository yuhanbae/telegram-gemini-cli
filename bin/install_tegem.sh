# tegem installer (Termux)
#
# Use this to create / update the `tegem` launcher shortcut:
#   1. It copies this repo's canonical launcher (bin/tegem.template) to
#      /data/data/com.termux/files/usr/bin/tegem
#   2. Makes it executable
#
# The launcher itself is committed in the repo so it survives re-clones.

set -e

REPO="$(cd "$(dirname "$0")" && pwd)"
DEST="/data/data/com.termux/files/usr/bin/tegem"

cp "$REPO/bin/tegem.template" "$DEST"
chmod +x "$DEST"
echo "Installed tegem -> $DEST"
echo "Run it with:  tegem        (foreground)"
echo "Or:           nohup tegem > ~/telegram-gemini-cli/logs/bot.log 2>&1 &"
