FROM node:22-alpine AS base

# Install pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app

# ── Dependency layer ─────────────────────────────────────────────────────────
FROM base AS deps

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# ── Build layer ──────────────────────────────────────────────────────────────
FROM base AS builder

WORKDIR /app

# Accept API URL at build time (Next.js bakes NEXT_PUBLIC_* at build)
ARG NEXT_PUBLIC_API_URL=http://sapsim-api.carlab.local/api
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

COPY --from=deps /app/node_modules ./node_modules
COPY . .

RUN pnpm build

# ── Production runner ────────────────────────────────────────────────────────
FROM base AS runner

WORKDIR /app

ENV NODE_ENV=production
# Re-expose the build-time var at runtime (for SSR reference if needed)
ARG NEXT_PUBLIC_API_URL=http://sapsim-api.carlab.local/api
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Copy only what Next.js needs to run in standalone/production mode
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

EXPOSE 3000

CMD ["pnpm", "start"]
