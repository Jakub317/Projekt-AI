# 📦 OmniPost - Smart Shelf z AI

Kompletny system inteligentnej półki (Smart Shelf) z wykorzystaniem AI do wykrywania przesyłek (YOLO), symulacji połączeń głosowych oraz Live AI Terminalu. Projekt jest w pełni skonteneryzowany i gotowy do uruchomienia w środowisku lokalnym.

## 🚀 Wymagania wstępne

Przed rozpoczęciem upewnij się, że masz zainstalowane:
- **Docker Desktop** z włączonym backendem WSL 2 (Windows) lub Docker Engine (Linux/macOS)
  - Pobierz: https://www.docker.com/products/docker-desktop/
- **Git** (do klonowania repozytorium)
  - Pobierz: https://git-scm.com/downloads

---

## ⚡ Instalacja i uruchomienie (krok po kroku)

### Krok 1: Sklonuj repozytorium

Otwórz terminal (PowerShell, CMD lub bash) i wykonaj:

```bash
git clone -b feature/omnipost-portal https://github.com/Jakub317/Projekt-AI.git
cd Projekt-AI

Krok 2: Utwórz plik konfiguracyjny .env

Projekt wymaga pliku .env z zmiennymi środowiskowymi. W repozytorium znajduje się plik .env.example z bezpiecznymi wartościami domyślnymi.

Windows PowerShell:
powershell

1. copy .env.example .env

(To polecenie automatycznie tworzy i zapisuje plik .env. Nie musisz go tworzyć ręcznie!). Plik należy zapisac z ustawieniem encoding utf8 (inne dają błedy)

Krok 3: Zbuduj i uruchom kontenery
bash

1. docker compose up -d --build

System automatycznie:
Zbuduje obraz Docker z aplikacją Django
Uruchomi bazę danych MariaDB
Poczeka, aż baza przejdzie test healthcheck
Uruchomi aplikację Django
Krok 4: Zainicjuj bazę danych
Utwórz tabele w bazie danych:

1. docker compose exec web python manage.py migrate

Krok 5: Utwórz konto administratora

1. docker compose exec web python manage.py createsuperuser

Postępuj zgodnie z instrukcjami w terminalu (podaj login, e-mail i hasło).

⚠️ BARDZO WAŻNY PIERWSZY KROK (przed wejściem na stronę)

Aby widok główny załadował się poprawnie i uniknąć błędów, musisz dodać dane testowe:

Wejdź do panelu admina: http://localhost:8000/admin/
Zaloguj się utworzonym kontem administratora.
Przejdź do sekcji Office -> Shelfs i kliknij Add.
Nadaj nazwę (np. "Półka Testowa") i wgraj dowolne zdjęcie w pole Photo.
Kliknij Save.
Bez tego aplikacja nie będzie miała danych do wyświetlenia w widoku "Przed/Po" i pojawi się błąd.
🌐 Dostęp do aplikacji

Panel Office (Live AI Terminal): http://localhost:8000/omnipost-portal/office/
Panel Administratora: http://localhost:8000/admin/

🛠️ Przydatne komendy

# Zatrzymanie aplikacji (zachowuje dane w bazie)
docker compose down

# Uruchomienie ponownie (bez przebudowy)
docker compose up -d

# Podgląd logów w czasie rzeczywistym (przydatne przy błędach)
docker compose logs -f web

# Wejście do konsoli Django w kontenerze
docker compose exec web python manage.py shell

🐛 Rozwiązywanie najczęstszych problemów

Kontener web się restartuje:

Sprawdź przyczynę w logach: docker compose logs web --tail=50. Najczęstszą przyczyną jest brak pliku .env lub literówka w jego nazwie.
Błąd IndexError na stronie /office/:
Zapomniałeś wykonać "BARDZO WAŻNY PIERWSZY KROK". Dodaj Półkę (Shelf) ze zdjęciem w panelu admina.
Port 8000 jest zajęty:
Zmień port w pliku docker-compose.yml (np. na "8001:8000") i uruchom ponownie: docker compose down && docker compose up -d.

