# SlidesPresenterNotes

SlidesPresenterNotes è uno script Python che estrae il testo dalle pagine di un PDF di slide e genera delle note presentatore (in italiano) per ciascuna slide sfruttando un modello di generazione testuale (es. Gemini tramite `google.genai`). Lo scopo è produrre testi discorsivi pronti da incollare nelle note presentatore di Apple Keynote.

## Panoramica
- Estrae il testo da ogni pagina del PDF (usa PyPDF2).
- Invia il testo estratto a un modello generativo via funzione `call_gemini` in `main.py`.
- Produce un file di output in formato plain (testo) o JSON.
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

```bash
export GEMINI_API_KEY="la_tua_chiave_gemini"
```

## Uso
Scrivere l'output su file (formato plain):

```bash
python main.py --pdf /percorso/alle/slide.pdf --out notes.txt
```


### Opzioni principali
- `--pdf, -p` (obbligatorio): percorso al file PDF delle slide.
- `--out, -o`: percorso del file di output (se omesso viene stampato su stdout).
- `--model`: nome del modello Gemini da usare (opzionale).
- `--format`: `plain` o `json` (default: `plain`).

## Dettagli tecnici
- L'estrazione del testo è effettuata con PyPDF2. Se il PDF contiene solo immagini (es. scan), PyPDF2 non ricaverà testo utile. Per documenti scannerizzati è necessario usare OCR (`pdf2image` + `pytesseract`) e integrare l'OCR dentro `extract_content_from_pdf`.
- Se una pagina è vuota o non contiene testo rilevato, lo script restituisce la stringa: `[NESSUN TESTO RILEVATO]`.
- Il prompt usato per la generazione (variabili `rag_v1` / `rag_v2` in `main.py`) è pensato per produrre un testo discorsivo in italiano e senza frasi di cortesia o introduzioni. Puoi modificarlo per adattarlo al tuo stile.
- C'è una limitazione semplice delle richieste (`max_rpm = 10`) per non superare un rate limit; adattala in base alle policy del provider.
- La funzione `call_gemini` usa il client `google.genai` ma alcuni SDK potrebbero avere interfacce diverse; in caso di errore aggiorna la chiamata alle API secondo la documentazione del client che usi.

## Flusso di lavoro consigliato
1. Preparare il PDF delle slide.
2. Esportare / impostare la chiave API come variabile d'ambiente.
3. Eseguire lo script e salvare l'output.
4. Aprire il file prodotto e copiare le note nella sezione presentatore di Keynote.

## Possibili miglioramenti
- Supporto OCR per slide scannerizzate.
- Lettura sicura della chiave API da `.env` (usando `python-dotenv`) o dal sistema di secret management.
- Migliorare logging e aggiungere flag per il livello di log.
- Tests automatici per l'estrazione del testo e la logica di parsing.
