# syntax=docker/dockerfile:1
# 本番を想定した Next.js イメージ（output: "standalone"）。
# 開発時はホストで npm run dev を使う（Next.js は Mac での開発に Docker を推奨していない）。
#
# API_BASE_URL はビルド時ではなく実行時に渡す（Server Component / Server Action からのみ使用し、
# NEXT_PUBLIC_ を付けないためブラウザ向けコードには埋め込まれない）。
# ビルド時に backend は不要（fetch は cache: "no-store"）。next/font/google のためインターネット接続は必要。

FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000
# standalone には public と .next/static が含まれないため個別にコピーする
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
COPY --from=builder --chown=node:node /app/public ./public
# 公式イメージに含まれる root 以外のユーザー
USER node
EXPOSE 3000
CMD ["node", "server.js"]
