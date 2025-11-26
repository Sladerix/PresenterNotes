import argparse
import io
import sys
import logging
from datetime import datetime
from time import sleep
from typing import List, Dict
from tqdm import tqdm
from PIL import Image
import os
from google import genai

logging.basicConfig(level=logging.ERROR)

parser = argparse.ArgumentParser(description='Estrai testo da un PDF per slide e invia ogni slide a Gemini (Google genai).')
parser.add_argument('--pdf', '-p', required=True, help='Percorso al file PDF delle slide')
parser.add_argument('--out', '-o', help='File di output (se omesso stampa su stdout)')
parser.add_argument('--detail-level', help='Livello di dettaglio per le note presentatore (0-3)', type=int, choices=[0, 1, 2, 3], default=0)
parser.add_argument('--model', help='Nome del modello Gemini da usare (opzionale)', default=None)
parser.add_argument('--pages', '-P', help='Pagine da estrarre (1-based). Esempi: "1,3-5" o "2-10". Se omesso, usa tutte le pagine.', default=None)
args = parser.parse_args()

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')



rag_v1 = """
Sono un professore e devo tenere un corso di otto ore sfruttando determinati pacchi di slide che ho già.
Le slide sono scritte in inglese, però per una sicurezza maggiore nel discorso (siccome il corso sarà in italiano) vorrei avere tutte le note presentatore scritte in italiano per ogni slide in modo da fare un discorso abbastanza esteso per ognuna ed essere sicuro di non finire mai il materiale che ho a disposizione.
Generarmi le note presentatore da inserire su Apple Keynote come se fosse un discorso orale, piuttosto che scritto.
In output NON aggiungere altre frasi se non quelle del discorso in modo tale che io possa copiarle ed incollarle direttamente nelle note presentatore.
Se una slide è vuota o non ha testo, rispondi semplicemente con "[NESSUN TESTO RILEVATO]".
Non usare formattazione particolare per il testo perchè le note presentatore di Apple Keynote non le supportano, piuttosto usa una formattazione basata su spazi, invii e tab per ottmizzare la leggibilità.
Se pensi che utile aggiungere ulteriori dettagli fallo pure.
l'output deve essere un testo discorsivo orale sulla slide che ti ho passato, senza aggiungere altro (nemmeno buongiorno, arrivederci o simili), nemmeno il riassunto finale.
Non è necessario che tu faccia riferimento al fatto che stai generando delle note presentatore, semplicemente genera il discorso orale da fare per la slide.
Assolutamente non devi inserire frasi di circostanza o simili, nessun "buongiorno", "arrivederci" ecc..
"""

rag_v2 = """
Sono un professore, devo tenere un corso di otto ore, sfruttando determinati pacchi di slide che ho già.
Le slide sono scritte in inglese, ma per questioni di sicurezza nel discorso orale ho bisogno di generare le note presentatore per Apple Keynote per ogni slide in italiano.
Le note presentatore devono ricalcare il contenuto di ogni slide, sottoforma di discorso orale adatto ad una lezione tecnica ma non troppo (si tratta di costi di formazione per persone che non sono direttamente nell'ambito in questione).
Non usare formattazione particolare per il testo, perché le note presentatori di Apple Keynote non le supportano, piuttosto usa una formattazione basata su spazi, invii e TAB, in modo da ottimizzare la leggibilità (PER ME) nel momento in cui andrò a presentare le slide.
L'output della generazione deve contenere solamente il testo che ti ho chiesto, senza ulteriori frasi, in modo tale che io possa accoppiare il contenuto dell'output direttamente nelle note presentatore senza avere rumore.
Se una slide è vuota o non ha contenuto rispondi semplicemente con "[NESSUN TESTO RILEVATO]".
Se pensi che sia utile aggiungere ulteriori informazioni di dettaglio sull'argomento della slide, fallo pure, più contenuto c'è meglio è.
Evita parole discorsive o di cortesia come "iniziamo, "buongiorno", "buonasera", "arriverderci", o simili, non devi preparare l'intero discorso, ma solamente quello legato al contenuto delle slide.
Non devi fare riferimento al fatto che stai generando delle note presentatore.
Non fare il riassunto finale della slide.
"""

