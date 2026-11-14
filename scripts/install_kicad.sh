#!/usr/bin/env bash
#
# Install KiCad MAJOR from the KiCad PPA on a GitHub runner and fail unless kicad-cli is that major version.
#
# ubuntu-latest is Ubuntu 26.04, whose amd64v3 architecture variant makes apt read only the binary-amd64v3 indexes.
# The KiCad PPA builds KiCad for amd64 only, so apt silently installed Ubuntu's KiCad 9 and every KiCad 10 file failed
# to load. Limiting the PPA source to the dpkg architecture fixes that (same fix as embedded-pro/kicad-bot v0.1.5).
#
# Usage: scripts/install_kicad.sh MAJOR [APT_INSTALL_ARGS...]   (default: --no-install-recommends kicad)
set -euo pipefail

major="${1:?usage: install_kicad.sh MAJOR [APT_INSTALL_ARGS...]}"
shift
if [ "$#" -eq 0 ]; then
  set -- --no-install-recommends kicad
fi
ppa="kicad/kicad-${major}.0-releases"

sudo add-apt-repository --yes "ppa:${ppa}"
arch="$(dpkg --print-architecture)"
for file in /etc/apt/sources.list.d/*.sources; do
  [ -e "$file" ] || continue
  grep -qF "/${ppa}/" "$file" || continue
  grep -q '^Architectures:' "$file" && continue
  sudo sed -i "/^Types:/a Architectures: ${arch}" "$file"
done
sudo apt-get update
sudo apt-get install --yes "$@"

installed="$(kicad-cli version)"
if [ "${installed%%.*}" != "${major}" ]; then
  echo "::error::expected KiCad ${major}, but kicad-cli reports ${installed}." >&2
  exit 1
fi
echo "KiCad ${installed}"
