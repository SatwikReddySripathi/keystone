FROM node:20-slim

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

ENV NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_KEY=ks_test_demo_key_001

RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]