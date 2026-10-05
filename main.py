import argparse
import base64
import hashlib
import io
import logging
import re
import sys
from collections import Counter
from time import sleep
from typing import Dict, List

from PIL import Image
from tqdm import tqdm

logging.basicConfig(level=logging.ERROR)  # warning (immagini saltate) nascosti

# Qualsiasi modello supportato da LiteLLM, formato "provider/modello". La chiave API
# si legge dalla variabile d'ambiente del provider (GROQ_API_KEY, GEMINI_API_KEY,
# ANTHROPIC_API_KEY, OPENAI_API_KEY, ...). Vedi https://docs.litellm.ai/docs/providers
DEFAULT_MODEL = "groq/qwen/qwen3.8-27b"
EMPTY_SLIDE = "[NESSUN TESTO RILEVATO]"
SHORT_TEXT_CHARS = 250  # sotto questa soglia + immagini = slide "visiva"
REPEATED_IMAGE_PAGES = 10  # immagine presente su >= N pagine = decorativa, scartata
RATE_LIMIT_RETRIES = 5
MAX_IMAGE_SIDE = 768  # px, lato lungo: meno token immagine

# Le versioni precedenti del prompt (v1-v5) sono nella git history.
RAG = """
Sono un professore e devo tenere un corso sfruttando dei pacchi di slide che ho già.
Le slide sono in inglese, ma il corso si tiene in italiano: per ogni slide devi scrivere ciò che dirò a voce, in italiano.
Scrivi un DISCORSO ORALE in prosa, come se stessi parlando davanti ai partecipanti: frasi complete e fluide, collegate tra loro, con un tono naturale e chiaro, adatto a una lezione tecnica ma accessibile (sono corsi di formazione per persone che non lavorano direttamente nell'ambito).
Spiega e collega i concetti della slide invece di elencarli: non riprodurre la slide punto per punto, non fare elenchi puntati o numerati, non usare tabelle. Se la slide contiene un elenco, trasformalo in un ragionamento parlato (es. "innanzitutto... poi... infine...").
Usa paragrafi brevi separati da una riga vuota, così il testo si legge facilmente mentre parlo.
Formattazione consentita: solo il grassetto (**parola**) per le poche parole chiave su cui voglio mettere enfasi. Niente titoli, niente heading (#), niente separatori (---), niente elenchi.
Se ci sono termini tecnici in inglese che non hanno una traduzione italiana comune, mantienili in inglese.
Inizia direttamente con il contenuto della slide, senza introduzioni o frasi di contesto, senza saluti o formule di cortesia ("iniziamo", "buongiorno", "arrivederci", ecc.) e senza riassunto finale.
Non fare riferimento al fatto che stai generando delle note né al fatto che stai guardando una slide ("in questa slide vediamo" è da evitare: parla direttamente degli argomenti).
Se la slide ha poco testo e contiene un'immagine, un diagramma o uno schema, il contenuto vero della slide è l'immagine: osservala con attenzione, descrivi a voce ciò che mostra (elementi, relazioni, etichette, flussi, rappresentazioni, ...) e spiega perché è significativa nel contesto del titolo/testo della slide, arricchendo il discorso con le informazioni rilevanti che conosci sull'argomento. In questo caso il discorso può essere più esteso del solito, ma comunque non eccessivo.
Se una slide è vuota o non ha contenuto rispondi semplicemente con "[NESSUN TESTO RILEVATO]".
Il tuo output verrà incollato direttamente nelle note presentatore: deve contenere solo il discorso, senza altro.
"""

