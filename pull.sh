#!/usr/bin/env bash
# pull.sh — Pull all repos in kali_combined monorepo
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "═══════════════════════════════════════"
echo " 🔄 Pulling kali_combined monorepo"
echo "═══════════════════════════════════════"

# Pull main monorepo
echo ""
echo "▸ Main monorepo ($SCRIPT_DIR)"
git pull --rebase || echo "⚠️  Main pull failed, continuing..."

# Repos to pull (directory → git URL)
REPOS=(
  "kali_core_emulator|https://github.com/zombiegirlcz/kali_core_emulator.git"
  "kali_ai_assistant|https://github.com/zombiegirlcz/kali_ai_assistant.git"
  "kali_GUI|https://github.com/zombiegirlcz/kali_GUI.git"
)

for entry in "${REPOS[@]}"; do
  IFS='|' read -r dir url <<< "$entry"
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "▸ $dir"

  if [ -d "$dir/.git" ]; then
    cd "$dir"
    git pull --rebase || echo "⚠️  Pull failed for $dir"
    cd "$SCRIPT_DIR"
  else
    echo "  ⏬ Not cloned yet → cloning..."
    git clone "$url" "$dir"
  fi
done

echo ""
echo "═══════════════════════════════════════"
echo " ✅ All done!"
echo "═══════════════════════════════════════"
