#!/bin/bash
# Build then RLVR - full pipeline
cd "$(dirname "$0")/../.."

echo "=== Waiting for build to complete ==="
while pgrep -f "build_full.sh" > /dev/null; do
    sleep 60
    echo "Build still running... $(date '+%H:%M')"
done

echo ""
echo "=== Build complete, starting RLVR ==="
echo "Started: $(date)"

# Make sure TK5 is running
if ! curl -s "http://localhost:8038/" > /dev/null 2>&1; then
    echo "Starting TK5..."
    cd tk5/mvs-tk5 && ./start_tk5.sh &
    cd ../..
    sleep 90
fi

# Run RLVR
./scripts/training/rlvr_auto.sh

echo ""
echo "=== RLVR Complete ==="
echo "Finished: $(date)"
