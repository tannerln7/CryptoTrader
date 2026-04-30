#!/usr/bin/env bash
set -euo pipefail

# Run this from the repo's .github directory:
#   cd .github && ./init_skills.sh

BASE_DIR="skills"

# Skill directory names (must match the "name:" in each SKILL.md frontmatter later)
SKILLS=(
  "chain-coengineer"
  "chain-implementer"
  "shared-research"
)

mkdir -p "$BASE_DIR"

for skill in "${SKILLS[@]}"; do
  dir="$BASE_DIR/$skill"
  file="$dir/SKILL.md"
  mkdir -p "$dir"

  if [[ -f "$file" ]]; then
    echo "exists: $file"
  else
    # Create empty file with a minimal header scaffold (safe to overwrite later manually)
    cat > "$file" <<EOF
---
name: $skill
description: TODO
user-invokable: true
disable-model-invocation: false
argument-hint: "TODO"
---

EOF
    echo "created: $file"
  fi
done

echo "Done. Created skill directories under .github/$BASE_DIR/"