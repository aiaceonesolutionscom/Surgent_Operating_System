# Multi-stage build: compile the Vite app, then serve the static output with nginx.
# (On InsForge the frontend is normally deployed with `deployments deploy`, which
# builds on the host from vercel.json - this image is the self-hosted alternative.)

FROM node:20-slim AS build
WORKDIR /app

# A production build bakes its configuration in, and vite.config.ts REFUSES to
# build without a real API URL and Clerk key - pass them as build args:
#   docker build --build-arg VITE_API_BASE_URL=https://api.example.com \
#                --build-arg VITE_CLERK_PUBLISHABLE_KEY=pk_live_... .
ARG VITE_API_BASE_URL
ARG VITE_CLERK_PUBLISHABLE_KEY
ARG VITE_SENTRY_DSN
ARG VITE_APP_VERSION
ARG VITE_POSTHOG_KEY
ARG VITE_POSTHOG_HOST
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_CLERK_PUBLISHABLE_KEY=$VITE_CLERK_PUBLISHABLE_KEY \
    VITE_SENTRY_DSN=$VITE_SENTRY_DSN \
    VITE_APP_VERSION=$VITE_APP_VERSION \
    VITE_POSTHOG_KEY=$VITE_POSTHOG_KEY \
    VITE_POSTHOG_HOST=$VITE_POSTHOG_HOST

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
