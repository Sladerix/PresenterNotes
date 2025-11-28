# SlidesPresenterNotes

SlidesPresenterNotes è uno script Python che estrae il testo dalle pagine di un PDF di slide e genera delle note presentatore (in italiano) per ciascuna slide sfruttando un modello di generazione testuale (es. Gemini tramite `google.genai`). Lo scopo è produrre testi discorsivi pronti da incollare nelle note presentatore di Apple Keynote.

## Panoramica
- Estrae il testo da ogni pagina del PDF (usa PyPDF2).
- Invia il testo estratto a un modello generativo via funzione `call_gemini` in `main.py`.
- Produce un file di output in formato Markdown (.md).
- Gestisce pagine vuote ritornando `[NESSUN TESTO RILEVATO]`.

## Requisiti
- Python 3.8 o superiore
- Dipendenze (vedi `requirements.txt`). Al minimo lo script usa:
  - PyPDF2
  - tqdm
  - google-genai (o l'SDK che usi per Gemini)

## Installazione
1. Apri la cartella del progetto:

```bash
cd /percorso/SlidesPresenterNotes
```

2. Crea e attiva un virtualenv (consigliato):

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Installa le dipendenze:

```bash
pip install -r requirements.txt
```

> Nota: se `requirements.txt` non contiene `google-genai`, aggiungilo o installa il client SDK che usi per il modello.

## Configurazione
Lo script utilizza la variabile `GEMINI_API_KEY` definita in `main.py`. Per evitare di inserire la chiave nel codice, è consigliabile leggere la chiave da una variabile d'ambiente. Puoi aggiungere all'inizio di `main.py`:

```python
import os
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
```

E impostare la variabile d'ambiente nel terminale (macOS / zsh):

> Generare la tua chiave API su [Google AI Studio](https://aistudio.google.com/app/projects)

```bash
export GEMINI_API_KEY="la_tua_chiave_gemini"
```

## Uso
Scrivere l'output su file Markdown (.md):

```bash
python main.py --pdf /percorso/alle/slide.pdf --out notes.md
```

Se ometti `--out`, l'output in Markdown verrà stampato su stdout.

### Opzioni principali
- `--pdf, -p` (obbligatorio): percorso al file PDF delle slide.
- `--out, -o`: percorso del file di output (se omesso viene stampato su stdout). Il file prodotto sarà in formato Markdown (.md).
- `--model`: nome del modello Gemini da usare (opzionale).
- `--detail-level`: livello di dettaglio per le note presentatore (0-3).
- `--pages, -P`: pagine da estrarre (1-based). Esempi: "1,3-5" o "2-10". Se omesso, usa tutte le pagine.

## Flusso di lavoro consigliato
1. Preparare il PDF delle slide.
2. Esportare / impostare la chiave API come variabile d'ambiente.
3. Eseguire lo script e salvare l'output in un file .md.

## Possibili miglioramenti
- Supporto OCR per slide scannerizzate.
- Lettura sicura della chiave API da `.env` (usando `python-dotenv`) o dal sistema di secret management.
- Migliorare logging e aggiungere flag per il livello di log.
- Tests automatici per l'estrazione del testo e la logica di parsing.
- Introdurre un sistema per fornire un contesto rassiuntivo per ogni iterazione
