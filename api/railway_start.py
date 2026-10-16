"""Railway start wrapper for the Mem0 REST API (replaces upstream `uvicorn --reload`).

1. Waits for Postgres, enables pgvector and creates APP_DB_NAME (upstream does this with
   an init-db.sh mounted into the Postgres container, which Railway Postgres can't take).
2. Runs `alembic upgrade head` (users, API keys, settings, request logs).
3. Serves the API with uvicorn on a dual-stack [::] socket, so Railway's private network
   (IPv6, and IPv4 in newer environments) and the healthcheck both reach it.
"""

import os
import socket
import subprocess
import sys
import time
import warnings

import psycopg
from psycopg import sql


def env(name: str, default: str) -> str:
    return os.environ.get(name) or default


def log(msg: str) -> None:
    print(f"[railway-start] {msg}", flush=True)


HOST = env("POSTGRES_HOST", "postgres")
PG_PORT = int(env("POSTGRES_PORT", "5432"))
USER = env("POSTGRES_USER", "postgres")
PASSWORD = env("POSTGRES_PASSWORD", "postgres")
VECTOR_DB = env("POSTGRES_DB", "postgres")
APP_DB = env("APP_DB_NAME", "mem0_app")


def prepare_database() -> None:
    deadline = time.time() + int(env("MEM0_DB_WAIT_SECONDS", "180"))
    while True:
        try:
            conn = psycopg.connect(
                host=HOST, port=PG_PORT, user=USER, password=PASSWORD, dbname=VECTOR_DB,
                autocommit=True, connect_timeout=5,
            )
            break
        except Exception as exc:  # noqa: BLE001
            if time.time() > deadline:
                log(f"Postgres at {HOST}:{PG_PORT} still unreachable, giving up: {exc}")
                sys.exit(1)
            log(f"waiting for Postgres at {HOST}:{PG_PORT} ({type(exc).__name__})")
            time.sleep(3)
    with conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (APP_DB,)).fetchone()
        if exists:
            log(f"database {APP_DB!r} exists")
        else:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(APP_DB)))
            log(f"created database {APP_DB!r}")
    log(f"pgvector ready in {VECTOR_DB!r}")


def migrate() -> None:
    log("running alembic upgrade head")
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd="/app", check=True, stderr=subprocess.STDOUT,
    )


def serve() -> None:
    import uvicorn

    port = int(env("PORT", "8000"))
    sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
    sock.bind(("::", port))
    log(f"serving Mem0 API on [::]:{port} (dual-stack)")
    config = uvicorn.Config(
        "main:app",
        proxy_headers=True,
        forwarded_allow_ips=env("FORWARDED_ALLOW_IPS", "*"),
        log_level=env("LOG_LEVEL", "info"),
        timeout_graceful_shutdown=20,
    )
    uvicorn.Server(config).run(sockets=[sock])


if __name__ == "__main__":
    # Railway tags every stderr line as an error. Python/uvicorn/alembic log INFO to stderr, so send
    # everything to stdout; the log lines still carry their own level (INFO/WARNING/ERROR).
    sys.stderr = sys.stdout
    # passlib 1.7 imports the stdlib `crypt` module, which warns on Python 3.12; harmless noise.
    warnings.filterwarnings("ignore", category=DeprecationWarning, module=r"passlib(\..*)?")
    os.chdir("/app")
    sys.path.insert(0, "/app")
    prepare_database()
    migrate()
    serve()
