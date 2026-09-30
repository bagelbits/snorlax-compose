# snorlax-compose

Docker Compose files for this homelab's stack, split by concern:

- docker-compose.auth.yml     - Caddy, Authelia, Postgres, Redis
- docker-compose.media.yml    - Plex, Tautulli, Overseerr
- docker-compose.torrents.yml - Radarr, Sonarr, qBittorrent, Prowlarr, Bazarr
- docker-compose.utils.yml    - Homepage, Unpackerr, Glances, Scrutiny, Byparr, socket-proxy
- config/caddy/Caddyfile      - Caddy routes, mounted into the proxy container
- scripts/                    - deploy.sh (cron) and one-off helpers
- renovate.json               - Renovate update rules
- .github/workflows/ci.yml    - validates compose and lints scripts on every PR

## Env setup

Secrets are not committed. Each ${VAR} in the compose files is filled in
from a local .env file at deploy time.

1. Copy the template:

       cp .env.example .env

2. Fill in real values in .env:

   - SMTP_USERNAME             - Authelia's SMTP login (password is a secrets file)
   - MY_DOMAIN                 - Caddy's domain, e.g. snorlax.media
   - POSTGRES_PASSWORD         - Postgres + Authelia storage
   - PLEX_CLAIM                - one-time claim token from plex.tv/claim, expires in ~4 min
   - SONARR_API_KEY            - copy from Sonarr's Settings > General
   - RADARR_API_KEY            - copy from Radarr's Settings > General
   - HOMEPAGE_VAR_*            - widget keys for Homepage (Tautulli,
                                 Overseerr, Bazarr, Prowlarr) and the
                                 qBittorrent login. Sonarr/Radarr reuse the
                                 API keys above.

## Running

compose.yaml includes every docker-compose.*.yml file, so from this
directory:

    docker compose up -d --remove-orphans

Or from anywhere:

    docker compose --env-file /opt/dockerapps/docker-compose/.env \
      -f /opt/dockerapps/docker-compose/compose.yaml up -d --remove-orphans

`include` needs Docker Compose 2.20 or newer. The project name stays
`media` (set in compose.yaml) so existing containers are reused.

Authelia's own secrets (JWT/session/storage keys, SMTP password) aren't in
.env - they're file-based (AUTHELIA_*_FILE vars pointing under
/opt/dockerapps/authelia/config/secrets/), managed on the host directly.
Redis reads its password from the same REDIS_PASSWORD file Authelia uses.

## Networks

- `auth` - Caddy, Authelia, Postgres, Redis. Caddy also joins `apps`.
- `apps` - everything else.
- `docker-api` - internal only: socket-proxy, Glances and Homepage.
  socket-proxy (read-only, containers/images) is the only thing that
  touches the Docker socket. Homepage reaches it through
  config/homepage/docker.yaml and `server: socket-proxy` on each service.

## Updates

Renovate (renovate.json) replaces Watchtower. It first opens a PR pinning every
image by digest. After that nothing changes until a Renovate PR is merged, and
merging deploys it within 10 minutes (see Auto-deploy).

- Saturday before 6am Pacific: one grouped PR with all routine image updates.
- Caddy, Authelia, Postgres, Redis and Plex get their own PRs, so review them
  one at a time.
- A Postgres major bump needs a dump and restore first. Do not merge one
  until you have done that.
- Unused images are pruned after each deploy.

## Auto-deploy

scripts/deploy.sh pulls main (fast-forward only), validates the config, and
runs `docker compose up -d --remove-orphans`. The host is Alpine (no
systemd), so root's cron runs it every 10 minutes. Add with `crontab -e`:

    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
    */10 * * * * flock -n /tmp/snorlax-deploy.lock /opt/dockerapps/docker-compose/scripts/deploy.sh >> /var/log/snorlax-deploy.log 2>&1

Make sure crond starts at boot: `rc-update add crond && rc-service crond start`.
Read results with `tail /var/log/snorlax-deploy.log`.

Keep main PR-only with CI required, since a merge deploys itself. Major
bumps such as Postgres still need a manual migration: see
docs/postgres-redis-upgrade.md.

## Authelia

config/authelia/configuration.yml is mounted read-only over the host's
/opt/dockerapps/authelia/config/configuration.yml. Secrets stay out of it
(AUTHELIA_*_FILE env vars). users_database.yml and secrets/ stay on the host,
since they hold password hashes and keys. deploy.sh restarts `auth` when the
file changes, because Authelia does not reload its config.

## Homepage

config/homepage/{settings,services,widgets,docker}.yaml are mounted read-only over
the host's /opt/dockerapps/homepage, which still supplies bookmarks.yaml,
logs/ and custom assets. Keys live in .env as HOMEPAGE_VAR_* and
are referenced as `{{HOMEPAGE_VAR_NAME}}` in the YAML. deploy.sh restarts
`homepage` when config/homepage changes.

## Glances

config/glances/glances.conf is mounted read-only as /glances/conf. deploy.sh
restarts `monitoring` when it changes.

## Caddy

config/caddy/Caddyfile is mounted read-only as a directory at /etc/caddy. Edit
it here and merge. CI validates it, and deploy.sh reloads Caddy when the file
changed. To reload by hand:

    docker compose exec proxy caddy reload --config /etc/caddy/Caddyfile

## Scripts

qbit-fix-paths.py is a one-off helper, run inside a container with python3.
It prints a plan by default; pass --apply to act. See --help for usage.

- deploy.sh         - pull main and apply it (run by cron, see Auto-deploy)
- qbit-fix-paths.py - repoint qBittorrent torrents from /torrents to /media/torrents
