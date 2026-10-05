# SlidesPresenterNotes

SlidesPresenterNotes è uno script Python che estrae il testo dalle pagine di un PDF di slide e genera delle note presentatore (in italiano) per ciascuna slide sfruttando un LLM a scelta (Groq, Gemini, Claude, OpenAI, ... tramite LiteLLM). Lo scopo è produrre testi discorsivi pronti da incollare nelle note presentatore di Apple Keynote.

## Panoramica
- Estrae il testo da ogni pagina del PDF (usa PyPDF2).
- Invia il testo estratto a un modello generativo via `call_llm` in `main.py` (LiteLLM).
- Produce un file di output in formato Markdown (.md).
- Gestisce pagine vuote ritornando `[NESSUN TESTO RILEVATO]`.

## Requisiti
- Python 3.8 o superiore
- Dipendenze (vedi `requirements.txt`). Al minimo lo script usa:
  - PyPDF2
  - tqdm
  - litellm

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

## Configurazione
Scegli il modello con `--model provider/modello` ([elenco provider](https://docs.litellm.ai/docs/providers)) ed esporta la chiave del provider:

```bash
export GROQ_API_KEY=...        # groq/meta-llama/llama-4-scout-17b-16e-instruct (default)
export GEMINI_API_KEY=...      # gemini/gemini-2.0-flash
export ANTHROPIC_API_KEY=...   # anthropic/claude-sonnet-4-5
export OPENAI_API_KEY=...      # openai/gpt-4o
```

Il modello deve supportare input immagine, altrimenti le immagini delle slide vanno rimosse.

## Uso
Scrivere l'output su file Markdown (.md):

```bash
python main.py --pdf /percorso/alle/slide.pdf --out notes.md
```

Se ometti `--out`, l'output in Markdown verrà stampato su stdout.

### Opzioni principali
- `--pdf, -p` (obbligatorio): percorso al file PDF delle slide.
- `--out, -o`: percorso del file di output (se omesso viene stampato su stdout). Il file prodotto sarà in formato Markdown (.md).
- `--model, -m`: modello LiteLLM `provider/modello` (default Groq Llama 4 Scout).
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
