# snorlax-compose

Docker Compose files for this homelab's stack, split by concern:

- docker-compose.auth.yml     - Caddy, Authelia, Postgres, Redis
- docker-compose.media.yml    - Plex, Tautulli, Overseerr
- docker-compose.torrents.yml - Radarr, Sonarr, qBittorrent, Prowlarr, Bazarr
- docker-compose.utils.yml    - Homepage, Watchtower, Unpackerr, Glances, Scrutiny, Portainer, FlareSolverr

## Env setup

Secrets are not committed. Each ${VAR} in the compose files is filled in
from a local .env file at deploy time.

1. Copy the template:

       cp .env.example .env

2. Fill in real values in .env:

   - MY_DOMAIN                 - Caddy's domain, e.g. snorlax.media
   - POSTGRES_PASSWORD         - Postgres + Authelia storage
   - REDIS_PASSWORD            - Redis + Authelia session store
   - PLEX_CLAIM                - one-time claim token from plex.tv/claim, expires in ~4 min
   - WATCHTOWER_HTTP_API_TOKEN - Watchtower's HTTP API
   - SONARR_API_KEY            - copy from Sonarr's Settings > General
   - RADARR_API_KEY            - copy from Radarr's Settings > General

3. Compose only auto-loads .env from the current working directory, not
   from wherever the -f files live. Either run compose from this
   directory, or pass --env-file explicitly.

## Running

    docker compose -f docker-compose.auth.yml \
      -f docker-compose.media.yml \
      -f docker-compose.torrents.yml \
      -f docker-compose.utils.yml \
      up -d --remove-orphans

Authelia's own secrets (JWT/session/storage keys, SMTP password) aren't in
.env - they're file-based (AUTHELIA_*_FILE vars pointing under
/opt/dockerapps/authelia/config/secrets/), managed on the host directly.
