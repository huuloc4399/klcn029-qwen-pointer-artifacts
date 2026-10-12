#!/usr/bin/env bash
# One-time setup of an Oracle Cloud Ubuntu 24.04 aarch64 VM for the extraction API:
# Docker + Compose, and ports 80/443 opened in the VM firewall (Oracle's Ubuntu images
# reject everything except SSH in iptables, in addition to the VCN security list).
# Usage on the VM: bash setup_vm.sh   (then log out and back in for the docker group)
set -euo pipefail

if [ "$(uname -m)" != "aarch64" ]; then
  echo "Expected an Ampere A1 (aarch64) VM, got $(uname -m)." >&2
  exit 1
fi

sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io docker-compose-v2 iptables-persistent
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"

# Insert ACCEPT rules before Oracle's catch-all REJECT so Caddy can serve HTTP(S).
reject_line=$(sudo iptables -L INPUT --line-numbers -n | awk '$2 == "REJECT" {print $1; exit}')
for port in 80 443; do
  if ! sudo iptables -C INPUT -p tcp -m state --state NEW --dport "$port" -j ACCEPT 2>/dev/null; then
    sudo iptables -I INPUT "${reject_line:-1}" -p tcp -m state --state NEW --dport "$port" -j ACCEPT
  fi
done
sudo netfilter-persistent save

echo "Done. Log out and back in, then: cd ~/klcn029-api && cp .env.example .env && nano .env"
