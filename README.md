SlidesPresenterNotes
=====================

Script CLI Python per estrarre testo da un PDF (una pagina = una slide) e inviare il testo di ogni slide a Google Gemini (tramite `google.genai`).

Installazione
------------
Consiglio di usare un virtualenv:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Uso
---
Esempio di esecuzione:

```bash
python main.py --pdf slides.pdf --prompt "{page_text}\n\nGenera le note presentatore in italiano:" --out notes.txt
```

Argomenti principali
- --pdf / -p: percorso al file PDF (obbligatorio)
- --prompt: template del prompt; usare `{page_text}` dove inserire il testo della slide. Se omesso, viene usato un prompt predefinito in italiano.
- --out / -o: file di output (se assente, stampa su stdout)
- --model: nome del modello Gemini (opzionale)
- --format: `plain` o `json`
- --ocr: provare l'OCR per le pagine senza testo (richiede dipendenze aggiuntive e Tesseract installato)

Nota sul client `google.genai`
----------------------------
Le API del client possono variare tra le versioni. `main.py` prova due modalità comuni di chiamata. Se la tua versione del pacchetto espone un'API diversa, adatta la funzione `call_gemini` nel file.

OCR
---
Il codice include un commento su come estendere con OCR; non è implementato di default.

Limitazioni e miglioramenti
- Aggiungere retry con backoff per chiamate all'API.
- Supporto concorrente per inviare più slide in parallelo.
- Output in file separati per slide.

