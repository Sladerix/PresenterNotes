# SlidesPresenterNotes

SlidesPresenterNotes è uno script Python che estrae il testo dalle pagine di un PDF di slide e genera delle note presentatore (in italiano) per ciascuna slide sfruttando un LLM a scelta (Groq, Gemini, Claude, OpenAI, ... tramite LiteLLM). Lo scopo è produrre testi discorsivi pronti da incollare nelle note presentatore di Apple Keynote.

## Panoramica
- Estrae il testo da ogni pagina del PDF (usa pypdf).
- Invia il testo estratto a un modello generativo via `call_llm` in `presenternotes.py` (LiteLLM).
- Produce un file di output in formato Markdown (.md).
- Gestisce pagine vuote ritornando `[NESSUN TESTO RILEVATO]`.

## Requisiti
- Python 3.8 o superiore
- Dipendenze (vedi `pyproject.toml`). Al minimo lo script usa:
  - pypdf
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
pip install -e .
```

## Configurazione
Scegli il modello con `--model provider/modello` ([elenco provider](https://docs.litellm.ai/docs/providers)) ed esporta la chiave del provider:

```bash
export GROQ_API_KEY=...        # groq/qwen/qwen3.8-27b (default)
export GEMINI_API_KEY=...      # gemini/gemini-2.0-flash
export ANTHROPIC_API_KEY=...   # anthropic/claude-sonnet-4-5
export OPENAI_API_KEY=...      # openai/gpt-4o
export OPENROUTER_API_KEY=...  # openrouter/<id modello OpenRouter>, es. openrouter/google/gemini-2.0-flash-001
export NVIDIA_NIM_API_KEY=...   # nvidia_nim/<id modello NIM>, es. nvidia_nim/meta/llama-3.2-90b-vision-instruct
```

Il modello deve supportare input immagine, altrimenti usa `--no-images`.

Esempio con Nvidia NIM (modello `moonshotai/kimi-k3`, l'ID va preso da [build.nvidia.com](https://build.nvidia.com/models)):

```bash
export NVIDIA_NIM_API_KEY=nvapi-...
presenternotes -p slides.pdf -m nvidia_nim/moonshotai/kimi-k3 --no-images --max-tokens 4000
```

`--no-images` serve se il modello è solo testuale; `--max-tokens` alto se è un modello "reasoning" (ragiona prima di rispondere e può finire i token senza produrre testo).

## Uso
Scrivere l'output su file Markdown (.md):

```bash
presenternotes --pdf /percorso/alle/slide.pdf --out notes.md
```

Se ometti `--out`, l'output viene scritto in `./presenternotes/<nome del pdf>.md` (cartella creata nella directory da cui lanci il comando).

### Opzioni principali
- `--pdf, -p` (obbligatorio): percorso al file PDF delle slide.
- `--out, -o`: percorso del file di output (default: `./presenternotes/<nome del pdf>.md`). Il file prodotto sarà in formato Markdown (.md).
- `--model, -m`: modello LiteLLM `provider/modello` (default `groq/qwen/qwen3.8-27b`).
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
