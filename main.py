import argparse
import json
import sys
import logging
from datetime import datetime
from time import sleep
from typing import List, Dict
from tqdm import tqdm

import os
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

from google import genai

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
Non osare formattazione particolare per il testo, perché le note presentatori di Apple Keynote non le supportano, piuttosto usa una formattazione basata su spazi, invii e TAB, in modo da ottimizzare la leggibilità (PER ME) nel momento in cui andrò a presentare le slide.
L'output della generazione deve contenere solamente il testo che ti ho chiesto, senza ulteriori frasi, in modo tale che io possa accoppiare il contenuto dell'output direttamente nelle note presentatore senza avere rumore.
Se una slide è vuota o non ha contenuto rispondi semplicemente con "[NESSUN TESTO RILEVATO]".
Se pensi che sia utile aggiungere ulteriori informazioni di dettaglio sull'argomento della slide, fallo pure, più contenuto c'è meglio è.
Evita parole discorsive o di cortesia come "iniziamo, "buongiorno", "buonasera", "arriverderci", o simili, non devi preparare l'intero discorso, ma solamente quello legato al contenuto delle slide.
Non devi fare riferimento al fatto che stai generando delle note presentatore.
Non fare il riassunto finale della slide.
"""

# first element is the minute, second element is the request made in that minute
max_rpm = 10
request_count: List[int] = [datetime.now().minute, 0]

def extract_content_from_pdf(path: str) -> List:
    """Estrae il testo da ogni pagina del PDF. Restituisce una lista di stringhe, una per pagina.
    Usa PyPDF2; se il PDF contiene solo immagini e vuoi OCR, il codice dovrà essere esteso con pdf2image+pytesseract (commento nel README).
    """
    pdf_content = []

    try:
        from PyPDF2 import PdfReader
    except Exception as e:
        raise RuntimeError("PyPDF2 è richiesto per l'estrazione del testo. Installa con: pip install PyPDF2") from e

    reader = PdfReader(path)
    for i, page in enumerate(reader.pages):
        page_content = []

        try:
            text = page.extract_text() or ""
        except Exception as e:
            text = ""
            logging.error(e)

        try:
            images = page.images
        except Exception as e:
            images = []
            logging.info(e)

        page_content.append(text)
        page_content.extend(images)

        pdf_content.append(page_content)

    return pdf_content

def call_gemini(prompt: str, model: str = "gemini-2.5-flash") -> str | None:
    """Invia `prompt` a Gemini tramite il client `google.genai`.
    Poiché l'SDK può avere diverse API, proviamo alcune chiamate comuni e forniamo un errore esplicativo se tutte falliscono.
    """
    # Non importiamo o inizializziamo client a livello globale per evitare side-effect in fase di import
    try:
        # Tentativo 1: istanziare client e usare generate_text
        client = genai.Client(api_key=GEMINI_API_KEY)

        resp = client.models.generate_content(
            model=model, contents=[f"{rag_v2}\n\n{prompt}"]
        )

        if hasattr(resp, 'text'):
            return resp.text
        if hasattr(resp, 'output'):
            # output potrebbe essere una lista di contenuti
            out = getattr(resp, 'output')
            return str(out)

        return str(resp)

    except Exception as e:
        logging.error(f"Generazione Gemini fallita: {e}")
        pass

def write_output(responses: Dict[int, str], out_path: str = None, fmt: str = 'plain') -> None:
    if out_path:
        if fmt == 'json':
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(responses, f, ensure_ascii=False, indent=2)
        else:
            with open(out_path, 'w', encoding='utf-8') as f:
                for idx in sorted(responses.keys()):
                    f.write(f"--- Slide {idx} ---\n")
                    f.write(responses[idx] + "\n\n")

        logging.info(f"Output written to {out_path}")

    else:
        if fmt == 'json':
            print(json.dumps(responses, ensure_ascii=False, indent=2))
        else:
            for idx in sorted(responses.keys()):
                print(f"--- Slide {idx} ---")
                print(responses[idx])
                print()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Estrai testo da un PDF per slide e invia ogni slide a Gemini (Google genai).')
    parser.add_argument('--pdf', '-p', required=True, help='Percorso al file PDF delle slide')
    parser.add_argument('--out', '-o', help='File di output (se omesso stampa su stdout)')
    parser.add_argument('--model', help='Nome del modello Gemini da usare (opzionale)', default=None)
    parser.add_argument('--format', choices=['plain', 'json'], default='plain', help='Formato di output')
    args = parser.parse_args()

    logging.basicConfig(level=logging.ERROR)

    try:
        pages = extract_content_from_pdf(args.pdf)
    except Exception as e:
        logging.error(f"Errore durante l'estrazione del PDF: {e}")
        sys.exit(2)

    responses: Dict[int, str] = {}

    for i, page_content in tqdm(enumerate(pages, start=1), unit="slide"):

        logging.info(f"Invio slide {i} a Gemini...")

        if  len(page_content) == 0:
            responses[i] = "[NESSUN TESTO RILEVATO]"
            continue

        try:
            if request_count[1] == max_rpm and request_count[0] == datetime.now().minute:
                sleep(60 - datetime.now().second + 1)

            resp_text = call_gemini(page_content)
            request_count[1] = request_count[1] + 1

        except Exception as e:
            logging.error(f"Errore chiamando Gemini per la slide {i}: {e}")
            resp_text = f"[ERROR] {e}"
        responses[i] = resp_text

    write_output(responses, out_path=args.out, fmt=args.format)
