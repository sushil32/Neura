FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy source code
COPY . .

# Build for production
# RUN npm run build

EXPOSE 3000

CMD ["npm", "run", "dev"]

