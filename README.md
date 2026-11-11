# 🚀 OmniPost / SmartShelf AI - System Biurowy

Witaj w repozytorium naszego projektu! Jest to kompletny system składający się z portalu dla studentów (Django), serwisu sztucznej inteligencji (YOLO) oraz bazy danych MariaDB.

## 🐳 Jak uruchomić projekt lokalnie

Nie musisz instalować Pythona ani bazy danych. Wystarczy **Docker Desktop**.

1. Pobierz repozytorium na swój komputer (kliknij zielony przycisk **Code** -> **Download ZIP** i rozpakuj).
2. Otwórz terminal (lub PowerShell) w folderze z projektem.
3. Skopiuj plik `.env.example` i zmień jego nazwę na `.env`:
   - **Windows:** `copy .env.example .env`
   - **Mac/Linux:** `cp .env.example .env`
4. Otwórz plik `.env` i zmień `DB_PASSWORD` na dowolne, wymyślone przez siebie hasło.
5. Uruchom system komendą:
   ```bash
   docker compose up -d
