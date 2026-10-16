# Mem0 REST API server (upstream server/ at v2.2.1), built for linux/amd64 on Railway.
# The official mem0/mem0-api-server image is stale (Sept 2025) and arm64-only.

# --- upstream source, pinned to the v2.2.1 commit and checksum-verified ---
FROM alpine:3.22.2@sha256:4b7ce07002c69e8f3d704a9c5d6fd3053be500b7f1c69fc0d80990c2ad8dd412 AS upstream
ARG MEM0_COMMIT=94c3fe9f238f3dbf29c9ce98643bd71eb13077cd
ARG MEM0_TARBALL_SHA256=0529671008cfa497329439a334d51fd12d24bd664bcdc53f9195c4a10ab63ad7
RUN wget -qO /tmp/mem0.tgz "https://codeload.github.com/mem0ai/mem0/tar.gz/${MEM0_COMMIT}" \
 && echo "${MEM0_TARBALL_SHA256}  /tmp/mem0.tgz" | sha256sum -c - \
 && mkdir -p /src \
 && tar -xzf /tmp/mem0.tgz -C /src --strip-components=1 \
 && rm -rf /tmp/mem0.tgz /src/server/dashboard

# --- runtime ---
FROM python:3.12.15-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MEM0_DIR=/app/history/.mem0
WORKDIR /app
COPY --from=upstream /src/server/ /app/
COPY constraints.txt patch_upstream.py railway_start.py /railway/
# mem0ai is pinned to the same release as the server (upstream requirements say >=0.1.48).
RUN pip install -r requirements.txt -c /railway/constraints.txt "mem0ai==2.2.1" \
 && python /railway/patch_upstream.py \
 && mkdir -p /app/history
EXPOSE 8000
CMD ["python", "/railway/railway_start.py"]
