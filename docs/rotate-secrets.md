# Rotating secrets

Runbook for replacing the credentials in `.env`. Use it after any leak, for
example a pasted `docker compose config` (see [Sharing config output](#sharing-config-output)).

Status: written from the compose files and Homepage config in this repo.
**Not run against the real server.** Menu paths in the apps can differ by
version; check them as you go.

Never write a secret into a doc, PR, commit or chat. `.env` lives only on the
server and is not in git.

## Things to know first

- `docker compose restart` does not re-read `.env`. Environment changes need a
  recreate: `docker compose up -d <service>` (Compose sees the changed env and
  recreates the container).
- `scripts/deploy.sh` runs `docker compose up -d` from cron every 10 minutes.
  A half-edited `.env` can be applied mid-rotation and recreate `homepage` or
  `unpackerr` with a mix of old and new values. Edit every variable for a
  rotation in one save, or pause the cron entry first.
- Changes in `config/homepage/*.yaml` are picked up by `docker compose restart
  homepage`, but the `HOMEPAGE_VAR_*` values come from the container
  environment, so they need the recreate.
- Most consumers are not in this repo. The links between Sonarr, Radarr,
  Prowlarr, Bazarr and Overseerr, and the qBittorrent login stored in the
  \*arr download-client settings, live in each app's own config volume and
  must be changed in its UI.

## Secret map

| Secret | `.env` variable | Consumers in this repo | Consumers in app UIs |
| --- | --- | --- | --- |
| qBittorrent username/password | `HOMEPAGE_VAR_QBITTORRENT_USERNAME`, `HOMEPAGE_VAR_QBITTORRENT_PASSWORD` | `homepage` widget (`config/homepage/services.yaml`) | Sonarr and Radarr download clients; Prowlarr download client if you added one |
| Sonarr API key | `SONARR_API_KEY` | `homepage` (as `HOMEPAGE_VAR_SONARR_KEY`), `unpackerr` (`UN_SONARR_0_API_KEY`) | Prowlarr (Apps), Bazarr (Sonarr), Overseerr (Sonarr server) |
| Radarr API key | `RADARR_API_KEY` | `homepage` (as `HOMEPAGE_VAR_RADARR_KEY`), `unpackerr` (`UN_RADARR_0_API_KEY`) | Prowlarr (Apps), Bazarr (Radarr), Overseerr (Radarr server) |
| Prowlarr API key | `HOMEPAGE_VAR_PROWLARR_KEY` | `homepage` widget | Sonarr/Radarr indexers synced from Prowlarr |
| Bazarr API key | `HOMEPAGE_VAR_BAZARR_KEY` | `homepage` widget | none |
| Overseerr API key | `HOMEPAGE_VAR_OVERSEERR_KEY` | `homepage` widget | none |
| Scrutiny key | `HOMEPAGE_VAR_SCRUTINY_KEY` | `homepage` widget | none |

`scripts/qbit-fix-paths.py` takes `QBT_USER`/`QBT_PASS` on its command line
(see its docstring). Nothing in the repo stores them, but clear any shell
history that holds them.

## Order of operations

1. Rotate the \*arr keys (Sonarr, Radarr) in each app first. The new key has
   to exist before it can go anywhere else.
2. Update the in-app links straight away (Prowlarr, Bazarr, Overseerr). Until
   you do, syncs and requests from those apps fail.
3. Rotate Prowlarr, then re-sync its indexers (below).
4. Rotate the other keys (Bazarr, Overseerr, Scrutiny) and the
   qBittorrent login.
5. Edit `.env` once with every new value, then recreate `homepage` and
   `unpackerr`.

Until step 5 finishes, Homepage widgets show errors and `unpackerr` logs
failed calls to Sonarr/Radarr. It retries (`UN_MAX_RETRIES`), so keep the gap
short. No downloads are lost; extraction resumes afterwards.

## Per secret

### Sonarr and Radarr API keys

1. In the app: Settings > General > Security > API Key, regenerate. Copy the
   new key somewhere that is not chat. The app restarts itself.
2. Update the apps that talk to it:
   - Prowlarr: Settings > Apps > Sonarr/Radarr, paste the key, Test, Save.
   - Bazarr: Settings > Sonarr / Radarr, paste the key, Test, Save.
   - Overseerr: Settings > Services > Sonarr/Radarr server, paste the key,
     Test, Save.
3. Set `SONARR_API_KEY` / `RADARR_API_KEY` in `.env`. One variable feeds both
   Homepage and `unpackerr`.
4. Recreate the consumers (see [Recreate](#recreate)).

### Prowlarr API key

1. Prowlarr: Settings > General > Security > API Key, regenerate.
2. Sonarr/Radarr hold Prowlarr-synced indexers that embed the old key. In
   Prowlarr: Settings > Apps, Test each app, then Sync App Indexers. Confirm
   the indexers in Sonarr/Radarr (Settings > Indexers) pass Test.
3. Set `HOMEPAGE_VAR_PROWLARR_KEY` in `.env`, then recreate `homepage`.

### Bazarr, Overseerr and Scrutiny keys

Only Homepage reads these.

- Bazarr: Settings > General > Security > API Key, regenerate.
- Overseerr: Settings > General > API Key, regenerate.
- Scrutiny: check where the value came from. Scrutiny has no built-in API key
  in the settings UI that this repo relies on. If the key is an
  auth token issued by something in front of it, rotate it there. If it is
  unused by the widget, remove the variable in a follow-up PR instead.

Set `HOMEPAGE_VAR_BAZARR_KEY`, `HOMEPAGE_VAR_OVERSEERR_KEY` and
`HOMEPAGE_VAR_SCRUTINY_KEY` in `.env`, then recreate `homepage`.

### qBittorrent username and password

1. qBittorrent: Options > Web UI > Authentication, set a new username and
   password, Save. Existing WebUI sessions end.
2. Update the clients that log in:
   - Sonarr and Radarr: Settings > Download Clients > qBittorrent, Test, Save.
   - Prowlarr: Settings > Download Clients, only if qBittorrent is listed.
3. Set `HOMEPAGE_VAR_QBITTORRENT_USERNAME` and
   `HOMEPAGE_VAR_QBITTORRENT_PASSWORD` in `.env`, then recreate `homepage`.

The container itself needs no recreate; the login is stored in
`qBittorrent.conf` on its config volume.

## Recreate

After saving `.env`:

```sh
docker compose up -d homepage unpackerr
```

- `homepage`: any `HOMEPAGE_VAR_*` change, including Sonarr/Radarr.
- `unpackerr`: only a Sonarr or Radarr key change.

Do not use `docker compose restart` for these; it keeps the old environment.

## Verify

Confirm the new values are live without printing them:

```sh
docker compose config --no-interpolate | grep -E 'HOMEPAGE_VAR|API_KEY'
```

That shows the `${VAR}` references only. To check that the recreated
containers picked up the change, compare against `.env` by eye on the server
rather than echoing values into a shared terminal.

Checklist:

- [ ] Old keys and the old qBittorrent login no longer work (try the old key
      against `http://<service>:<port>/api/...` from inside the `apps`
      network, expect 401).
- [ ] Homepage loads and every widget shows data: Scrutiny, Plex
      (Tautulli), Overseerr, Sonarr, Radarr, Bazarr, Prowlarr, qBittorrent.
- [ ] Prowlarr > Settings > Apps: Sonarr and Radarr both pass Test.
- [ ] Sonarr/Radarr > Settings > Indexers: synced indexers pass Test.
- [ ] Sonarr/Radarr > Settings > Download Clients: qBittorrent passes Test.
- [ ] Bazarr > Settings > Sonarr / Radarr: Test passes.
- [ ] Overseerr > Settings > Services: Sonarr and Radarr pass Test.
- [ ] `docker compose logs --tail=50 unpackerr` shows no auth errors.
- [ ] `docker compose ps` shows all services up.
- [ ] Shell history and scrollback that held old values are cleared.

## Sharing config output

`docker compose config` resolves `${VAR}` and prints every secret in plain
text. Do not paste it into chat, issues or PRs.

When you need to share the shape of the config:

```sh
docker compose config --no-interpolate
```

This keeps the `${VAR}` placeholders. Alternatively filter to the lines that
show where values come from, without the values:

```sh
docker compose config | grep source
```

`source` lines are bind mounts and secret files, not env values. Check the
output before sharing anyway; do not assume the filter is safe for other
patterns.

For a syntax check that prints nothing, use `docker compose config -q`.