rag_v3 = """
Sono un professore, devo tenere un corso di otto ore, sfruttando determinati pacchi di slide che ho già.
Le slide sono scritte in inglese, ma per questioni di sicurezza nel discorso orale ho bisogno di generare le note presentatore per Apple Keynote per ogni slide in italiano.
Le note presentatore devono ricalcare il contenuto di ogni slide, sottoforma di discorso orale adatto ad una lezione tecnica ma non troppo (si tratta di costi di formazione per persone che non sono direttamente nell'ambito in questione).
Le note presentatore in output devono essere scritte in Markdown (.md) sfruttando titolo, sottotitoli e elenchi, in modo da ottimizzare la leggibilità (PER ME) nel momento in cui andrò a presentare le slide.
L'output della generazione deve contenere solamente il testo che ti ho chiesto, senza ulteriori frasi, in modo tale che io possa accoppiare il contenuto dell'output direttamente nelle note presentatore senza avere rumore.
Se una slide è vuota o non ha contenuto rispondi semplicemente con "[NESSUN TESTO RILEVATO]".
Se pensi che sia utile aggiungere ulteriori informazioni di dettaglio sull'argomento della slide, fallo pure, più contenuto c'è meglio è.
Evita parole discorsive o di cortesia come "iniziamo, "buongiorno", "buonasera", "arriverderci", o simili, non devi preparare l'intero discorso, ma solamente quello legato al contenuto delle slide.
Non devi fare riferimento al fatto che stai generando delle note presentatore.
Non fare il riassunto finale della slide.
"""

rag_v4 = """
Sono un professore, devo tenere un corso, sfruttando determinati pacchi di slide che ho già.
Le slide sono scritte in inglese, ma per questioni di sicurezza nel discorso orale ho bisogno di generare le note presentatore per ogni slide in italiano.
Le note presentatore devono ricalcare il contenuto di ogni slide, sottoforma di discorso orale adatto ad una lezione tecnica ma non troppo (si tratta di cosri di formazione per persone che non sono direttamente nell'ambito in questione).
Le note presentatore in output devono essere scritte in Markdown (.md) sfruttando titolo, sottotitoli e elenchi, in modo da ottimizzare la leggibilità (PER ME) nel momento in cui andrò a presentare le slide.
L'output della generazione deve contenere solamente il testo che ti ho chiesto, senza ulteriori frasi, in modo tale che io possa accoppiare il contenuto dell'output direttamente nelle note presentatore senza avere rumore.
Se una slide è vuota o non ha contenuto rispondi semplicemente con "[NESSUN TESTO RILEVATO]".
Solo se pensi che sia utile aggiungere ulteriori informazioni di dettaglio sull'argomento della slide, aggiungi pure del contenuto ma con moderazione, può anche darsi che alcune cose le spieghi nelle slide successive. Mi raccomendo, non esagerare.
Evita parole discorsive o di cortesia come "iniziamo, "buongiorno", "buonasera", "arriverderci", o simili, non devi preparare l'intero discorso, ma solamente quello legato al contenuto delle slide.
Non devi fare riferimento al fatto che stai generando delle note presentatore.
Non fare il riassunto finale della slide.
"""

rag_v5 = """
Sono un professore, devo tenere un corso, sfruttando determinati pacchi di slide che ho già.
Le slide sono scritte in inglese, ma per questioni di sicurezza nel discorso orale ho bisogno di generare le note presentatore per ogni slide in italiano.
Le note presentatore devono ricalcare il contenuto di ogni slide, sottoforma di discorso orale adatto ad una lezione tecnica ma non troppo (si tratta di cosri di formazione per persone che non sono direttamente nell'ambito in questione).
Le note presentatore in output devono essere scritte in Markdown (.md) sfruttando titolo, sottotitoli e elenchi, in modo da ottimizzare la leggibilità (PER ME) nel momento in cui andrò a presentare le slide. Ogni slide deve essere separata dalle altre da un titolo iniziale (esempio: #Slide 1) e da un separatore orizzontale (---) alla sua fine.
L'output della generazione deve contenere solamente il testo che ti ho chiesto, senza ulteriori frasi, in modo tale che io possa accoppiare il contenuto dell'output direttamente nelle note presentatore senza avere rumore.
Se una slide è vuota o non ha contenuto rispondi semplicemente con "[NESSUN TESTO RILEVATO]".
Evita parole discorsive o di cortesia come "iniziamo, "buongiorno", "buonasera", "arriverderci", o simili, non devi preparare l'intero discorso, ma solamente quello legato al contenuto delle slide.
Non devi fare riferimento al fatto che stai generando delle note presentatore.
Non fare il riassunto finale della slide.\n
"""

