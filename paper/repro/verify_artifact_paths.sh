#!/usr/bin/env sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
tmp="${TMPDIR:-/tmp}/cq-paper-artifacts.$$"
trap 'rm -f "$tmp"' EXIT

find "$root/paper" -type f \( -name '*.tex' -o -name '*.md' \) \
  -exec grep -hoE '(data|docs|paper/figures|figures)/[A-Za-z0-9_./*{}-]+' {} + \
  | sed 's/[).,;:]$//' \
  | sort -u > "$tmp"

missing=0
while IFS= read -r path; do
  case "$path" in
    *'*'*|*'{'*|*'}'*)
      continue
      ;;
  esac
  if [ "${path#figures/}" != "$path" ]; then
    candidate="$root/paper/$path"
  else
    candidate="$root/$path"
  fi
  if [ ! -e "$candidate" ]; then
    echo "MISSING: $path"
    missing=1
  fi
done < "$tmp"

if [ "$missing" -ne 0 ]; then
  exit 1
fi

echo "All referenced concrete artifact paths exist."
