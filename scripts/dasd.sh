#!/bin/bash

dasd_expected_files() {
  awk '$3 ~ /^dasd\// { sub(/^dasd\//, "", $3); print $3 }' \
    "$TK5/conf/tk5.cnf" "$TK5/conf/tk5-linux.cnf" 2>/dev/null | sort -u
}

dasd_expected_count() {
  dasd_expected_files | awk 'NF { count++ } END { print count + 0 }'
}

dasd_real_count() {
  local base="$1"
  local rel path size count=0

  [ -d "$base" ] || {
    echo 0
    return 0
  }

  while IFS= read -r rel; do
    [ -n "$rel" ] || continue
    path="$base/$rel"
    [ -f "$path" ] || continue
    size=$(wc -c < "$path" 2>/dev/null || echo 0)
    [ "$size" -gt 1024 ] || continue
    count=$((count + 1))
  done <<EOF
$(dasd_expected_files)
EOF

  echo "$count"
}

dasd_has_real_set() {
  local base="$1"
  local expected

  expected=$(dasd_expected_count)
  [ "$expected" -gt 0 ] || return 1
  [ "$(dasd_real_count "$base")" -eq "$expected" ]
}

dasd_seed_backup() {
  local source_dir="${1:-$TK5/dasd}"
  local backup_dir="${2:-$TK5/dasd_backup}"

  mkdir -p "$backup_dir"
  cp -f "$source_dir/"* "$backup_dir/" 2>/dev/null || true
}

dasd_sync_from_lfs() {
  command -v git >/dev/null 2>&1 || return 1
  git -C "$DIR" rev-parse --show-toplevel >/dev/null 2>&1 || return 1
  git -C "$DIR" lfs version >/dev/null 2>&1 || return 1
  git -C "$DIR" lfs install --local >/dev/null 2>&1 || return 1
  git -C "$DIR" lfs pull || return 1
}
