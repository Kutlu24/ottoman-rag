#!/bin/sh
# Runs as root (see Dockerfile) so it can fix ownership on a freshly-mounted
# volume before dropping to the non-root "user" for the actual server
# process - same pattern as fundraising-assistant's docker-entrypoint.sh
# and dhra's (added at the same time, for the same reason).
#
# Not yet observed as a live crash here the way it was for dhra (nothing
# in this app's own startup path writes to backend/src/backend/config.py's
# data dir eagerly - METADATA_DB_PATH/CHROMA_DB_DIR/RAW_IMAGES_DIR are only
# touched on first real ingest/upload), but it's the same root cause: a
# Docker named volume's mount point is created root:root regardless of the
# image's own directory ownership, and this container's real point (OCR
# uploads under actual RAM, unlike Render's 512MB) is exactly the workload
# that would hit it. Fixed proactively rather than waiting for it to
# surface mid-test.
set -e

mkdir -p "$HOME/app/data"
chown -R user:user "$HOME/app/data"

exec su -s /bin/sh user -c "python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-7860} --app-dir backend/src"
