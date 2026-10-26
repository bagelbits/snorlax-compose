# Unpackerr 0.16.1 -> v1

This upgrades the pinned golift image to v1.0.0 and persists `/config`.
Sonarr/Radarr configuration, download paths, UID/GID and extraction timers
stay unchanged. **The webserver is disabled for now** with
`UN_WEBSERVER_LISTEN_ADDR=`: v1 otherwise listens on `0.0.0.0:5656` by
default. No Caddy route, published port, DNS or network change is needed.

Host preparation and live checks are manual. Merging deploys through
`scripts/deploy.sh` within 10 minutes. Do not merge until the directory
below is ready. These instructions have not been run against the live host.

## Before merge: prepare persistent storage

Run on the server, not on a development machine:

```sh
mkdir -p /opt/dockerapps/unpackerr
chown 1000:1002 /opt/dockerapps/unpackerr
chmod 0750 /opt/dockerapps/unpackerr
```

This matches the existing container `user: 1000:1002`. If the directory
already contains configuration/history, back it up and check those files
are writable by UID 1000 too; do not overwrite them. Mount the whole
directory read-write, not a read-only config file: Unpackerr writes
`/config/unpackerr.conf` and future UI saves would replace that file.

Keep appdata and its backups out of Git and restrict access: configuration
can contain API keys and history includes download paths.

## Configuration and history

The existing `UN_SONARR_0_*`, `UN_RADARR_0_*`, `UN_START_DELAY`,
`UN_RETRY_DELAY` and `UN_MAX_RETRIES` stay in Compose. Environment variables
override file values. Do not remove them in this rollout: startup-generated
configuration is not proof that environment-owned settings have been
migrated into it. A later migration must first write and verify equivalent
persistent settings, back them up, and only then remove the corresponding
variables and recreate Unpackerr. Those fields remain locked if the UI is
enabled in the future.

With the default stdout logging, history is stored beside the config as
`/config/unpackerr.history.jsonl`. Both files survive container recreation.
If `log_file` is changed later, history follows its directory; choose a
persistent writable path. History retention defaults to 400 completed/
failed items, plus eligible in-progress records.

No Whisparr, watched folders or metrics are configured here; their v1
migrations are not part of this change.

## Rollout verification on the host

After preparing storage and merging, inspect the next cron deploy or run
the usual deployment process deliberately. `deploy.sh` validates Compose
and recreates Unpackerr. Caddy and Authelia configuration are unchanged.

```sh
cd /opt/dockerapps/docker-compose
docker compose config -q
docker compose ps unpackerr
docker compose logs --tail=100 unpackerr
```

Verify the following before calling the rollout successful:

1. Logs report v1.0.0, `Webserver Disabled`, and the existing Sonarr/Radarr
   instances, with no configuration/history permission errors. Confirm
   `/opt/dockerapps/unpackerr/unpackerr.conf` exists and is writable by
   UID 1000. Keep the environment settings even if their values are absent
   from this file.
2. `docker inspect unpackerr` shows the intended `/config` and download
   mounts and no host binding for 5656. From an existing `apps` container
   with an HTTP client, a request to `http://unpackerr:5656/api/auth/me`
   must fail to connect, not serve the UI/API. Supplying `Remote-User` or
   other identity headers must not change that. No proxy login or WebSocket
   check is applicable while the listener is disabled.
3. Allow a completed archived download from **each** of Sonarr and Radarr
   to extract and import normally. Verify paths, permissions, extraction
   delay/retry behavior and cleanup. Confirm `unpackerr.history.jsonl`
   appears under the appdata directory and contains completed entries.
4. When no extraction is active, record a checksum of `unpackerr.conf`
   and note completed history entries, then run:

   ```sh
   docker compose up -d --no-deps --force-recreate unpackerr
   ```

   Confirm the same configuration and completed history remain, both
   Starr instances still poll, and the webserver remains disabled.
   Continued normal writes can update history; it need not be byte-identical.

Local Compose validation and isolated container checks cannot establish
host permissions or real Sonarr/Radarr extraction behavior. The live
checks above remain required even when CI is green.

## Local validation

Compose validation passes with `.env.example`; the resolved listener value
is an empty string, `/config` is writable, and no host port is published.
Using the pinned v1 image in an isolated container as UID 1000:GID 1002
reproduced the default 5656 listener and startup-generated configuration.
Recreating it twice with the explicit empty listener kept the port closed,
even with the saved enabled-listener config and a forged identity header.
The config file and a seeded completed-history record survived recreation.
This was not a real extraction test or a live-host deployment.

## Enabling the UI later

Defer the UI rather than trust all of `apps`, a Docker gateway or broad
private address space. In v1.0.0, `webserver.upstreams` accepts literal
IP/CIDR entries only; a Docker service name is not resolved. Header login
(`webauth:Remote-User`) requires a trusted TCP peer.

Revisit when upstream supports tracking proxy service names safely, or
when a narrowly scoped fixed-IP network is explicitly desired. Before
enabling it, add a Caddy/Authelia route with client identity-header
stripping, choose exact proxy trust, review the user audience (header-auth
users are admins unless roles are configured), and check DNS, login,
unauthenticated/header-spoof denial and WebSocket live updates. Keep
Unpackerr's port unpublished. Do not simply remove the disabling variable:
that would enable a listener reachable by other `apps` containers.

## Rollback

If extraction fails, preserve the new appdata and logs for diagnosis.
Pause cron before any temporary host rollback so it cannot immediately
reapply the upgrade. Revert the upgrade PR through the normal PR process,
then deploy the revert to restore the 0.16.1 image and original mount list.
Keep the original Starr environment values and download mount unchanged.
The unmounted v1 appdata can stay for a corrected rollout; do not feed its
rewritten config into 0.16.1. Resume cron once the intended revision is
deployed.

## References

- [Upgrading to v1](https://unpackerr.zip/docs/install/upgrading/)
- [Web UI and reverse proxy](https://unpackerr.zip/docs/install/web-ui/)
- [v1.0.0 listener and proxy IP parsing](https://github.com/Unpackerr/unpackerr/blob/v1.0.0/pkg/unpackerr/webserver.go)
- [v1.0.0 header authentication](https://github.com/Unpackerr/unpackerr/blob/v1.0.0/pkg/unpackerr/auth.go)
- [v1.0.0 history location](https://github.com/Unpackerr/unpackerr/blob/v1.0.0/pkg/unpackerr/historyfile.go)
