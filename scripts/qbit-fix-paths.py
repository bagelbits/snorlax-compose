#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

OLD_ROOT = "/torrents"
NEW_ROOT = "/media/torrents"

USAGE = """\
Run inside the qbittorrent container:

  docker exec -i -e QBT_USER=admin -e QBT_PASS='...' qbittorrent python3 - < scripts/qbit-fix-paths.py
  docker exec -i -e QBT_USER=admin -e QBT_PASS='...' qbittorrent python3 - --apply < scripts/qbit-fix-paths.py

QBT_USER/QBT_PASS can be left out if "Bypass authentication for clients
on localhost" is on. Without --apply it only prints the plan.
"""


def map_path(path):
    path = path.rstrip("/") or "/"
    if path == OLD_ROOT or path.startswith(OLD_ROOT + "/"):
        return NEW_ROOT + path[len(OLD_ROOT):]
    return path


class Client:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def call(self, endpoint, **fields):
        data = urllib.parse.urlencode(fields).encode() if fields else None
        with self.opener.open(self.base_url + "/api/v2/" + endpoint, data) as resp:
            return resp.read().decode()

    def login(self, username, password):
        try:
            failed = self.call("auth/login", username=username, password=password).strip() == "Fails."
        except urllib.error.HTTPError:
            failed = True
        if failed:
            raise SystemExit("qBittorrent login failed; check QBT_USER/QBT_PASS")

    def torrents(self):
        return json.loads(self.call("torrents/info"))

    def start(self, hashes):
        try:
            self.call("torrents/start", hashes=hashes)
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            self.call("torrents/resume", hashes=hashes)


def plan(torrents):
    groups = {}
    for t in torrents:
        new = map_path(t["save_path"])
        if new != (t["save_path"].rstrip("/") or "/"):
            groups.setdefault(new, []).append(t)
    return groups


def wait_for_moves(client, hashes, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        pending = [t for t in client.torrents()
                   if t["hash"] in hashes and (t["state"] == "moving" or map_path(t["save_path"]) != t["save_path"].rstrip("/"))]
        if not pending:
            return []
        time.sleep(2)
    return pending


def main():
    parser = argparse.ArgumentParser(
        description="Repoint qBittorrent torrents from %s to %s." % (OLD_ROOT, NEW_ROOT),
        epilog=USAGE, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="change torrents instead of printing the plan")
    parser.add_argument("--url", default="http://localhost:%s" % os.environ.get("WEBUI_PORT", "8080"),
                        help="qBittorrent web UI URL (default: localhost on $WEBUI_PORT)")
    parser.add_argument("--self-test", action="store_true", help="run built-in checks and exit")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    client = Client(args.url)
    if os.environ.get("QBT_USER"):
        client.login(os.environ["QBT_USER"], os.environ.get("QBT_PASS", ""))

    try:
        torrents = client.torrents()
    except urllib.error.HTTPError as e:
        raise SystemExit("qBittorrent API returned %s; set QBT_USER/QBT_PASS" % e.code)

    groups = plan(torrents)
    total = sum(len(g) for g in groups.values())
    print("%d torrents, %d under %s" % (len(torrents), total, OLD_ROOT))
    for location, group in sorted(groups.items()):
        print("\n%s  (%d torrents)" % (location, len(group)))
        for t in group:
            print("  %-12s %s" % (t["state"], t["name"]))

    if not total:
        return 0
    if not args.apply:
        print("\nDry run; add --apply to change them.")
        return 0

    hashes = set()
    for location, group in groups.items():
        group_hashes = [t["hash"] for t in group]
        client.call("torrents/setLocation", hashes="|".join(group_hashes), location=location)
        hashes.update(group_hashes)

    stuck = wait_for_moves(client, hashes)
    if stuck:
        print("\nStill moving or not updated after 2 minutes; not rechecking these:")
        for t in stuck:
            print("  %s  %s" % (t["save_path"], t["name"]))
        hashes -= {t["hash"] for t in stuck}

    joined = "|".join(sorted(hashes))
    if joined:
        client.start(joined)
        client.call("torrents/recheck", hashes=joined)
    print("\nRepointed and rechecking %d torrents. Watch progress in the web UI." % len(hashes))
    return 1 if stuck else 0


def self_test():
    assert map_path("/torrents/radarr") == "/media/torrents/radarr"
    assert map_path("/torrents/radarr/") == "/media/torrents/radarr"
    assert map_path("/torrents") == "/media/torrents"
    assert map_path("/torrentsx") == "/torrentsx"
    assert map_path("/media/torrents/sonarr") == "/media/torrents/sonarr"
    torrents = [{"save_path": "/torrents/radarr/", "hash": "a"},
                {"save_path": "/torrents/sonarr", "hash": "b"},
                {"save_path": "/media/torrents/radarr", "hash": "c"}]
    groups = plan(torrents)
    assert sorted(groups) == ["/media/torrents/radarr", "/media/torrents/sonarr"]
    assert [t["hash"] for t in groups["/media/torrents/radarr"]] == ["a"]
    print("self-test OK")


if __name__ == "__main__":
    sys.exit(main())
