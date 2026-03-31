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

dasd_restore_from_archive() {
  local archive="$1"
  local source_dir="${2:-$TK5/dasd}"
  local backup_dir="${3:-$TK5/dasd_backup}"
  local tmp_template tmp_dir extracted=""

  [ -f "$archive" ] && [ -s "$archive" ] || return 1

  tmp_template="${TMPDIR:-/tmp}"
  tmp_template="${tmp_template%/}/mainframe-ai-dasd.XXXXXX"
  tmp_dir=$(mktemp -d "$tmp_template") || return 1

  if ! tar xzf "$archive" -C "$tmp_dir" >/dev/null 2>&1; then
    rm -rf "$tmp_dir"
    return 1
  fi

  if [ -d "$tmp_dir/dasd" ]; then
    extracted="$tmp_dir/dasd"
  elif [ -d "$tmp_dir/tk5/mvs-tk5/dasd" ]; then
    extracted="$tmp_dir/tk5/mvs-tk5/dasd"
  fi

  if [ -z "$extracted" ]; then
    rm -rf "$tmp_dir"
    return 1
  fi

  mkdir -p "$source_dir" "$backup_dir"
  cp -f "$extracted/"* "$backup_dir/" 2>/dev/null || true
  cp -f "$backup_dir/"* "$source_dir/" 2>/dev/null || true
  rm -rf "$tmp_dir"

  dasd_has_real_set "$source_dir"
}

dasd_restore_from_candidates() {
  local source_dir="${1:-$TK5/dasd}"
  local backup_dir="${2:-$TK5/dasd_backup}"
  local archive

  shift 2
  for archive in "$@"; do
    [ -n "$archive" ] || continue
    if dasd_restore_from_archive "$archive" "$source_dir" "$backup_dir"; then
      printf '%s\n' "$archive"
      return 0
    fi
  done

  return 1
}

dasd_download_archive() {
  local url="$1"
  local output="$2"

  [ -n "$url" ] || return 1
  mkdir -p "$(dirname "$output")"
  rm -f "$output"

  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url" -o "$output" >/dev/null 2>&1 || return 1
  elif command -v wget >/dev/null 2>&1; then
    wget -q "$url" -O "$output" >/dev/null 2>&1 || return 1
  else
    return 1
  fi

  [ -s "$output" ]
}

dasd_sync_from_lfs() {
  command -v git >/dev/null 2>&1 || return 1
  git -C "$DIR" rev-parse --show-toplevel >/dev/null 2>&1 || return 1
  git -C "$DIR" lfs version >/dev/null 2>&1 || return 1
  git -C "$DIR" lfs install --local >/dev/null 2>&1 || return 1
  git -C "$DIR" lfs pull || return 1
}
