
================================================================================
                    OMNIPOST & SMARTSHELF AI - PREZENTACJA PROJEKTU
===================================================================

---

SLAJD 1: EKRAN TYTUŁOWY (Wizja i wejście)
-------------------------------------------

Tytuł główny: OmniPost & SmartShelf AI
Podtytuł:     Globalna rewolucja w monitoringu korespondencji fizycznej
              przy użyciu systemów wizyjnych AI.

Treść / Opis projektu:

* Inteligentny system automatyzacji procesów logistycznych.
* Całodobowa kontrola obiegu dokumentów papierowych.
* Skalowalne rozwiązanie: od pojedynczego biura do globalnego rynku pocztowego.

GRAFIKA: Użyj obrazu [ docs/images/ai3.jpg ] jako pełnoekranowego tła slajdu.

---

SLAJD 2: PROBLEM W MIKROSKALI (Środowisko Biurowe)
---------------------------------------------------

Tytuł: Wąskie Gardło Współczesnego Biznesu: Fizyczny Obieg Pism

Kluczowe problemy:

* Dark Data: Dokumenty papierowe trafiają na regały bez żadnego cyfrowego śladu.
* Łamanie procedur SLA: Pisma prawne i urzędowe zalegają na półkach bez wiedzy adresata.
* Straty czasowe: Manualna, codzienna weryfikacja zawartości skrzynek przez pracowników.

Rozwiązanie (SmartShelf AI):

* Stały monitoring zajętości wydzielonych półek klienckich za pomocą kamer.
* Algorytmy detekcji zmian stanów (State Detection) automatyzujące rejestrację.

GRAFIKA: Wklej po prawej stronie obraz [ docs/images/ai1.jpg ] (Regał biurowy).

---

SLAJD 3: SKALOWANIE DO MAKROSKALI (Hit Światowy - Model Grecki)
----------------------------------------------------------------

Tytuł: Globalny Potencjał Rynkowy: Zarządzanie Chaosem Logistycznym

Dwa tryby pracy systemu:

1. Model Uporządkowany: Stała geometria wydzielonych półek i boksów.
2. Model Chaotyczny (Sterta): Masowe punkty zrzutu poczty (np. mniejsze wyspy
   w Grecji, kurorty, małe społeczności), gdzie listy lądują na jednej stercie.

Innowacja OmniPost AI w trybie sterty:

* Analiza różnicowa obrazu (kilka klatek na sekundę) identyfikuje moment
  odłożenia i podniesienia każdego obiektu w przestrzeni chaosu.

GRAFIKA: Wklej po prawej stronie obraz [ docs/images/ai2.jpg ] (Sterta w Grecji).

---

SLAJD 4: ARCHITEKTURA TECHNOLOGICZNA MVP
----------------------------------------

Tytuł: Skalowana i Lekka Infrastruktura na Serwerze VPS

Komponenty techniczne:

* Edge Camera (Smartfon): Dowolny telefon jako mobilny, bezprzewodowy sensor
  wizyjny przesyłający ujęcia przez API. Brak konieczności zakupu drogiego sprzętu.
* VPS Backend: Centralny serwer przetwarzający obraz w Pythonie. Posiada moduł
  OCR do natychmiastowego odczytu adresatów z góry (w trybie sterty).
* Baza Danych SQL: Relacyjny rejestr zdarzeń, logów obecności oraz automatycznego
  wyliczania czasu SLA dokumentów.

Schemat blokowy systemu:
[ Smartfon (Kamera IP) ] ➔ [ Bramka API (VPS) ] ➔ [ Silnik AI / Baza SQL ] ➔ [ Panel Dashboard ]

---

SLAJD 5: PRZYSZŁOŚĆ PROJEKTU I KOMERCJALIZACJA (Roadmap)
-----------------------------------------------------------

Tytuł: Kolejne Kamienie Milowe i Potencjał Biznesowy B2B

Kierunki rozwoju aplikacji:

* Anti-Theft AI: Autoryzacja odbiorcy pism za pomocą rozpoznawania sylwetek i twarzy.
  Ochrona przed niepowołanym pobraniem wrażliwych dokumentów.
* Generatywne AI (LLM Summaries): Automatyczne skanowanie treści pisma przez AI
  i wysyłanie klientowi gotowego streszczenia w powiadomieniu SMS/E-mail.
* Integracja logistyczna: Współpraca z autonomicznymi robotami sortującymi
  w dużych hubach przeładunkowych.
  ================================================================================
