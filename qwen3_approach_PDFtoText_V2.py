import os
import base64
from pathlib import Path
from pdf2image import convert_from_path
from openai import OpenAI
from PIL import Image
import time
import xml.etree.ElementTree as ET
from xml.dom import minidom
import re
import time
from PIL import Image
import numpy as np

print("SCRIPT STARTET")

# ==============================
# KONFIGURATION
# ==============================
BASE_DIR = Path.cwd()

PDF_PATH = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR = BASE_DIR / "logs"


PROMPT = """
Du bist eine STRICT OCR engine.

WICHTIGE REGELN:
- Gib EXAKT die Zeichen zurück, die im Bild sichtbar sind.
- NICHT interpretieren.
- NICHT modernisieren.
- NICHT übersetzen.
- NICHT korrigieren.
- NICHT ergänzen.
- NICHT zusammenfassen.
- NICHT medizinisch interpretieren.
- Keine Synonyme verwenden.
- Keine Vermutungen.
- Wenn ein Feld leer ist, lasse es leer.
- Wenn nur einzelne Buchstaben sichtbar sind, gib nur diese Buchstaben aus.
- Historische Schreibweisen müssen exakt erhalten bleiben.
- Alte Orthographie exakt übernehmen.
- Lateinische Begriffe exakt übernehmen.

Dieses Bild enthält genau einen Eintrag (entweder oberer oder unterer Teil der Seite).
- linke Spalte: Zusatzdata
- rechte Spalte: Haupttext

Lies strikt zeilenweise von oben nach unten pro Spalte.

Gib ausschließlich diese Struktur zurück:

Zusatzdata:
...

Haupttext:
...

Keine zusätzlichen Kommentare.
Erfinde niemals etwas neues
"""
#MAX_WIDTH = 512
RETRIES = 3
RETRY_DELAY = 20  # Sekunden
MAX_RETRIES = 5

BATCH_SIZE = 5
BATCH_PAUSE = 60

print("=== DEBUG START ===")
print(f"BASE_DIR: {BASE_DIR}")
print(f"PDF_PATH: {PDF_PATH}")
print(f"Existiert PDF_PATH? {PDF_PATH.exists()}")

try:
    print(f"Inhalt von PDF_PATH: {list(PDF_PATH.glob('*'))}")
except Exception as e:
    print(f"Fehler beim Lesen von PDF_PATH: {e}")

print("=== DEBUG ENDE ===")

# ==============================
# PDF → PNG
# ==============================
print("Starte PDF → PNG Konvertierung...")

from pdf2image import convert_from_path, pdfinfo_from_path

def resize_image(image_path, max_size=1400):
    img = Image.open(image_path)

    if img.width > max_size:
        wpercent = max_size / float(img.width)
        hsize = int(float(img.height) * float(wpercent))
        img = img.resize((max_size, hsize), Image.Resampling.LANCZOS)
        img.save(image_path)

# ==============================
# PNG → Qwen3-VL
# ==============================

client = OpenAI(
    base_url="https://gpustack.unibe.ch/v1-openai",
    api_key="gpustack_4e16e86379d3975a_d2d4bc77a2aca0ce10e7a993d25af209"
)

def send_to_qwen(image_path):
    """Sende ein PNG an Qwen und return den Text."""
    with open(image_path, "rb") as f:
        image_base64 = base64.b64encode(f.read()).decode("utf-8")
        if len(image_base64) > 10_000_000:  # Beispiel: 10 MB Limit
            print("Bild zu groß – bitte verkleinern!")
            return None

    response = client.chat.completions.create(
        model="qwen3-vl-8b-instruct",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
                ]
            }
        ],
        temperature=0.0
    )

    return response.choices[0].message.content

import time
from PIL import Image

MAX_RETRIES = 5

def send_to_qwen_with_retry(png_path):
    current_path = png_path
    backoff = 5

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"→ Versuch {attempt}")

            result = send_to_qwen(current_path)  # deine Originalfunktion

            if result:
                return result

        except Exception as e:
            print(f"[Fehler] Versuch {attempt}: {e}")

        # Wenn 3 Versuche fehlgeschlagen → Bild verkleinern
        if attempt == 2:
            print("⚠ Verkleinere Bild und versuche erneut...")
            current_path = downscale_image(current_path, scale=0.75)

        print(f"Warte {backoff} Sekunden...")
        time.sleep(backoff)
        backoff *= 2  # exponentielles Backoff

    return None
from PIL import ImageEnhance, ImageFilter

def enhance_image(img):
    # 1. Graustufen (wichtig für OCR)
    img = img.convert("L")

    # 2. Kontrast erhöhen
    img = ImageEnhance.Contrast(img).enhance(1.8)

    # 3. Schärfen
    img = ImageEnhance.Sharpness(img).enhance(2.0)

    # 4. leichter zusätzlicher Sharpen-Filter
    img = img.filter(ImageFilter.SHARPEN)

    return img

def downscale_image(png_path, scale=0.75):
    img = Image.open(png_path)

    new_size = (int(img.width * scale), int(img.height * scale))
    img = img.resize(new_size, Image.LANCZOS)

    new_path = png_path.with_name(png_path.stem + "_small.png")
    img.save(new_path)

    return new_path
import re

def parse_ocr_output(text):

    sections = {
        "Zusatzdata": "",
        "Haupttext": ""
    }

    current_key = None

    keywords = [
        "Zusatzdata",
        "Haupttext"
    ]

    for line in text.splitlines():

        clean_line = line.strip()

        if not clean_line:
            continue

        found_header = False

        for key in keywords:

            if re.match(
                rf'^\**{key}\**',
                clean_line,
                re.IGNORECASE
            ):

                current_key = key
                found_header = True

                content_after_header = re.sub(
                    rf'^\**{key}\**\s*:?\s*',
                    '',
                    clean_line,
                    flags=re.IGNORECASE
                )

                if content_after_header:
                    sections[current_key] += (
                        content_after_header + "\n"
                    )

                break

        if found_header:
            continue

        if current_key:
            sections[current_key] += line + "\n"

    return sections


