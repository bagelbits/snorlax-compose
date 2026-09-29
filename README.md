# snorlax-compose

Docker Compose files for this homelab's stack, split by concern:

- docker-compose.auth.yml     - Caddy, Authelia, Postgres, Redis
- docker-compose.media.yml    - Plex, Tautulli, Overseerr
- docker-compose.torrents.yml - Radarr, Sonarr, qBittorrent, Prowlarr, Bazarr
- docker-compose.utils.yml    - Homepage, Watchtower, Unpackerr, Glances, Scrutiny, Portainer, Byparr

## Env setup

Secrets are not committed. Each ${VAR} in the compose files is filled in
from a local .env file at deploy time.

1. Copy the template:

       cp .env.example .env

2. Fill in real values in .env:

   - MY_DOMAIN                 - Caddy's domain, e.g. snorlax.media
   - POSTGRES_PASSWORD         - Postgres + Authelia storage
   - PLEX_CLAIM                - one-time claim token from plex.tv/claim, expires in ~4 min
   - WATCHTOWER_HTTP_API_TOKEN - Watchtower's HTTP API
   - SONARR_API_KEY            - copy from Sonarr's Settings > General
   - RADARR_API_KEY            - copy from Radarr's Settings > General

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
