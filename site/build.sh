#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Full history is needed for gather_links.py
if git rev-parse --is-shallow-repository 2>/dev/null | grep -q true; then
  echo "Unshallowing repository..."
  git fetch --unshallow
fi

python3 site/gather_links.py

if [ "${GENERATE_LLM_DOCS:-0}" = "1" ]; then
  echo "Generating LLM docs..."
  python3 site/write_docs.py
fi

python3 site/build_colophon.py
python3 site/build_dates.py
python3 site/build_index.py
python3 site/build_by_month.py

# Inject footer.js before </body> in every tool html file
FOOTER_HASH=$(git rev-parse HEAD:footer.js 2>/dev/null || echo "v1")

for f in */index.html; do
  grep -q "footer.js" "$f" && continue
  awk -v hash="$FOOTER_HASH" '
    /<\/body>/ && !injected {
      print "<script src=\"../footer.js?v=" hash "\"></script>"
      injected=1
    }
    { print }
  ' "$f" > "$f.tmp" && mv "$f.tmp" "$f"
  echo "  Injected footer → $f"
done

python3 site/build_redirects.py

echo "Build complete."
