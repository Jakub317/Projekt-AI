# Portal OmniPost / SmartShelf AI

Portal dla upoważnionych studentów projektu OmniPost do przesyłania zdjęć półek,
kodu źródłowego, archiwów ZIP i modeli ML. Część infrastruktury Fundacji
Respublica Civium.

## Adres publiczny

https://respublicacivium.pl/omnipost-portal/

## Architektura

- Aplikacja Django 6.1 (projekt `portalconfig`, aplikacja `submissions`).
- Osobne środowisko Python: `/var/www/omnipost-portal/venv` (Python 3.13).
- Baza danych: MariaDB, baza `omnipost_portal`, użytkownik `omniportal`
  (uprawnienia tylko do tej bazy; hasło w `/etc/omnipost-portal.env`, tryb 0640
  root:www-data).
- Pliki studentów: `/var/lib/omnipost-portal/uploads/` (poza WWW, tryb 0750
  krzysztof:www-data).
- Pliki statyczne: `/var/lib/omnipost-portal/static/`.
- Usługa systemd: `omnipost-portal.service` (gunicorn, 3 workery, 127.0.0.1:8010).
- Nginx: `location /omnipost-portal/` → `proxy_pass http://127.0.0.1:8010`.
- Istniejąca demonstracja OmniPost (`/omnipost/`) i strona Fundacji (`/`)
  pozostają nietknięte.

## Struktura katalogów

    /var/www/omnipost-portal/
    ├── manage.py
    ├── portalconfig/          # settings, urls, wsgi
    ├── submissions/           # modele, widoki, formularze, szablony
    │   ├── migrations/
    │   ├── templates/submissions/
    │   ├── models.py          # UserProfile, UploadedMaterial, AuditLog
    │   ├── views.py
    │   ├── forms.py
    │   ├── urls.py
    │   └── admin.py
    ├── venv/                  # środowisko Python (nie commitować)
    └── README.md

    /var/lib/omnipost-portal/
    ├── uploads/               # pliki studentów (poza WWW)
    └── static/                # pliki statyczne Django (collectstatic)

    /etc/omnipost-portal.env   # konfiguracja (hasła, DB, UPLOAD_ROOT)
    /etc/systemd/system/omnipost-portal.service

## Zarządzanie użytkownikami

Rejestracja jest zamknięta — konta tworzy administrator portalu przez
`manage.py shell` (brak otwartej rejestracji publicznej).

### Utworzenie studenta

    sudo -u krzysztof -g www-data bash -c '
      set -a; source /etc/omnipost-portal.env; set +a;
      /var/www/omnipost-portal/venv/bin/python /var/www/omnipost-portal/manage.py shell -c "
        from django.contrib.auth.models import User
        from submissions.models import UserProfile
        u = User.objects.create_user(username=\"LOGIN\", password=\"HASŁO\")
        p, _ = UserProfile.objects.get_or_create(user=u)
        p.role = \"student\"
        p.save()
        print(u.username, p.role)
      "'

### Zmiana roli (student ↔ admin)

    ... p.role = \"admin\"; p.save()

### Zablokowanie konta

    ... p.is_blocked = True; p.save()

(Uwaga: flaga `is_blocked` jest sprawdzana w widokach — jeśli chcesz twardej
blokady logowania, ustaw też `u.is_active = False`.)

### Reset hasła

    sudo -u krzysztof -g www-data /var/www/omnipost-portal/venv/bin/python \
      /var/www/omnipost-portal/manage.py changepassword LOGIN

## Panel administratora (Django admin)

    https://respublicacivium.pl/omnipost-portal/admin/

Wymaga konta z `is_staff=True` i `is_superuser=True` oraz `UserProfile.role="admin"`.
Rejestracja modeli: `UserProfile`, `UploadedMaterial`, `AuditLog` — z filtrami
po typie, statusie i użytkowniku.

## Procedura backupu

### Baza danych

    sudo mysqldump --single-transaction --routines --triggers \
      -u omniportal -p omnipost_portal | gzip > \
      /root/backup-omnipost_portal-$(date +%F).sql.gz

(hasło do bazy: z `/etc/omnipost-portal.env`, NIE umieszczać w dokumentacji)

### Pliki studentów

    sudo tar -czf /root/backup-omnipost-uploads-$(date +%F).tar.gz \
      -C /var/lib/omnipost-portal uploads

### Konfiguracja

    sudo tar -czf /root/backup-omnipost-config-$(date +%F).tar.gz \
      /etc/omnipost-portal.env \
      /etc/systemd/system/omnipost-portal.service \
      /etc/nginx/sites-enabled/respublicacivium \
      /var/www/omnipost-portal/portalconfig \
      /var/www/omnipost-portal/submissions

### Odtwarzanie

    sudo systemctl stop omnipost-portal
    gunzip < /root/backup-omnipost_portal-YYYY-MM-DD.sql.gz | \
      sudo mysql -u omniportal -p omnipost_portal
    sudo tar -xzf /root/backup-omnipost-uploads-YYYY-MM-DD.tar.gz \
      -C /var/lib/omnipost-portal
    sudo systemctl start omnipost-portal

## Procedura aktualizacji

Gdy pojawi się nowy kod (np. repo Git w `/var/www/omnipost-portal/`):

    cd /var/www/omnipost-portal
    sudo -u krzysztof -g www-data git pull            # jeśli repo istnieje
    sudo -u krzysztof -g www-data venv/bin/pip install -r requirements.txt
    sudo -u krzysztof -g www-data bash -c '
      set -a; source /etc/omnipost-portal.env; set +a;
      venv/bin/python manage.py migrate --noinput
      venv/bin/python manage.py collectstatic --noinput
    '
    sudo systemctl restart omnipost-portal
    sudo systemctl reload nginx

## Testy bezpieczeństwa (wykonane)

- Brak dostępu do `/dashboard/` i `/admin-panel/` bez logowania → 302.
- Logowanie studenta → 302 na `/dashboard/`.
- Upload pliku → wpis w `UploadedMaterial` + plik w `/var/lib/omnipost-portal/uploads/`.
- Download własnego pliku → 200.
- Upload bez CSRF → 403.
- Download cudzego pliku (student2 → plik student1) → 403.

## Ograniczenia i uwagi

- Limit rozmiaru pliku: **25 MB** (`client_max_body_size 25M` w Nginx
  + `MAX_UPLOAD_SIZE` w `submissions/forms.py`).
- Dozwolone rozszerzenia zależą od typu: patrz `ALLOWED_BY_TYPE` w `forms.py`.
- Pliki studentów **nie są wykonywane** na serwerze — są tylko przechowywane
  i pobierane przez widok z kontrolą dostępu.
- Kod studentów (rozpoznawanie półek, symulacja neuronu, SMS-y) **nie jest
  jeszcze zintegrowany** — zostanie podłączony po otrzymaniu kodu, zgodnie
  z zasadą „nie uruchamiamy nieznanego kodu na serwerze produkcyjnym".
- `DEBUG=False`, `ALLOWED_HOSTS` ograniczone do `respublicacivium.pl`,
  `www.respublicacivium.pl`, `127.0.0.1`, `localhost`.
- `MEDIA_URL = "/private-uploads/"` — Nginx **nie serwuje** tego prefiksu;
  pliki są dostępne wyłącznie przez widok `download` z kontrolą dostępu.

## Kontakt / utrzymanie

Administrator: krzysztof (konto systemowe na VPS + konto w portalu z rolą `admin`).
