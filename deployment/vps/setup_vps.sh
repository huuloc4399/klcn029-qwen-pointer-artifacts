#!/usr/bin/env bash
# One-time setup of an Ubuntu 22.04/24.04 x86_64 VPS for the demo: Docker + Compose, swap, firewall.
# Usage on the VPS:  bash setup_vps.sh   (then log out and back in so the docker group applies)
set -euo pipefail

if [ "$(uname -m)" != "x86_64" ]; then
  echo "Expected an x86_64 VPS, got $(uname -m)." >&2
  exit 1
fi
. /etc/os-release
echo "OS: $PRETTY_NAME"
if [ "$(systemd-detect-virt 2>/dev/null || true)" = "openvz" ] || [ "$(systemd-detect-virt 2>/dev/null || true)" = "lxc" ]; then
  echo "This VPS is $(systemd-detect-virt): Docker usually does not run there. Ask the provider for a KVM VPS." >&2
  exit 1
fi

sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io docker-compose-v2 ufw
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"

# 6 GB swap: the model (~4 GB) plus OCR (~3 GB) can exceed 8 GB RAM for a moment.
if ! swapon --show | grep -q /swapfile; then
  sudo fallocate -l 6G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi
echo 'vm.swappiness=10' | sudo tee /etc/sysctl.d/99-klcn029.conf >/dev/null
sudo sysctl --system >/dev/null

# Firewall: SSH, HTTP, HTTPS only. Docker publishes 80/443 for Caddy; the API port stays internal.
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

echo
lscpu | grep -E 'Model name|^CPU\(s\)|Flags' | sed -E 's/(Flags:).*(avx512f|avx2).*/\1 ... \2 .../' | head -3
free -h
echo
echo "Done. Log out and back in, then: cd ~/klcn029 && cp .env.example .env && nano .env"