def create_page_xml(sections, output_path):
    PcGts = ET.Element("PcGts")
    Page = ET.SubElement(PcGts, "Page")

    for region_id, content in sections.items():
        TextRegion = ET.SubElement(Page, "TextRegion", id=region_id)
        TextEquiv = ET.SubElement(TextRegion, "TextEquiv")
        Unicode = ET.SubElement(TextEquiv, "Unicode")
        Unicode.text = content.strip()

    # Pretty Print
    rough_string = ET.tostring(PcGts, encoding="utf-8")
    reparsed = minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent="  ")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(pretty_xml)
# ==============================
# Dynamische Trennlinie suchen
# ==============================

def find_split_line(page_image):

    gray = page_image.convert("L")

    arr = np.array(gray)

    # dunkle Pixel zählen
    dark_pixels = arr < 140

    row_scores = dark_pixels.sum(axis=1)

    h = arr.shape[0]

    # nur mittleren Bereich durchsuchen
    start = int(h * 0.35)
    end = int(h * 0.65)

    search_scores = row_scores[start:end]

    split_y = start + np.argmax(search_scores)

    print(f"Gefundene Trennlinie bei y={split_y}")

    return split_y


# ==============================
# Dynamisches ROI Cropping
# ==============================

def crop_rois_dynamic(page_image):

    width, height = page_image.size

    split_y = find_split_line(page_image)

    # etwas Rand wegschneiden
    left_margin = int(width * 0.10)

    # Sicherheitspuffer um die Linie
    padding = 20

    top = page_image.crop(
        (
            left_margin,
            0,
            width,
            split_y + padding
        )
    )

    bottom = page_image.crop(
        (
            left_margin,
            split_y - padding,
            width,
            height
        )
    )

    return top, bottom

# ==============================
# HAUPTPROGRAMM
# ==============================

def main():
    print(f"BASE_DIR: {BASE_DIR}")
    print(f"PDF_PATH: {PDF_PATH}")

    pdf_files = list(PDF_PATH.glob("*.pdf"))

    if not pdf_files:
        print("Keine PDFs gefunden.")
        return

    COOLDOWN_EVERY = 15
    COOLDOWN_SECONDS = 180

    import gc
    from pdf2image import pdfinfo_from_path

    for pdf in pdf_files:

        print(f"\n=== Verarbeite PDF: {pdf.name} ===")

        pdf_output_dir = OUTPUT_DIR / pdf.stem
        pdf_output_dir.mkdir(parents=True, exist_ok=True)

        info = pdfinfo_from_path(str(pdf))
        max_pages = info["Pages"]

        page_counter = 0

        for i in range(1, max_pages + 1):

            page_counter += 1

            print(f"\n--- Seite {i}/{max_pages} ---")

            # Nur EINE Seite rendern
            pages = convert_from_path(
                str(pdf),
                dpi=300,
                first_page=i,
                last_page=i
            )
            
            page = pages[0]
            
            top, bottom = crop_rois_dynamic(page)
            
            top = enhance_image(top)
            bottom = enhance_image(bottom)
            
            png_top = pdf_output_dir / f"{pdf.stem}_page_{i}_top.png"
            png_bottom = pdf_output_dir / f"{pdf.stem}_page_{i}_bottom.png"
            
            top.save(png_top, "PNG", compress_level=2)
            bottom.save(png_bottom, "PNG", compress_level=2)
            
            resize_image(png_top, max_size=1400)
            resize_image(png_bottom, max_size=1400)
        

            # Speicher freigeben
            page.close()
            del page
            del pages
            gc.collect()

            print(f"--- Sende Seite {i} an Qwen ---")

            result_top = send_to_qwen_with_retry(png_top)
            result_bottom = send_to_qwen_with_retry(png_bottom)
            if result_top:
            
                sections_top = parse_ocr_output(result_top)
            
            else:
            
                sections_top = {
                    "Zusatzdata": "",
                    "Haupttext": ""
                }
            
            if result_bottom:
            
                sections_bottom = parse_ocr_output(result_bottom)
            
            else:
            
                sections_bottom = {
                    "Zusatzdata": "",
                    "Haupttext": ""
                }
            
            if result_top or result_bottom:
            
                sections = {
            
                    "Zusatzdata1":
                        sections_top.get("Zusatzdata", ""),
            
                    "Haupttext1":
                        sections_top.get("Haupttext", ""),
            
                    "Zusatzdata2":
                        sections_bottom.get("Zusatzdata", ""),
            
                    "Haupttext2":
                        sections_bottom.get("Haupttext", "")
                }
                xml_output_path = (
                    pdf_output_dir /
                    f"{pdf.stem}_page_{i}.xml"
                )

                create_page_xml(
                    sections,
                    xml_output_path
                )

                print(
                    f"PAGE-XML gespeichert: "
                    f"{xml_output_path}"
                )

            else:
                print(f"Fehler bei Seite {i}")

            # PNG löschen
            for p in [png_top, png_bottom]:
                try:
                    os.remove(p)
                except:
                    pass

            time.sleep(2)

            # Stabilitäts-Cooldown
            if page_counter % COOLDOWN_EVERY == 0:

                print(
                    f"\n=== Cooldown "
                    f"{COOLDOWN_SECONDS}s ===\n"
                )

                time.sleep(COOLDOWN_SECONDS)

    print("\n=== Verarbeitung abgeschlossen ===")


if __name__ == "__main__":
    main()
