# Build stage: compile the SPA with Vite.
FROM node:20-alpine AS builder

WORKDIR /app

# Dependencies first, in their own layer. `npm ci` requires a lockfile that is
# in sync with package.json, and fails rather than silently resolving
# something different -- which is the point on a build someone else will run.
COPY package*.json ./
RUN npm ci

# Source after, so editing a component does not invalidate the install layer.
COPY . .
RUN npm run build

# Production stage: serve the static output with nginx.
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Validate at build time, not at container start.
#
# Without this, a syntax error in nginx.conf passes `docker compose build`
# cleanly and then the container exits immediately on boot -- typically at the
# moment the demo is supposed to start. Failing the build means the error
# appears while someone is still fixing things rather than five minutes before
# a presentation.
RUN nginx -t

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
