#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
old=$(git rev-parse HEAD)
git pull --ff-only
docker compose config -q
docker compose up -d --remove-orphans
docker image prune -f
if ! git diff --quiet "$old" HEAD -- config/caddy; then
  docker compose exec -T proxy caddy reload --config /etc/caddy/Caddyfile
fi
