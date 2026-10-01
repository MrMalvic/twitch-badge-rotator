#!/usr/bin/env python3
"""Rotate your Twitch global chat badge every time you send a message."""

import argparse
import http.client
import itertools
import json
import logging
import os
import random
import socket
import ssl
import sys
import time

CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"
GQL_HOST = "gql.twitch.tv"
IRC_HOST = "irc.chat.twitch.tv"
IRC_PORT = 443
IRC_IDLE_TIMEOUT = 360
RECONNECT_DELAY = 5

log = logging.getLogger("badge-rotator")


class TwitchError(Exception):
    pass


class AuthError(TwitchError):
    pass


class GQLClient:
    def __init__(self, token):
        self._headers = {
            "Client-Id": CLIENT_ID,
            "Authorization": f"OAuth {token}",
            "Content-Type": "application/json",
        }
        self._conn = http.client.HTTPSConnection(GQL_HOST, timeout=10)

    def query(self, query):
        status, payload = self._post(json.dumps({"query": query}))
        if status == 401:
            raise AuthError("auth token rejected, grab a fresh auth-token cookie")
        if status != 200:
            raise TwitchError(f"HTTP {status}: {payload[:200]!r}")
        body = json.loads(payload)
        if body.get("errors"):
            raise TwitchError(body["errors"][0].get("message", "unknown GQL error"))
        return body["data"]

    def _post(self, body):
        try:
            return self._send(body)
        except (http.client.HTTPException, OSError):
            self._conn.close()
            return self._send(body)

    def _send(self, body):
        self._conn.request("POST", "/gql", body, self._headers)
        resp = self._conn.getresponse()
        return resp.status, resp.read()


def fetch_badges(gql):
    user = gql.query("{ currentUser { login availableBadges { setID version title } } }")["currentUser"]
    if not user:
        raise AuthError("token is not attached to a logged-in account")
    return user["login"], user["availableBadges"]


def select_badge(gql, badge):
    set_id, version = json.dumps(badge["setID"]), json.dumps(badge["version"])
    gql.query(
        f"mutation {{ selectGlobalBadge(input: {{ badgeSetID: {set_id}, badgeSetVersion: {version} }}) "
        "{ user { id } } }"
    )


def parse_sender(line):
    prefix, _, rest = line.partition(" ")
    if prefix.startswith(":") and rest.startswith("PRIVMSG "):
        return prefix[1:].partition("!")[0].lower()
    return None


def chat_senders(channels):
    ctx = ssl.create_default_context()
    with socket.create_connection((IRC_HOST, IRC_PORT), timeout=IRC_IDLE_TIMEOUT) as raw:
        with ctx.wrap_socket(raw, server_hostname=IRC_HOST) as sock:
            sock.sendall(
                f"NICK justinfan{random.randint(10000, 99999)}\r\n"
                f"JOIN {','.join('#' + c for c in channels)}\r\n".encode()
            )
            buf = b""
            while chunk := sock.recv(4096):
                buf += chunk
                *lines, buf = buf.split(b"\r\n")
                for line in lines:
                    if line.startswith(b"PING"):
                        sock.sendall(b"PONG" + line[4:] + b"\r\n")
                    elif sender := parse_sender(line.decode(errors="replace")):
                        yield sender
    raise ConnectionResetError("server closed the connection")


def watch(channels):
    while True:
        try:
            yield from chat_senders(channels)
        except OSError as e:
            log.warning("chat connection lost (%s), reconnecting in %ds", e, RECONNECT_DELAY)
            time.sleep(RECONNECT_DELAY)


def rotate(gql, login, badges, channels):
    rotation = itertools.cycle(badges)
    for sender in watch(channels):
        if sender != login:
            continue
        badge = next(rotation)
        started = time.perf_counter()
        try:
            select_badge(gql, badge)
        except AuthError:
            raise
        except (TwitchError, OSError) as e:
            log.warning("could not switch to %s: %s", badge["title"], e)
            continue
        log.info("-> %s (%.0f ms)", badge["title"], (time.perf_counter() - started) * 1000)


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("channels", nargs="+", help="channels to watch for your messages")
    parser.add_argument("--in-order", action="store_true", help="cycle badges alphabetically instead of shuffled")
    args = parser.parse_args(argv)
    args.channels = sorted({c.lstrip("#").lower() for c in args.channels})
    args.token = os.environ.get("TWITCH_AUTH_TOKEN", "").strip().strip('"')
    if not args.token:
        parser.error("set TWITCH_AUTH_TOKEN to the auth-token cookie from twitch.tv")
    return args


def main(argv=None):
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    gql = GQLClient(args.token)
    try:
        login, badges = fetch_badges(gql)
        if not badges:
            sys.exit(f"{login} has no global badges to rotate")
        if not args.in_order:
            random.shuffle(badges)
        log.info("%s: %d badges, watching %s", login, len(badges), ", ".join(args.channels))
        rotate(gql, login, badges, args.channels)
    except TwitchError as e:
        sys.exit(f"error: {e}")
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
