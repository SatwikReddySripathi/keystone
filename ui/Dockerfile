FROM node:20-slim

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

# These are injected at build time by Railway/Vercel
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ARG NEXT_PUBLIC_API_KEY=ks_test_demo_key_001
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_KEY=$NEXT_PUBLIC_API_KEY

RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
