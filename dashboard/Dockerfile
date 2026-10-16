# Mem0 dashboard (upstream server/dashboard at v2.2.1, Next.js standalone), built on Railway.
# Same stages as upstream server/dashboard/Dockerfile, with pinned base images, a pinned
# source commit and a frozen pnpm lockfile.

FROM alpine:3.22.2@sha256:4b7ce07002c69e8f3d704a9c5d6fd3053be500b7f1c69fc0d80990c2ad8dd412 AS upstream
ARG MEM0_COMMIT=94c3fe9f238f3dbf29c9ce98643bd71eb13077cd
ARG MEM0_TARBALL_SHA256=0529671008cfa497329439a334d51fd12d24bd664bcdc53f9195c4a10ab63ad7
RUN wget -qO /tmp/mem0.tgz "https://codeload.github.com/mem0ai/mem0/tar.gz/${MEM0_COMMIT}" \
 && echo "${MEM0_TARBALL_SHA256}  /tmp/mem0.tgz" | sha256sum -c - \
 && mkdir -p /src \
 && tar -xzf /tmp/mem0.tgz -C /src --strip-components=1 "mem0-${MEM0_COMMIT}/server/dashboard" \
 && rm /tmp/mem0.tgz

FROM node:20.20.2-alpine3.22@sha256:8f47899606d000b0704e992f927fe7335adcd0d6c98851600072fb6e14a13e60 AS base
RUN apk add --no-cache libc6-compat
WORKDIR /app

FROM base AS deps
COPY --from=upstream /src/server/dashboard/package.json /src/server/dashboard/pnpm-lock.yaml /src/server/dashboard/pnpm-workspace.yaml ./
RUN corepack enable pnpm && pnpm install --frozen-lockfile

FROM base AS builder
COPY --from=upstream /src/server/dashboard/ ./
COPY --from=deps /app/node_modules ./node_modules
ENV NEXT_TELEMETRY_DISABLED=1
# Placeholders swapped for the real values at container start by upstream entrypoint.sh
ENV NEXT_PUBLIC_API_URL=NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_INSTANCE_NAME=NEXT_PUBLIC_INSTANCE_NAME
RUN corepack enable pnpm && pnpm run build

FROM base AS runner
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=::
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=upstream --chown=nextjs:nodejs /src/server/dashboard/entrypoint.sh /home/nextjs/entrypoint.sh
RUN chmod +x /home/nextjs/entrypoint.sh
USER nextjs
EXPOSE 3000
ENTRYPOINT ["/home/nextjs/entrypoint.sh"]
CMD ["node", "server.js"]
