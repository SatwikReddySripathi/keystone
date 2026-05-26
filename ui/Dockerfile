FROM node:20-slim

WORKDIR /app

# Install dependencies from the locked manifest. `npm ci` is strict and
# fast: it refuses to install if package.json and package-lock.json
# disagree, and never mutates the lockfile.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# These are injected at build time. They must be set BEFORE `next build`
# because Next.js inlines NEXT_PUBLIC_* values into the static output
# during the build, not at container start.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ARG NEXT_PUBLIC_API_KEY=am_test_demo_key_001
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_KEY=$NEXT_PUBLIC_API_KEY

RUN npm run build

# Drop root before serving. nextjs is the conventional non-root user in
# upstream Next.js Docker examples.
RUN groupadd --system --gid 1001 nodejs \
    && useradd --system --uid 1001 --gid nodejs --shell /usr/sbin/nologin nextjs \
    && chown -R nextjs:nodejs /app
USER nextjs

EXPOSE 3000

CMD ["npm", "start"]
