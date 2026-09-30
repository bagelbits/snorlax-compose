# Cleanup after the Postgres 18 / Redis 8 migration

The migration in [postgres-redis-upgrade.md](postgres-redis-upgrade.md)
finished on 2026-09-30. The PG15 rollback assets are kept for a week, then
deleted.

**Earliest safe date: 2026-10-07.** Nothing here has been run; do it on the
server, in `/opt/dockerapps/docker-compose`.

## What gets deleted

| Path | What it is |
|------|------------|
| `/opt/dockerapps/authelia/postgres` | old PG15 data dir |
| `/opt/dockerapps/authelia/postgres15-cold` | cold copy of the PG15 data dir |
| `/opt/dockerapps/authelia/backups` | `authelia-pg15.dump`, `counts-before.txt`, `counts-after.txt` |

## 1. Preconditions

All must hold. If any fails, stop and leave the old assets in place.

- Authelia login works through Caddy, including your TOTP/WebAuthn device.
- `docker compose ps` shows `database`, `redis` and `auth` healthy.
- No auth errors in the last week:

  ```sh
  docker compose logs auth --since 7d | grep -iE 'error|fatal'
  ```

  Expect no output, or only errors you can explain.

## 2. Take a new baseline backup first

`backups` is about to be deleted, and it holds the only dump. Write the new
one somewhere else:

```sh
N=/opt/dockerapps/authelia/backups-pg18; mkdir -p "$N"
docker compose exec -T database pg_dump -U authelia -d authelia -Fc > "$N/authelia-pg18-$(date +%F).dump"
docker run --rm -i postgres:18 pg_restore --list < "$N"/authelia-pg18-*.dump | head
ls -lh "$N"
```

Do not continue unless the listing works and the file is non-trivial in size.

## 3. Delete the old assets

`ls` each path first and check it is what you expect. `ls` failing means the
path is wrong: do not run the `rm`.

```sh
ls -la /opt/dockerapps/authelia/postgres
sudo rm -rf /opt/dockerapps/authelia/postgres

ls -la /opt/dockerapps/authelia/postgres15-cold
sudo rm -rf /opt/dockerapps/authelia/postgres15-cold

ls -la /opt/dockerapps/authelia/backups
sudo rm -rf /opt/dockerapps/authelia/backups
```

`sudo` is needed because the Postgres data dirs are owned by the container's
`postgres` uid. Do not touch `postgres18` or `backups-pg18`.

## What you can no longer do

- Roll back to Postgres 15: the old data dir, the cold copy and the PG15 dump
  are all gone. Only the PG18 baseline remains, and PG15 cannot restore it.
- Compare row counts against the pre-migration state (`counts-*.txt`).
- Recover anything that existed in PG15 but not in PG18. The migration was
  verified (25 tables, matching counts), but that check can no longer be rerun.

Rolling back Redis is unaffected: it only ever held sessions.
