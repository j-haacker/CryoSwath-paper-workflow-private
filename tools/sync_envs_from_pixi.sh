#!/usr/bin/env bash
set -euo pipefail

platform="linux-64"
envs=(default)

if [[ "$#" -gt 0 ]]; then
  envs=("$@")
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

strip_pip_deps() {
  local input_file="$1"
  local output_file="$2"

  awk '
    BEGIN { in_pip_block = 0 }
    /^- pip$/ { next }
    /^- pip:$/ { in_pip_block = 1; next }
    in_pip_block && /^  - / { next }
    in_pip_block { in_pip_block = 0 }
    { print }
  ' "$input_file" > "$output_file"
}

for env_name in "${envs[@]}"; do
  pixi workspace export conda-environment \
    --environment "$env_name" \
    --name "$env_name" \
    > "$tmp_dir/$env_name.yaml"

  strip_pip_deps "$tmp_dir/$env_name.yaml" "envs/$env_name.yaml"
done

env_args=()
for env_name in "${envs[@]}"; do
  env_args+=(--environment "$env_name")
done

pixi workspace export conda-explicit-spec \
  "$tmp_dir/specs" \
  --platform "$platform" \
  --ignore-pypi-errors \
  --ignore-source-errors \
  --frozen \
  "${env_args[@]}"

for env_name in "${envs[@]}"; do
  cp \
    "$tmp_dir/specs/${env_name}_${platform}_conda_spec.txt" \
    "envs/${env_name}.${platform}.pin.txt"
done