rag_level = [
    "Solo se pensi che sia utile aggiungere ulteriori informazioni di dettaglio sull'argomento della slide, aggiungi pure del contenuto ma con moderazione, può anche darsi che alcune cose le spieghi nelle slide successive. Mi raccomando, non esagerare.",
    "Solo se pensi che sia utile aggiungere ulteriori informazioni di dettaglio sull'argomento della slide, aggiungi pure del contenuto ma con moderazione, può anche darsi che alcune cose le spieghi nelle slide successive. Se vedi slide con poco testo, allora in quel caso si estensivo senza esagerare.",
    "Solo se pensi che sia utile aggiungere ulteriori informazioni di dettaglio sull'argomento della slide, aggiungi pure del contenuto, potrebbe essere utile avere maggiori informazioni per la spiegazione.",
    "Più contenuto c'è meglio è, quindi sentiti libero di espandere il discorso ove necessario.",
]


def parse_page_selection(selection: str | None, num_pages: int) -> List[int]:
    """Parsa "1,3-5" in una lista ordinata di numeri 1-based. ValueError se non valido."""
    if not selection:
        return list(range(1, num_pages + 1))

    pages = set()
    for part in (p.strip() for p in selection.split(',') if p.strip()):
        try:
            start, _, end = part.partition('-')
            lo, hi = int(start), int(end or start)
        except ValueError:
            raise ValueError(f"Pagina o intervallo non valido: '{part}'")
        if lo < 1 or hi < lo or hi > num_pages:
            raise ValueError(f"Pagina o intervallo fuori dai limiti: '{part}' (numero pagine: {num_pages})")
        pages.update(range(lo, hi + 1))

    return sorted(pages)


def extract_content_from_pdf(path: str, page_selection: str | None = None, with_images: bool = True, max_images: int | None = None) -> Dict[int, list]:
    """Restituisce {numero_pagina (1-based): [testo, immagine PIL, ...]} per le pagine selezionate.
    Nessun OCR: un PDF di sole immagini arriva al modello come immagini.
    """
    from pypdf import PdfReader

    reader = PdfReader(path)
    selected = parse_page_selection(page_selection, len(reader.pages))

    pdf_content: Dict[int, list] = {}
    digests: Dict[int, list] = {}  # pagina -> hash immagini, per scartare quelle ripetute
    for page_number in selected:
        page = reader.pages[page_number - 1]

        try:
            text = page.extract_text() or ""
        except Exception as e:
            text = ""
            logging.error(f"Pagina {page_number}: estrazione testo fallita: {e}")

        images, hashes = [], []
        try:
            n_images = len(page.images) if with_images else 0
        except Exception as e:
            n_images = 0
            logging.warning(f"Pagina {page_number}: lista immagini fallita: {e}")
        for i in range(n_images):
            # una per una: alcuni modi immagine possono fallire decodificare alcuni modi (es. PA), si salta solo quell'immagine
            try:
                data = page.images[i].data
                images.append(Image.open(io.BytesIO(data)))
                hashes.append(hashlib.md5(data).hexdigest())
            except Exception as e:
                logging.warning(f"Pagina {page_number}: immagine {i} saltata: {e}")

        pdf_content[page_number] = [text, *images]
        digests[page_number] = hashes

    # logo/sfondi: stessa immagine su >= REPEATED_IMAGE_PAGES pagine -> non la rimando al modello
    counts = Counter(h for hs in digests.values() for h in set(hs))
    for n, content in pdf_content.items():
        keep = [img for img, h in zip(content[1:], digests[n]) if counts[h] < REPEATED_IMAGE_PAGES]
        if max_images is not None:  # tiene le N più grandi (le piccole sono di solito icone)
            keep = sorted(keep, key=lambda im: im.width * im.height, reverse=True)[:max_images]
        pdf_content[n] = [content[0], *keep]

    return pdf_content


def pil_to_data_uri(img: Image.Image) -> str:
    buf = io.BytesIO()
    img = img.convert("RGB")
    img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    img.save(buf, format="PNG")  # RGB: PNG non salva CMYK
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"


