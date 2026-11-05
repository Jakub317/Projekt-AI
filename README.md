https://drive.google.com/file/d/1em4WpEfoIP9CbXEdOmGzWCyi2ebwGLTm/view?usp=sharing

Projekt AI – Wykrywanie Kartek z Obrazów i Wideo

Projekt oparty na sztucznej inteligencji (Computer Vision), służący do automatycznego wykrywania i analizowania kartek papieru z plików graficznych oraz materiałów wideo.

##  Technologie
* **Język:** Python / JavaScript (w zależności od backendu/frontendu)
* **Computer Vision / AI:** OpenCV, PyTorch / TensorFlow / YOLO (lub odpowiednie modele użyte w projekcie)
* **Frontend / Web:** HTML5, CSS3, JavaScript / React (strona dostępna pod adresem projektu)

---

## Instrukcja Instalacji i Uruchomienia (Lokalnie)

### Wymagania wstępne
* Python (wersja 3.8 lub nowsza)
* Zainstalowany `git`

### Krok po kroku:

1. **Sklonuj repozytorium:**
   ```bash
   git clone [https://github.com/Jakub317/Projekt-AI.git](https://github.com/Jakub317/Projekt-AI.git)
   cd Projekt-AI
   1. Utwórz i aktywuj środowisko wirtualne (zalecane):
   python -m venv venv
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate
2.Zainstaluj wymagane zależności:
pip install -r requirements.txt
3. python app.py  # lub komenda uruchomieniowa Twojego serwera
4.Otwórz przeglądarkę i przejdź pod wskazany adres (np. http://localhost:5000):
##  Spis Treści
1. [Wprowadzenie](#wprowadzenie)
2. [Wymagania systemowe](#wymagania-systemowe)
3. [Główne funkcjonalności](#główne-funkcjonalności)
4. [Instrukcja krok po kroku](#instrukcja-krok-po-kroku)
   - [Wykrywanie kartek ze zdjęć](#1-wykrywanie-kartek-ze-zdjęć)
   - [Wykrywanie kartek z wideo](#2-wykrywanie-kartek-z-wideo)
5. [Rozwiązywanie problemów (FAQ)](#rozwiązywanie-problemów-faq)

---

### 1. Wprowadzenie
Aplikacja internetowa do wykrywania kartek papieru wykorzystuje zaawansowane algorytmy sztucznej inteligencji. Pozwala na błyskawiczne wgranie zdjęcia lub pliku wideo w celu precyzyjnego zaznaczenia i analizy obiektów (kartek) w czasie rzeczywistym.

### 2. Wymagania systemowe
* Dowolna nowoczesna przeglądarka internetowa (Google Chrome, Mozilla Firefox, Microsoft Edge, Safari).
* Dobre połączenie z internetem (w przypadku wersji hostowanej online).

### 3. Główne funkcjonalności
*  **Przesyłanie zdjęć:** Obsługa popularnych formatów graficznych (PNG, JPG, JPEG).
*  **Analiza wideo:** Możliwość wgrywania i odtwarzania filmów z nałożoną detekcją algorytmu AI.
*  **Szybki podgląd wyników:** Wizualne zaznaczenie wykrytych kartek bezpośrednio na ekranie.

---

### 4. Instrukcja krok po kroku

#### Wykrywanie kartek ze zdjęć:
1. Wejdź na stronę główną aplikacji.
2. Wybierz zakładkę lub opcję **"Zdjęcie"** / **"Obraz"**.
3. Kliknij przycisk **"Prześlij plik"** (lub przeciągnij zdjęcie w wyznaczone pole ramki).
4. Poczekaj chwilę, aż algorytm przetworzy obraz.
5. Wynik pojawi się na ekranie – wykryte kartki zostaną otoczone ramką z oznaczeniem modelu AI.

####  Wykrywanie kartek z filmów:
1. Przejdź do zakładki **"Wideo"** lub **"Film"**.
2. Kliknij przycisk **"Wgraj wideo"** i wskaż plik filmowy ze swojego urządzenia.
3. Uruchom odtwarzanie za pomocą przycisku **Play**.
4. Algorytm w czasie rzeczywistym będzie śledził i zaznaczał kartki pojawiające się w kadrze filmu.

---

### 5. Rozwiązywanie problemów (FAQ)
* **Plik wideo/zdjęcia nie chce się wgrać:** Upewnij się, że format pliku jest wspierany (np. MP4 dla wideo, JPG/PNG dla zdjęć) oraz że plik nie przekracza dozwolonego limitu wagowego.
* **Algorytm nie wykrywa kartki:** Upewnij się, że kartka jest dobrze oświetlona, kontrastuje z tłem i znajduje się w miarę blisko obiektywu, co ułatwi detekcję sztucznej inteligencji.
– chętnie to zaktualizuję!
