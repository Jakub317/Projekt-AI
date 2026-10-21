
# OmniPost & SmartShelf AI 🌍📦

> Od Inteligentnego Regału Biurowego do Globalnej Kontroli Chaosu Logistycznego.

## 🚀 O Projekcie

Projekt łączy systemy wizyjne (Computer Vision) oraz sztuczną inteligencję w celu automatyzacji i monitorowania fizycznego obiegu korespondencji. System działa w dwóch trybach:

1. **SmartShelf (Biuro):** Kontrola zajętości dedykowanych półek klienckich i monitorowanie czasu SLA.
2. **OmniPost (Globalny):** Zarządzanie chaotycznymi strefami zrzutu listów (np. "Model Grecki") przy użyciu analizy różnicowej obrazu oraz modułu OCR.

---

## 📸 Wizualizacja Systemu

### 1. Monitoring Uporządkowany (Regał Biurowy)

![Regał Biurowy](docs/images/ai1.jpg)

### 2. Zarządzanie Chaosem (Model Grecki / Sterta)

![Model Grecki](docs/images/ai2.jpg)

### 3. Interfejs Operacyjny i Analityka (Kokpit VPS)

![Kokpit Systemu](docs/images/ai3.jpg)

---

## 🛠️ Architektura Techniczna

Aplikacja została zaprojektowana do wdrożenia na serwerze VPS:

- **Backend:** Python (FastAPI / Flask) + SQLite
- **Frontend / Kokpit:** Panel analityczny z wbudowanym "Generatorem Chaosu" do celów demonstracyjnych.
- **Weryfikacja:** Dowolny smartfon jako mobilna kamera przesyłająca ujęcia do bramki API.
