ORGANIZER AI — lokalny panel webowy (prototyp)

1. Zainstaluj Python 3.10–3.12 dla Windows.
2. Skopiuj swój model best.pt do folderu model\best.pt.
3. Uruchom run_windows.bat.
4. Otwórz http://127.0.0.1:5000 w przeglądarce.
5. Wybierz nagranie i uruchom analizę.

Pierwsze uruchomienie tworzy .venv i instaluje biblioteki. Może potrwać kilka minut.

Aplikacja uruchamia istniejący skrypt analizy jako osobny proces. Wyniki trafiają do results/<id>/, a przesłane nagrania do uploads/.

Ograniczenia prototypu:
- pasek postępu jest orientacyjny i odświeża się na podstawie komunikatów skryptu;
- historia pochodzi z raportu ostatniej analizy, trwałą bazę SQLite dodamy później;
- widok 8 przegródek jest na razie statycznym podglądem, nie odczytuje jeszcze stanu na żywo;
- zasłonięcie dłoni jest szacowane przez ruch obrazu, nie przez osobny detektor dłoni;
- serwer nasłuchuje tylko na 127.0.0.1. Nie wystawiaj go do internetu.
