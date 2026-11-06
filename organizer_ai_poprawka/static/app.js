
const form = document.querySelector('#form');
const file = document.querySelector('#video');
const start = document.querySelector('#start');

let timer = null;

// Zmiana wybranego pliku
file.addEventListener('change', () => {
    document.querySelector('#filename').textContent =
        file.files[0]?.name || 'Nie wybrano pliku';
});

// Rozpoczęcie analizy
form.addEventListener('submit', async e => {
    e.preventDefault();

    if (!file.files.length) return;

    start.disabled = true;
    start.textContent = 'Przesyłanie…';

    document.querySelector('#progress').classList.add('visible');
    document.querySelector('#error').textContent = '';

    const data = new FormData();
    data.append('video', file.files[0]);

    try {
        const r = await fetch('/api/analyze', {
            method: 'POST',
            body: data
        });

        const j = await r.json();

        if (!r.ok) throw Error(j.error || 'Błąd uruchamiania');

        if (timer) clearInterval(timer);

        timer = setInterval(refresh, 1500);
        await refresh();

    } catch (err) {
        document.querySelector('#error').textContent = err.message;
        start.disabled = false;
        start.textContent = 'Spróbuj ponownie';
    }
});


// WYŚWIETLANIE 8 PRZEGRÓDEK
function renderSlots(slots) {
    const grid = document.querySelector('#slots-grid');

    if (!grid) {
        console.error('Nie znaleziono elementu #slots-grid w HTML');
        return;
    }

    const names = {
        occupied: 'Zajęta',
        empty: 'Pusta',
        unknown: 'Brak danych'
    };

    grid.innerHTML = '';

    for (let i = 1; i <= 8; i++) {
        const state = slots?.[String(i)] || 'unknown';

        const card = document.createElement('div');
        card.className = `slot-card slot-${state}`;

        const number = document.createElement('div');
        number.className = 'slot-number';
        number.textContent = `Przegródka ${i}`;

        const status = document.createElement('div');
        status.className = 'slot-status';
        status.textContent = names[state] || names.unknown;

        card.appendChild(number);
        card.appendChild(status);

        grid.appendChild(card);
    }
}


// ODŚWIEŻANIE STATUSU ANALIZY
async function refresh() {
    try {
        const response = await fetch('/api/status');
        const s = await response.json();

        // Aktualizacja podglądu przegródek
        renderSlots(s.slots);

        const names = {
            idle: 'Oczekiwanie',
            queued: 'W kolejce',
            running: 'W trakcie',
            completed: 'Zakończona',
            error: 'Błąd'
        };

        document.querySelector('#status-short').textContent =
            names[s.status] || s.status;

        document.querySelector('#status-message').textContent = s.message;
        document.querySelector('#progress-title').textContent =
            names[s.status] || s.status;

        document.querySelector('#message').textContent = s.message;
        document.querySelector('#percent').textContent =
            (s.progress || 0) + '%';

        document.querySelector('#bar').style.width =
            (s.progress || 0) + '%';

        if (s.status === 'completed') {
            clearInterval(timer);
            timer = null;

            start.disabled = false;
            start.textContent = 'Analizuj kolejne nagranie';

            const panel = document.querySelector('#result');
            panel.hidden = false;

            if (s.video_ready) {
                const video = document.querySelector('#video-result');
                video.src = `/results/${s.id}/annotated_video.mp4`;
                video.load();
            }

            if (s.report_ready) {
                document.querySelector('#report').href =
                    `/results/${s.id}/raport.csv`;
            }

            await loadEvents();
        }

        if (s.status === 'error') {
            clearInterval(timer);
            timer = null;

            start.disabled = false;
            start.textContent = 'Spróbuj ponownie';

            document.querySelector('#error').textContent =
                s.error || 'Nieznany błąd';
        }

    } catch (e) {
        console.error('Błąd odświeżania:', e);
    }
}


// HISTORIA ZDARZEŃ
async function loadEvents() {
    const data = await fetch('/api/events').then(r => r.json());
    const body = document.querySelector('#events');

    document.querySelector('#count').textContent =
        data.events.length + ' zdarzeń';

    if (!data.events.length) {
        body.innerHTML =
            '<tr><td colspan="3" class="empty">Nie zarejestrowano zmian.</td></tr>';
        return;
    }

    body.innerHTML = data.events.map(x => {
        const add = (x.typ || '').toUpperCase().includes('DODANIE');

        return `
            <tr>
                <td>${esc(x.czas_filmu || '')}</td>
                <td>Przegródka ${esc(x.przegrodka || '?')}</td>
                <td>${add ? 'Dodanie' : 'Usunięcie'}</td>
            </tr>
        `;
    }).join('');
}


// ZABEZPIECZENIE TEKSTU HTML
function esc(s) {
    return String(s).replace(/[&<>"']/g, c => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[c]));
}


// URUCHOMIENIE PO ZAŁADOWANIU STRONY
(async () => {
    await refresh();

    const s = await fetch('/api/status')
        .then(r => r.json())
        .catch(() => null);

    if (s && ['queued', 'running'].includes(s.status)) {
        document.querySelector('#progress').classList.add('visible');
        timer = setInterval(refresh, 1500);
    }
})();
