#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
git pull --ff-only
docker compose config -q
docker compose up -d --remove-orphans
