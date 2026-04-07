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

# ==============================
# KONFIGURATION
# ==============================

PDF_PATH = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR = BASE_DIR / "logs"

PROMPT = """Führe eine OCR-Analyse des angehängten Bildes durch. Das Bild ist jeweils so angeordnet, dass es zwei voneinander unabhängige einträge sind. Neben den langen text, steht links davon immer noch ein referenzeintrag. Diese beiden gehören zusammen. Gib nur den erkannten text aus, ändere den text nicht und füge keinerlei erklärungen hinzu. Trenne die beiden einzelnen Einträge und füge dem langen Eintrag (rechts) eine überschrift "Haupttext1" bzw. "Haupttext2" und dem kleineren Eintrag (links) die überschrift "Zusatzdata1" bzw. "Zusatzdata2" hinzu. Nutze exakt diese Labels: Zusatzdata1, Haupttext1, Zusatzdata2, Haupttext2. Die Nummer 1 betrifft die beiden oberen Einträge und Nummer 2 die beiden unteren."""

#MAX_WIDTH = 512
RETRIES = 3
RETRY_DELAY = 20  # Sekunden
MAX_RETRIES = 5

BATCH_SIZE = 5
BATCH_PAUSE = 60

# ==============================
# PDF → PNG
# ==============================

def pdf_to_png(pdf_path: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    pages = convert_from_path(str(pdf_path), dpi=150)  # DPI auf 150 reduzieren
    image_paths = []
    for i, page in enumerate(pages):
        path = output_dir / f"{pdf_path.stem}_page_{i+1}.png"
        page.convert("L").save(str(path), "PNG", compress_level=6)  # Graustufen + Kompression
        resize_image(path, max_size=1200)  # Maximalgröße begrenzen
        image_paths.append(path)
    return image_paths


def resize_image(image_path, max_size=1500):
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
        if attempt == 3:
            print("⚠ Verkleinere Bild und versuche erneut...")
            current_path = downscale_image(current_path, scale=0.75)

        print(f"Warte {backoff} Sekunden...")
        time.sleep(backoff)
        backoff *= 2  # exponentielles Backoff

    return None


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
        "Zusatzdata1": "",
        "Haupttext1": "",
        "Zusatzdata2": "",
        "Haupttext2": ""
    }

    current_key = None
    # Suche nach den Keywords irgendwo in der Zeile, ignoriere Groß/Kleinschreibung und Sterne
    keywords = ["Zusatzdata1", "Haupttext1", "Zusatzdata2", "Haupttext2"]

    for line in text.splitlines():
        clean_line = line.strip()
        if not clean_line:
            continue

        found_header = False
        for key in keywords:
            # Prüft, ob das Keyword (evtl. mit Sternchen drumherum) am Zeilenanfang steht
            if re.match(rf'^\**{key}\**', clean_line, re.IGNORECASE):
                current_key = key
                found_header = True
                
                # Falls nach dem Header direkt Text kommt (z.B. "Haupttext1: Dies ist der Text")
                # Entferne den Header-Teil aus der ersten Zeile
                content_after_header = re.sub(rf'^\**{key}\**\s*:?\s*', '', clean_line, flags=re.IGNORECASE)
                if content_after_header:
                    sections[current_key] += content_after_header + "\n"
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
# HAUPTPROGRAMM
# ==============================

def main():
    pdf_files = list(PDF_PATH.glob("*.pdf"))
    if not pdf_files:
        print("Keine PDFs im Input-Ordner gefunden.")
        return

    # 🔹 Globale Stabilitäts-Parameter
    COOLDOWN_EVERY = 15
    COOLDOWN_SECONDS = 180

    for pdf in pdf_files:
        print(f"\n=== Verarbeite PDF: {pdf.name} ===")

        # 🔹 PDF → PNG
        pdf_output_dir = OUTPUT_DIR / pdf.stem
        pdf_output_dir.mkdir(parents=True, exist_ok=True)

        png_files = pdf_to_png(pdf, pdf_output_dir)

        page_counter = 0  # zählt über alle Batches hinweg

        # 🔹 Batch-Verarbeitung
        for batch_start in range(0, len(png_files), BATCH_SIZE):

            batch = png_files[batch_start:batch_start + BATCH_SIZE]
            print(f"\n=== Starte Batch {batch_start//BATCH_SIZE + 1} ===")

            for png in batch:
                page_counter += 1

                print(f"--- Sende {png.name} an Qwen ---")
                print(f"Dateigröße: {png.stat().st_size} Bytes")

                result = send_to_qwen_with_retry(png)

                if result:
                    sections = parse_ocr_output(result)
                    xml_output_path = pdf_output_dir / (png.stem + ".xml")
                    create_page_xml(sections, xml_output_path)
                    print(f"PAGE-XML gespeichert: {xml_output_path}")
                    print(f"Antwort von Qwen: {result[:100]}...")

                    # ✅ Mini-Pause nach erfolgreichem Request
                    time.sleep(2)

                else:
                    print(f"Fehler: {png.name} konnte nicht verarbeitet werden.")
                    print("=== Fehler erkannt – 90 Sekunden Cooldown ===")
                    time.sleep(90)

                # 🔥 Globaler Cooldown alle X Seiten
                if page_counter % COOLDOWN_EVERY == 0:
                    print(f"\n=== Globaler Cooldown für {COOLDOWN_SECONDS} Sekunden ===\n")
                    time.sleep(COOLDOWN_SECONDS)

            # 🔥 Pause nach jedem Batch (nur wenn noch Seiten übrig sind)
            if batch_start + BATCH_SIZE < len(png_files):
                print(f"\n=== Batch fertig – Pause {BATCH_PAUSE} Sekunden ===\n")
                time.sleep(BATCH_PAUSE)

if __name__ == "__main__":
    main()
