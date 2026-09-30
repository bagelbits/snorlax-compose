#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
old=$(git rev-parse HEAD)
git pull --ff-only
docker compose config -q
docker compose up -d --remove-orphans
docker image prune -f
if ! git diff --quiet "$old" HEAD -- config/authelia; then
  docker compose restart auth
fi
if ! git diff --quiet "$old" HEAD -- config/glances; then
  docker compose restart monitoring
fi
if ! git diff --quiet "$old" HEAD -- config/caddy; then
  docker compose exec -T proxy caddy reload --config /etc/caddy/Caddyfile
fi
