# Postgres 15 -> 18 and Redis 7 -> 8

Authelia storage (`database`) and sessions (`redis`) only. Expect a few
minutes of downtime: anything behind Authelia is unreachable while `auth` is
stopped. Sites behind `forward_auth` return 502 (they fail closed, not open);
`overseerr.` has no Authelia gate and keeps serving.

Status: written against the upstream image docs and checked locally
(`postgres:18.6`, `redis:8.10.2` on a scratch volume). **Not run against the
real server.** Read it through once before you start.

## Why this is manual

- `scripts/deploy.sh` runs `docker compose up -d` from cron every 10 minutes,
  so merging a tag bump deploys it.
- Postgres 18 cannot open a Postgres 15 data directory. Worse, the 18 image
  changed its layout (below), so the old bind mount would silently become an
  empty cluster and Authelia would migrate a blank schema: TOTP and WebAuthn
  registrations gone.
- The compose change is therefore a separate PR. Merge it at step 4, not
  before.

## Image changes that matter

Postgres 18+ (official image docs):

- `VOLUME` moved from `/var/lib/postgresql/data` to `/var/lib/postgresql`.
- `PGDATA` is versioned: `/var/lib/postgresql/18/docker`.
- Mount at `/var/lib/postgresql`. Mounting at the old `/data` path on 18
  creates an anonymous volume and the data does not persist.

So the compose change is a new mount target **and** a new host directory
(`/opt/dockerapps/authelia/postgres18`). The old directory stays untouched and
is the rollback.

Redis 8: same image family, same `docker-entrypoint.sh`, `/data`, and
`redis-cli`. Nothing in the existing `command` or healthcheck needs to change.

## Redis: 8 or Valkey?

Recommendation: `redis:8`.

- Smallest change. Checked locally on `redis:8` (8.10.2): the
  `exec docker-entrypoint.sh redis-server ... --requirepass "$(cat ...)"`
  command starts, and the `REDISCLI_AUTH=... redis-cli ping` healthcheck
  returns `PONG`.
- Licence: Redis 8 is tri-licensed (RSALv2, SSPLv1, AGPLv3). The AGPLv3 option
  is OSI open source, and an internal session store triggers none of the
  network-copyleft obligations.
- Valkey (`valkey/valkey`, BSD-3) is a fine alternative if you want a
  permissive licence. It would need the healthcheck switched to `valkey-cli`
  and the entrypoint/user-drop behaviour rechecked. Not tested here. Authelia
  talks to either through a standard Redis client.
- Data loss is harmless. Redis holds only Authelia login sessions. Dropping
  `/opt/dockerapps/authelia/redis` logs everyone out; nothing else is lost.
  Bans and registrations live in Postgres.
- Redis needs no dump and can go with the Postgres change.

## Procedure

Run on the server in `/opt/dockerapps/docker-compose`. `$B` is the backup dir.

### 1. Prepare

```sh
B=/opt/dockerapps/authelia/backups; mkdir -p "$B"
crontab -e          # comment out the deploy.sh line; re-enable in step 8
docker pull postgres:18 && docker pull redis:8
```

Pausing cron stops a merge from deploying mid-migration. Confirm no deploy is
running: `pgrep -f deploy.sh` prints nothing.

### 2. Stop auth, dump

```sh
docker compose stop auth

# row counts before, for step 6
docker compose exec -T database psql -U authelia -d authelia -Atc "
  SELECT table_name, (xpath('/row/c/text()', query_to_xml(
    format('select count(*) as c from %I.%I', table_schema, table_name),
    false, true, '')))[1]::text
  FROM information_schema.tables
  WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
  ORDER BY 1" > "$B/counts-before.txt"

docker compose exec -T database pg_dump -U authelia -d authelia -Fc > "$B/authelia-pg15.dump"
```

Only the `authelia` database matters here. The role comes from
`POSTGRES_USER`, so `pg_dumpall` would add nothing. If you would rather have
a belt-and-braces plain copy, also run
`docker compose exec -T database pg_dumpall -U authelia > "$B/all-pg15.sql"`.

### 3. Check the dump, take a cold copy

```sh
docker run --rm -i postgres:18 pg_restore --list < "$B/authelia-pg15.dump" | head
ls -lh "$B"        # dump should be non-trivial in size

docker compose stop database
cp -a /opt/dockerapps/authelia/postgres /opt/dockerapps/authelia/postgres15-cold
```

The original directory is never written to again, so the cold copy is a
second safety net rather than the main rollback.

### 4. Merge the compose PR

Merge it only now. The PR moves `database` to `postgres:18`, mounts
`/opt/dockerapps/authelia/postgres18` at `/var/lib/postgresql`, and moves
`redis` to `redis:8`. Cron is paused, so nothing deploys yet:

```sh
mkdir -p /opt/dockerapps/authelia/postgres18
git pull --ff-only
docker compose --env-file .env config -q
```

### 5. Start Postgres 18, restore

```sh
docker compose up -d database          # wait for "healthy": docker compose ps database
docker compose exec -T database pg_restore -U authelia -d authelia \
  --no-owner --exit-on-error < "$B/authelia-pg15.dump"
docker compose exec -T database psql -U authelia -d authelia -c "ANALYZE"
```

`POSTGRES_PASSWORD` in `.env` must still match Authelia's `STORAGE_PASSWORD`
secret: the new cluster takes its password from `.env` on first start.

### 6. Verify

```sh
docker compose exec database psql -U authelia -d authelia -Atc "show server_version"   # 18.x
# rerun the step 2 count query into "$B/counts-after.txt", then:
diff "$B/counts-before.txt" "$B/counts-after.txt" && echo same
```

Any diff: stop and go to Rollback.

### 7. Start the rest

```sh
docker compose up -d            # recreates redis on 8; starts auth
docker compose logs --tail=50 auth
docker compose exec redis sh -c 'redis-server --version'
```

Sign in through Caddy. Everyone is logged out once (Redis sessions gone or
reset). Confirm your TOTP/WebAuthn device still works, since that proves the
data restored.

### 8. Resume auto-deploy

`crontab -e` and restore the `deploy.sh` line. Check the next run in
`tail /var/log/snorlax-deploy.log`.

After a week of good behaviour, remove `postgres`, `postgres15-cold`, and the
old dump.

## Rollback

Safe until Authelia has taken meaningful new writes on 18 (new device
registrations, password resets). Those writes are lost on rollback.

```sh
docker compose stop auth database
git revert <compose-pr-merge-commit>      # back to postgres:15 + old mount
docker compose up -d database auth        # old directory is untouched
```

Then push the revert through a PR as usual, or leave cron paused until you
have. If the old directory looks damaged, restore `postgres15-cold` over it,
or start `postgres:15` on an empty directory and
`pg_restore` the step 2 dump into it.

Redis: pin `redis:7` again. If 7 refuses the `dump.rdb` written by 8, delete
`/opt/dockerapps/authelia/redis/dump.rdb`; only sessions are lost.