def call_llm(system: str, page_content: list, model: str, temperature: float = 0.6, max_tokens: int = 1000) -> str:
    """Una chiamata LiteLLM per slide. Solleva eccezione su errore (il chiamante decide)."""
    import litellm
    from litellm import RateLimitError, completion
    litellm.suppress_debug_info = True  # niente banner "Give Feedback" a ogni errore

    text = page_content[0].strip() or EMPTY_SLIDE
    if len(page_content) > 1 and len(text) < SHORT_TEXT_CHARS:
        text += "\n\n[NOTA: questa slide ha poco testo; l'immagine allegata è il contenuto principale: descrivila e spiegala in modo arricchito.]"
    user_content = [{"type": "text", "text": text}]
    for img in page_content[1:]:
        try:
            user_content.append({"type": "image_url", "image_url": {"url": pil_to_data_uri(img)}})
        except Exception as e:
            logging.error(f"Immagine ignorata: {e}")

    kwargs = dict(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user_content}],
        temperature=temperature,
        max_tokens=max_tokens,
        num_retries=3,  # errori transitori; i rate limit li gestisce il ciclo sotto
    )
    for attempt in range(RATE_LIMIT_RETRIES + 1):
        try:
            response = completion(**kwargs)
            break
        except RateLimitError as e:
            if attempt == RATE_LIMIT_RETRIES:
                raise
            # i provider dicono quanto aspettare: "Please try again in 4.875s" / "1m2.5s"
            m = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", str(e))
            wait = (int(m.group(1) or 0) * 60 + float(m.group(2)) + 1) if m else 15
            tqdm.write(f"Rate limit: attendo {wait:.0f}s e riprovo ({attempt + 1}/{RATE_LIMIT_RETRIES})")
            sleep(wait)
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("risposta vuota dal modello")
    return content.strip()


def write_output(responses: Dict[int, str], out_path: str | None = None) -> None:
    md = "".join(f"# Slide {idx}\n\n{responses[idx]}\n\n---\n\n" for idx in sorted(responses))
    if out_path:
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(md)
    else:
        print(md)


def main() -> None:
    parser = argparse.ArgumentParser(description='Genera note presentatore in italiano da un PDF di slide usando un LLM a scelta.')
    parser.add_argument('--pdf', '-p', required=True, help='Percorso al file PDF delle slide')
    parser.add_argument('--out', '-o', help='File di output (se omesso stampa su stdout)')
    parser.add_argument('--detail-level', help='Livello di dettaglio per le note presentatore (0-3)', type=int, choices=[0, 1, 2, 3], default=0)
    parser.add_argument('--model', '-m', default=DEFAULT_MODEL,
                        help=f'Modello LiteLLM "provider/modello", es. gemini/gemini-2.0-flash, anthropic/claude-sonnet-4-5 (default: {DEFAULT_MODEL})')
    parser.add_argument('--pages', '-P', help='Pagine da estrarre (1-based). Esempi: "1,3-5" o "2-10". Se omesso, usa tutte le pagine.')
    parser.add_argument('--no-images', action='store_true', help='Non inviare le immagini al modello (molto meno token)')
    parser.add_argument('--max-images', type=int, metavar='N', help='Massimo N immagini per slide (le più grandi), per modelli con limiti es. Groq free = 3')
    args = parser.parse_args()

    system = RAG + rag_level[args.detail_level]
    print(f"Modello: {args.model} | livello di dettaglio: {args.detail_level}", file=sys.stderr)

    try:
        pages = extract_content_from_pdf(args.pdf, page_selection=args.pages, with_images=not args.no_images, max_images=args.max_images)
    except Exception as e:
        logging.error(f"Errore durante l'estrazione del PDF: {e}")
        sys.exit(2)

    responses: Dict[int, str] = {}
    for page_number, page_content in tqdm(pages.items(), unit="slide"):
        if not page_content[0].strip() and len(page_content) == 1:
            responses[page_number] = EMPTY_SLIDE
            continue
        try:
            responses[page_number] = call_llm(system, page_content, args.model)
        except Exception as e:
            logging.error(f"Slide {page_number}: {e}")
            responses[page_number] = f"[ERROR] {e}"

    write_output(responses, out_path=args.out)


if __name__ == '__main__':
    main()
