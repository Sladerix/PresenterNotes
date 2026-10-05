import argparse
import base64
import io
import logging
import sys
from typing import Dict, List

from PIL import Image
from tqdm import tqdm

logging.basicConfig(level=logging.ERROR)  # warning (immagini saltate) nascosti

# Qualsiasi modello supportato da LiteLLM, formato "provider/modello". La chiave API
# si legge dalla variabile d'ambiente del provider (GROQ_API_KEY, GEMINI_API_KEY,
# ANTHROPIC_API_KEY, OPENAI_API_KEY, ...). Vedi https://docs.litellm.ai/docs/providers
DEFAULT_MODEL = "groq/meta-llama/llama-4-scout-17b-16e-instruct"
EMPTY_SLIDE = "[NESSUN TESTO RILEVATO]"

# Le versioni precedenti del prompt (v1-v5) sono nella git history.
RAG = """
Sono un professore, devo tenere un corso, sfruttando determinati pacchi di slide che ho già.
Le slide sono scritte in inglese, ma per questioni di sicurezza nel discorso orale ho bisogno di generare le note presentatore per ogni slide in italiano in un file markdown (.md).
Se ci sono termini tecnici in inglese che non hanno una traduzione italiana comune, mantienili in inglese.
Le note presentatore devono ricalcare il contenuto di ogni slide, sottoforma di discorso orale adatto ad una lezione tecnica ma non troppo (si tratta di corsi di formazione per persone che non sono direttamente coinvolte nell'ambito in questione).
Le note presentatore in output devono essere scritte in Markdown (.md) sfruttando tutti gli headings, sottotitoli e elenchi, in modo da ottimizzare la struttura e la leggibilità per il lettore.
è importante sfruttare la sintassi di markdown per rispettare la gerarchia dei contenuti nella slide (sottocapitoli, elenchi puntati o numerati, sotto elenchi).
Formatta diversamente il testo per catturare l'attenzione sulle parole chiave dove necessario (es. bold, italic, ecc...).
Non inserire il titolo principale di ogni slide perchè ci penserò io a metterlo dopo, quindi non inserire nessun heading di primo o secondo livello (#, ##) parti con headings di secondo livello (###).
Non inserire MAI separatori markdown orizzontali (---).
è importantissimo che inizi il discorso direttamente con il contenuto della slide, senza introduzioni o frasi di contesto.
L'output della generazione deve contenere solamente il testo che ti ho chiesto, senza ulteriori frasi, in modo tale che io possa accoppiare il contenuto dell'output direttamente nelle note presentatore senza avere rumore.
Evita parole discorsive o di cortesia come "iniziamo, "buongiorno", "buonasera", "arriverderci", o simili. Non devi preparare l'intero discorso, ma solamente quello legato al contenuto delle slides.
Non devi fare riferimento al fatto che stai generando delle note presentatore.
Non fare il riassunto finale della slide.
Se una slide è vuota o non ha contenuto rispondi semplicemente con "[NESSUN TESTO RILEVATO]".
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


def extract_content_from_pdf(path: str, page_selection: str | None = None) -> Dict[int, list]:
    """Restituisce {numero_pagina (1-based): [testo, immagine PIL, ...]} per le pagine selezionate.
    Nessun OCR: un PDF di sole immagini arriva al modello come immagini.
    """
    from PyPDF2 import PdfReader

    reader = PdfReader(path)
    selected = parse_page_selection(page_selection, len(reader.pages))

    pdf_content: Dict[int, list] = {}
    for page_number in selected:
        page = reader.pages[page_number - 1]

        try:
            text = page.extract_text() or ""
        except Exception as e:
            text = ""
            logging.error(f"Pagina {page_number}: estrazione testo fallita: {e}")

        images = []
        try:
            n_images = len(page.images)
        except Exception as e:
            n_images = 0
            logging.warning(f"Pagina {page_number}: lista immagini fallita: {e}")
        for i in range(n_images):
            # una per una: PyPDF2 non sa decodificare alcuni modi (es. PA), si salta solo quell'immagine
            try:
                images.append(Image.open(io.BytesIO(page.images[i].data)))
            except Exception as e:
                logging.warning(f"Pagina {page_number}: immagine {i} saltata: {e}")

        pdf_content[page_number] = [text, *images]

    return pdf_content


def pil_to_data_uri(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")  # RGB: PNG non salva CMYK
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"


def call_llm(system: str, page_content: list, model: str, temperature: float = 0.6, max_tokens: int = 800) -> str:
    """Una chiamata LiteLLM per slide. Solleva eccezione su errore (il chiamante decide)."""
    from litellm import completion

    text = page_content[0].strip() or EMPTY_SLIDE
    user_content = [{"type": "text", "text": text}]
    for img in page_content[1:]:
        try:
            user_content.append({"type": "image_url", "image_url": {"url": pil_to_data_uri(img)}})
        except Exception as e:
            logging.error(f"Immagine ignorata: {e}")

    response = completion(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user_content}],
        temperature=temperature,
        max_tokens=max_tokens,
        num_retries=3,  # gestisce rate limit / errori transitori
    )
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
    args = parser.parse_args()

    system = RAG + rag_level[args.detail_level]
    print(f"Modello: {args.model} | livello di dettaglio: {args.detail_level}", file=sys.stderr)

    try:
        pages = extract_content_from_pdf(args.pdf, page_selection=args.pages)
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
