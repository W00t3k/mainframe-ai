#!/usr/bin/env bash
set -u

print_check() {
  printf '\n== %s ==\n' "$1"
}

check_command() {
  local name="$1"
  local hint="$2"

  if command -v "$name" >/dev/null 2>&1; then
    printf '[ok] %s: %s\n' "$name" "$(command -v "$name")"
    return 0
  fi

  printf '[warn] %s not found. %s\n' "$name" "$hint"
  return 1
}

print_check "Apple Silicon Readiness"
arch="$(uname -m)"
printf 'uname -m: %s\n' "$arch"
if [ "$arch" != "arm64" ]; then
  printf '[warn] This machine does not report arm64. These docs target Apple Silicon Macs.\n'
else
  printf '[ok] Apple Silicon architecture detected.\n'
fi

print_check "Required Tools"
check_command brew "Install Homebrew from https://brew.sh/ before following the macOS setup docs."
check_command python3 "Install Python with Homebrew: brew install python"
check_command git "Install Git with Homebrew: brew install git"

if check_command ollama "Install Ollama with Homebrew: brew install ollama"; then
  print_check "Ollama Models"
  ollama_output="$(ollama list 2>&1)"
  ollama_status=$?
  if [ "$ollama_status" -eq 0 ]; then
    printf '%s\n' "$ollama_output"
    printf '[ok] Ollama responded to ollama list.\n'
  else
    printf '[warn] ollama list failed with exit status %s.\n' "$ollama_status"
    printf '[warn] Start Ollama with: ollama serve\n'
    printf '[warn] First diagnostic lines:\n'
    printf '%s\n' "$ollama_output" | sed -n '1,8p'
  fi
fi

print_check "Friendly Next Steps"
printf '1. Pull Mistral: ollama pull mistral\n'
printf '2. Optional BigIron.ai wrapper: ollama create bigiron-mistral -f configs/ollama/Modelfile.bigiron-mistral\n'
printf '3. Use the local model: export OLLAMA_MODEL=bigiron-mistral\n'
printf '4. Create a venv and install deps: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt\n'
printf '5. Start the app: ./start.sh\n'
printf '\nThis script only checks and reports. It does not install packages, use sudo, or change system state.\n'
