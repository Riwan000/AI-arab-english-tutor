FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x scripts/start_api.sh

EXPOSE 8000

# Render injects PORT; start script ensures the SQLite directory exists
CMD ["scripts/start_api.sh"]