rag_v6 = """
Sono un professore, devo tenere un corso, sfruttando determinati pacchi di slide che ho già.
Le slide sono scritte in inglese, ma per questioni di sicurezza nel discorso orale ho bisogno di generare le note presentatore per ogni slide in italiano in un file mardown (.md).
Se ci sono termini tecnici in inglese che non hanno una traduzione italiana comune, mantienili in inglese.
Le note presentatore devono ricalcare il contenuto di ogni slide, sottoforma di discorso orale adatto ad una lezione tecnica ma non troppo (si tratta di corsi di formazione per persone che non sono direttamente coinvolte nell'ambito in questione).
Le note presentatore in output devono essere scritte in Markdown (.md) sfruttando tutti gli headings, sottotitoli e elenchi, in modo da ottimizzare la struttura e la leggibilità per il lettore.
è importante sfruttare la sintassi di markdown per rispettare la gerarchia dei contenuti nelle slide (capitoli, sottocapitoli ed elenchi puntati o numerati dove necessario).
Non inserire il titolo principale di ogni slide perchè ci penserò io a metterlo dopo.
Non inserire separatori orizzontali.
Se una slide è vuota o non ha contenuto metti comunque il separatore senza nessun contenuto, così anche se non c'è testo nelle slide io lo vedo nel file markdown.
Evita parole discorsive o di cortesia come "iniziamo, "buongiorno", "buonasera", "arriverderci", o simili. Non devi preparare l'intero discorso, ma solamente quello legato al contenuto delle slides.
Non devi fare riferimento al fatto che stai generando delle note presentatore.
Non fare il riassunto finale della slide.\n
"""

rag_level = [
    "Solo se pensi che sia utile aggiungere ulteriori informazioni di dettaglio sull'argomento della slide, aggiungi pure del contenuto ma con moderazione, può anche darsi che alcune cose le spieghi nelle slide successive. Mi raccomendo, non esagerare.",
    "Solo se pensi che sia utile aggiungere ulteriori informazioni di dettaglio sull'argomento della slide, aggiungi pure del contenuto ma con moderazione, può anche darsi che alcune cose le spieghi nelle slide successive. Se vedi slide con poco testo, allora in quel caso si estensivo senza esagerare.",
    "Solo se pensi che sia utile aggiungere ulteriori informazioni di dettaglio sull'argomento della slide, aggiungi pure del contenuto, potrebbe essere utile avere maggiori informazioni per la spiegazione.",
    "Solo se pensi che sia utile aggiungere ulteriori informazioni di dettaglio sull'argomento della slide, più contenuto c'è meglio è, quindi sentiti libero di espandere il discorso.",
    ]


RAG_DETAIL_LEVEL = args.detail_level or 0
RAG = rag_v6 + rag_level[RAG_DETAIL_LEVEL]

# first element is the minute, second element is the request made in that minute
max_rpm = 10
request_count: List[int] = [datetime.now().minute, 0]


def parse_page_selection(selection: str, num_pages: int) -> List[int]:
    """Parsa una stringa di selezione pagine come "1,3-5" in una lista ordinata di numeri 1-based.
    Solleva ValueError su input non valido o range fuori limiti.
    """
    if not selection:
        return list(range(1, num_pages + 1))

    pages = set()
    parts = [p.strip() for p in selection.split(',') if p.strip()]
    for part in parts:
        if '-' in part:
            start_str, end_str = part.split('-', 1)
            try:
                start = int(start_str)
                end = int(end_str)
            except ValueError:
                raise ValueError(f"Intervallo pagina non valido: '{part}'")
            if start < 1 or end < start or end > num_pages:
                raise ValueError(f"Intervallo pagina fuori dai limiti: '{part}' (numero pagine: {num_pages})")
            for n in range(start, end + 1):
                pages.add(n)
        else:
            try:
                n = int(part)
            except ValueError:
                raise ValueError(f"Numero di pagina non valido: '{part}'")
            if n < 1 or n > num_pages:
                raise ValueError(f"Numero di pagina fuori dai limiti: {n} (numero pagine: {num_pages})")
            pages.add(n)

    return sorted(pages)


