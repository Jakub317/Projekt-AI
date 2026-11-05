1-- Problem i wartość
Projekt ma usprawnić obsługę fizycznych dokumentów poprzez wykrywanie kartek na półkach i docelowo rejestrowanie ich przyjęcia oraz odbioru. Może ograniczyć ręczne sprawdzanie korespondencji i pomóc w pilnowaniu terminów.
Brakuje jednak pomiarów potwierdzających korzyści: czasu zaoszczędzonego przez pracownika, liczby obsługiwanych dokumentów czy kosztu działania. Obecna implementacja obejmuje tylko fragment przedstawionej wizji.
Zalecenia:  Określić użytkownika, przebieg obsługi oraz kryteria sukcesu. Zmierzyć czas zaoszczędzony względem obsługi ręcznej, liczbę pominiętych zdarzeń i fałszywych powiadomień. Pozwoli to ocenić praktyczną wartość rozwiązania.

2-- AI
Wykorzystano gotowy model YOLO11n, dostrajany do własnych danych. To uzasadniony wybór dla prototypu wykrywania obiektów. Skrypt pozwala ustawiać m.in. rozmiar obrazu i urządzenie obliczeniowe.
Występuje niespójność: instrukcja opisuje jedną klasę „kartka”, natomiast konfiguracja zawiera klasy „kartka” i „polka”. Nie przedstawiono również porównania z prostszą metodą, np. wykrywaniem zmian obrazu przy nieruchomej kamerze.
Zalecenie: ujednolicić klasy czyli czy model ma rozpoznawać kartki czy półki czy obie klasy 

3-- Kod
Data.yaml zawiera bezwzględną ścieżkę do katalogu na komputerze autora, co utrudnia uruchomienie projektu na innym urządzeniu. - Rozwiązanie: zmiana ścieżki na ścieżkę względną, która będzie działać u każdego.
model_test.py zlicza wszystkie wykryte obiekty jako kartki. Przy modelu rozpoznającym również półki wynik będzie nieprawidłowy.brak pliku  modelu ai - Rozwiązanie: Wprowadzić rozwiązanie umożliwiające na osobne wykrywanie półek, oraz kartek, 
Kolejne treningi korzystają z tego samego katalogu wynikowego, co utrudnia rozdzielenie eksperymentów. - Rozwiązanie: Zmiana katalogu wynikowego, co ułatwi katalogowanie, oraz prawidłowe sprawdzanie otrzymanych wyników.

4-- Jakość wyników
Przez brak dostarczenia modelu sztucznej inteligencji,można zobaczyć wyniki dostarczone przez autorów projektu na GitHub.

5-- Dane
Model korzysta ze zdjęć kartek i półek z oznaczonymi obiektami, niestety obejmuje tylko 9 unikalnych zdjęć, a walidacja nie zawiera oznaczeń klasy „półka”. - Rozwiązanie: Zebrać bardziej różnorodne zdjęcia, ujednolicić oznaczenia i utworzyć rozłączne zbiory treningowy, walidacyjny i testowy.

6-- UX i Wizualizacja

7-- Dokumentacja
    
  Zamiast 2 osobnych plików README.md powinnien być tylko jeden, podzielony na instalacje i obsługę.

  README.md
  1. Nie czytelene instrukcję, do przy poleceniu git clone powinnien być tylko jeden link bez nawiasów.
  2. Tekst kóry nie jest poleceniem powinnien być zakomentowany
  3. Polecenie aktywacji instalacji dla windows jak i linux nie jest oznaczone jako polecenie tylko zwykły tekst
  4. Hiperłącza spisu treści na stronie nie przekierowywuja do odpowiedniej części strony
  5. Niejasna instrukja gdzie znaleść pliki potrzebne do instalacji
  
  Dokumentacja główna
  1. Niekompletna dokumentacja:
     a. Brak planu projektu
     b. Brak spisu użytch narzędzi.
     c. Brak opisu działania aplikacji i funkcji
  
8-- Etyka i Ryzyka
    1. Brak możliwości ograniczenia kadru kamery do obszaru potrzebnego do wykrywania dokumentów.
    2. Zapewnić ręcze zatwierdzenie i korygowanie wprowadzanych danych.
    3. Zabezpieczyć dane o przechowywanych twarzach.
    4. Szansa wycieku danych osobowych/twarzy.
