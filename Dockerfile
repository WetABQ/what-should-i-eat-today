FROM node:20-slim AS frontend

WORKDIR /app/web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY src/ ./src/
COPY config.yaml .
COPY main.py .
COPY bot.py .

# Copy built frontend
COPY --from=frontend /app/web/dist ./web/dist

# Create data directory
RUN mkdir -p data/cache data/presets

ENV PORT=8000
EXPOSE 8000

CMD uvicorn src.api:app --host 0.0.0.0 --port $PORT
