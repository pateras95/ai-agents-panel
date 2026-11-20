# NEXUS AI

Τοπική προβολή ορίων Claude Code και Codex, μαζί με το ιστορικό ημερήσιων stand-up.

## Εκτέλεση στο Ubuntu

Από τον κεντρικό φάκελο του project:

```bash
npm --prefix frontend ci
npm --prefix frontend run build
python3 -B -m backend.web --bind 192.168.1.138 --port 8766
```

Για προβολή στο τερματικό, τρέξε `python3 -B -m backend.limits`.

Χρησιμοποίησε την τρέχουσα IPv4 του Ubuntu στο Wi-Fi αν η διεύθυνση έχει αλλάξει. Άνοιξε στο Safari του iPhone τη διεύθυνση που εμφανίζει ο server, όσο οι δύο συσκευές βρίσκονται στο ίδιο Wi-Fi.

## Δομή

- `backend/` · Ανάγνωση ορίων και αναφορών, HTTP server.
- `frontend/` · Dashboard Vue 3 και Vuetify. Ο Python server σερβίρει το τοπικό build και το JSON API.
- `reports/` · Μία ημερήσια αναφορά ανά αρχείο `YYYY-MM-DD.json`.

Για νέα αναφορά, πρόσθεσε αρχείο με την ημερομηνία και τρεις λίστες κειμένου, `completed`, `next` και `blockers`. Πάτησε **Ανανέωση** στη σελίδα. Η πιο πρόσφατη ημερομηνία εμφανίζεται πρώτη.
