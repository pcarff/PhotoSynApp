#!/usr/bin/env bash
set -euo pipefail

# PhotoSynApp - Sync Photos from Synology NAS to Cortex (/Workspaces/Photos)
# Usage: ./scripts/sync_from_nas.sh [laura|paul|historical|all]

TARGET="${1:-all}"
DEST_BASE="/Workspaces/Photos"
TIMESTAMP="$(date +'%Y-%m-%d_%H%M%S')"
ARCHIVE_DIR="$DEST_BASE/_Deleted_Archive/$(date +'%Y-%m-%d')"

mkdir -p "$DEST_BASE/Laura_Only" "$DEST_BASE/Paul_Combined" "$DEST_BASE/Historical_Master"

# Standard exclusions for Synology metadata and OS junk
COMMON_EXCLUDES=(
    --exclude '@eaDir'
    --exclude '@eaDir/**'
    --exclude '#recycle'
    --exclude '#recycle/**'
    --exclude '@tmp'
    --exclude '@tmp/**'
    --exclude '.DS_Store'
    --exclude '._*'
    --exclude 'Thumbs.db'
    --exclude 'desktop.ini'
)

# Safe deletion mirroring: cleans up removed files from active tree, but archives them safely
SAFE_DELETE_OPTS=(
    --delete
    --backup
    --backup-dir="$ARCHIVE_DIR"
)

sync_laura() {
    echo "=========================================================="
    echo "Syncing Laura's Photos (NAS -> Cortex)..."
    echo "Source: synology:/volume1/PhotoSync/Laura/ALL_PHOTOS/"
    echo "Dest:   $DEST_BASE/Laura_Only/"
    echo "=========================================================="
    rsync -avh --info=progress2 --stats \
        "${COMMON_EXCLUDES[@]}" \
        "${SAFE_DELETE_OPTS[@]}" \
        synology:/volume1/PhotoSync/Laura/ALL_PHOTOS/ "$DEST_BASE/Laura_Only/"
}

sync_paul() {
    echo "=========================================================="
    echo "Syncing Paul's Combined Photos (NAS -> Cortex)..."
    echo "Source: synology:/volume1/PhotoSync/ALL_PHOTOS/"
    echo "Dest:   $DEST_BASE/Paul_Combined/"
    echo "=========================================================="
    rsync -avh --info=progress2 --stats \
        "${COMMON_EXCLUDES[@]}" \
        "${SAFE_DELETE_OPTS[@]}" \
        synology:/volume1/PhotoSync/ALL_PHOTOS/ "$DEST_BASE/Paul_Combined/"
}

sync_historical() {
    echo "=========================================================="
    echo "Syncing Historical Master Photos (NAS -> Cortex)..."
    echo "Source: synology:/volume1/Photos/"
    echo "Dest:   $DEST_BASE/Historical_Master/"
    echo "=========================================================="
    rsync -avh --info=progress2 --stats \
        "${COMMON_EXCLUDES[@]}" \
        "${SAFE_DELETE_OPTS[@]}" \
        synology:/volume1/Photos/ "$DEST_BASE/Historical_Master/"
}

case "$TARGET" in
    laura)
        sync_laura
        ;;
    paul)
        sync_paul
        ;;
    historical)
        sync_historical
        ;;
    all)
        sync_laura
        sync_paul
        sync_historical
        ;;
    *)
        echo "Unknown target: $TARGET. Choose: laura, paul, historical, or all."
        exit 1
        ;;
esac

# Clean up empty archive dir if nothing was deleted/backed up
if [ -d "$ARCHIVE_DIR" ] && [ -z "$(ls -A "$ARCHIVE_DIR" 2>/dev/null)" ]; then
    rmdir "$ARCHIVE_DIR" 2>/dev/null || true
fi

echo ""
echo "Sync completed successfully at $(date)!"