def extract_content_from_pdf(path: str, page_selection: str | None = None) -> list:
    """Estrae il testo da ogni pagina selezionata del PDF. Restituisce una lista di page_content in ordine di pagina.
    page_selection può essere una stringa come "1,3-5" (1-based). Se None -> tutte le pagine.
    Usa PyPDF2; se il PDF contiene solo immagini e vuoi OCR, il codice dovrà essere esteso con pdf2image+pytesseract (commento nel README).
    """
    pdf_content = []

    try:
        from PyPDF2 import PdfReader
    except Exception as e:
        raise RuntimeError("PyPDF2 è richiesto per l'estrazione del testo. Installa con: pip install PyPDF2") from e

    reader = PdfReader(path)
    num_pages = len(reader.pages)

    try:
        selected_pages = parse_page_selection(page_selection, num_pages)
    except ValueError as e:
        raise RuntimeError(f"Selezione pagine non valida: {e}") from e

    for page_number in selected_pages:
        # page_number è 1-based
        page = reader.pages[page_number - 1]
        page_content = []

        try:
            text = page.extract_text() or ""
        except Exception as e:
            text = ""
            logging.error(e)

        try:
            pil_images = []

            # Itera sulle immagini nella pagina (se presenti)
            for img in getattr(page, 'images', []):
                data = img.data
                pil_img = Image.open(io.BytesIO(data))
                pil_images.append(pil_img)

        except Exception as e:
            pil_images = []
            logging.info(e)

        page_content.append(text)
        page_content.extend(pil_images)

        pdf_content.append(page_content)

    return pdf_content

def call_gemini(prompt, model: str = "gemini-2.5-flash") -> str | None:
    """Invia `prompt` a Gemini tramite il client `google.genai`.
    Poiché l'SDK può avere diverse API, proviamo alcune chiamate comuni e forniamo un errore esplicativo se tutte falliscono.
    """
    # Non importiamo o inizializziamo client a livello globale per evitare side-effect in fase di import
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)

        prompt.insert(0, RAG)

        resp = client.models.generate_content(
            model=model, contents=prompt
        )

        if hasattr(resp, 'text'):
            return resp.text
        if hasattr(resp, 'output'):
            out = getattr(resp, 'output')
            return str(out)

        return str(resp)

    except Exception as e:
        logging.error(f"Generazione Gemini fallita: {e}")
        pass

def write_output(responses: Dict[int, str], out_path: str = None) -> None:
    """Scrive le risposte in formato Markdown (default) o JSON.
    Per Markdown crea una separazione leggibile per slide usando intestazioni e linee orizzontali.
    """
    if out_path:
        with open(out_path, 'w', encoding='utf-8') as f:
            for idx in sorted(responses.keys()):
                response = responses[idx] or ""
                f.write(f"## Slide {idx}\n\n")
                f.write(response)
                f.write("\n\n---\n\n")

        logging.info(f"Output written to {out_path}")

    else:
        for idx in sorted(responses.keys()):
            print(f"## Slide {idx}\n")
            print(responses[idx] or "")
            print("\n---\n")


if __name__ == '__main__':
    try:
        pages = extract_content_from_pdf(args.pdf, page_selection=args.pages)
    except Exception as e:
        logging.error(f"Errore durante l'estrazione del PDF: {e}")
        sys.exit(2)

    responses: Dict[int, str] = {}

    for i, page_content in tqdm(enumerate(pages, start=1), total=len(pages), unit="slide"):

        logging.info(f"Invio slide {i} a Gemini...")

        if  len(page_content) == 0:
            responses[i] = "[NESSUN TESTO RILEVATO]"
            continue

        try:
            # If we have exceeded max requests per minute, wait
            if request_count[1] == max_rpm and request_count[0] == datetime.now().minute:
                sleep(60 - datetime.now().second + 1)

            # Reset count if minute has changed
            if request_count[0] != datetime.now().minute:
                request_count[0] = datetime.now().minute
                request_count[1] = 0

            resp_text = call_gemini(page_content, model=args.model or "gemini-2.5-flash")
            request_count[1] = request_count[1] + 1

        except Exception as e:
            logging.error(f"Errore chiamando Gemini per la slide {i}: {e}")
            resp_text = f"[ERROR] {e}"
        responses[i] = resp_text

    write_output(responses, out_path=args.out)  # always uses default 'md'
