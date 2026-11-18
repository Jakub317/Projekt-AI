# Używamy stabilnego obrazu Pythona
FROM python:3.11-slim

# Instalujemy zależności systemowe potrzebne dla mysqlclient
RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    build-essential \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Ustawiamy katalog roboczy
WORKDIR /app

# Kopiujemy plik z zależnościami i je instalujemy
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiujemy resztę kodu projektu
COPY . .

# Ustawiamy zmienne środowiskowe
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Uruchamiamy aplikację (używamy gunicorn dla produkcji, lub runserver dla dev)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
