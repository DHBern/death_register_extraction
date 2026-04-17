import os
import csv
from pathlib import Path
from openai import OpenAI
import xml.etree.ElementTree as ET
import time
import json

BASE_DIR = Path.cwd()

INPUT_BASE = BASE_DIR / "output"  # ← hier liegen deine XML-Ordner
EXTRACTION_OUTPUT = BASE_DIR / "extraction_output"

PROMPT_TEMPLATE = PROMPT_TEMPLATE = """Führe für den nachfolgenden Text eine Keyword-Extraktion durch.

Die Extraktion basiert auf den Start-Stop-Wörtern der mitgelieferten Liste.

WICHTIG:
- Pro Tag darf es nur EIN zusammenhängendes Segment geben.
- Falls mehrere Segmente zum gleichen Tag gehören, fasse sie zu EINEM Block zusammen.
- Gib das Ergebnis ausschließlich als JSON im folgenden Format zurück:
{
  "Todeszeit": "...",
  "Todesort/Ursache": "...",
  "Name/Beruf/Familienverhältnis/Vater/Mutter/Zivilstand/Religion/Heimatort": "",
  "Wohnort/Geburtsdatum": "..."
}
- Jeder Key darf nur einmal vorkommen.
- Wiederhole keinen Tag mehrfach.
- Füge nichts weiteres hinzu.

"start_keywords": ["Den", "mittags", "Bescheinigung", "wohnhaft in"],
"end_keywords": ["Uhr", "ärztlicher", "wohnhaft", "Eingetragen"],
"tags": ["Todeszeit", "Todesort/Ursache", "Name/Beruf/Familienverhältnis/Vater/Mutter/Zivilstand/Religion/Heimatort", "Wohnort/Geburtsdatum"]

Extrahiere ausschließlich den Text zwischen den Start- und End-Keywords. Falls eines der Keywords nicht gefunden wird, lasse das entsprechende Feld leer. Fasse alle Segmente, die zum gleichen Tag gehören, zu einem einzigen Block zusammen. Gib das Ergebnis als JSON zurück.
BEISPIEL:

Text:
Den fünften September eintausendneunhundert eins um ein Uhr dreissig Minuten vor mittags ist gestorben zu Zürich im Kinderspital an Blinddarmverbindung, Bauchfellbruch laut ärztlicher Bescheinigung Siller, Reinhold Friedrich Beruf: des Vaters Pack- und Magaziner Sohn des Siller Reinhold und der Pauline Füning geb. Dörr Zivilstand: Religion: von Ulmback wohnhaft in Zürich geboren den zehnten Mai eintausendachthundert neunundzwanzig in Zürich

Erwartete Ausgabe:
{
  "Todeszeit": "Den fünften September eintausendneunhundert eins um ein Uhr",
  "Todesort/Ursache": "zu Zürich im Kinderspital an Blinddarmverbindung, Bauchfellbruch laut ",
  "Name/Beruf/Familienverhältnis/Vater/Mutter/Zivilstand/Religion/Heimatort": "Siller, Reinhold Friedrich Beruf: des Vaters Pack- und Magaziner Sohn des Siller Reinhold und der Pauline Füning geb. Dörr Zivilstand: Religion: von Ulmback",
  "Wohnort/Geburtsdatum": "in Zürich geboren den zehnten Mai eintausendachthundert neunundzwanzig in Zürich"
}
Nun extrahiere für folgenden Text:
"""

RETRIES = 3
RETRY_DELAY = 5

client = OpenAI(
    base_url="https://gpustack.unibe.ch/v1-openai",
    api_key="gpustack_4e16e86379d3975a_d2d4bc77a2aca0ce10e7a993d25af209"
)

# ==============================
# XML → Text extrahieren
# ==============================

def extract_haupttexte_from_xml(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    regions = root.findall(".//TextRegion")

    blocks = []
    current_zusatz = ""

    for region in regions:
        region_id = region.attrib.get("id", "")

        unicode_element = region.find(".//Unicode")
        if unicode_element is None or not unicode_element.text:
            continue

        text_content = unicode_element.text.strip()

        # Zusatzdata merken
        if region_id.startswith("Zusatzdata"):
            # Zeilenumbrüche entfernen → CSV sauber
            current_zusatz = " ".join(text_content.split())

        # Haupttext bekommt zuletzt gelesene Zusatzdata
        elif region_id.startswith("Haupttext"):
            blocks.append((region_id, current_zusatz, text_content))

    return blocks
def clean_text(text: str) -> str:
    """
    Bereinigt OCR-Text für stabile LLM-Extraktion.
    Entfernt Register-Nachträge, Unterschriften,
    Zeilenumbrüche und Mehrfach-Leerzeichen.
    """

    # 1. Alles ab "Eingetragen" abschneiden
    text = re.split(r"\bEingetragen\b", text, flags=re.IGNORECASE)[0]

    # 2. Unterschriften / Mitteilungen entfernen
    text = re.sub(r"Vorgelesen.*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Mitgeteilt.*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[Unterschrift.*?\]", "", text)

    # 3. OCR-Lücken reduzieren (optional)
    text = re.sub(r"_+", "", text)

    # 4. Zeilenumbrüche entfernen
    text = text.replace("\n", " ")

    # 5. Mehrfach-Leerzeichen normalisieren
    text = re.sub(r"\s+", " ", text)

    return text.strip()
# ==============================
# Qwen Text Call
# ==============================

def send_to_qwen(text):
    full_prompt = PROMPT_TEMPLATE + "\n" + text
    print("Prompt an Qwen:\n", full_prompt[:500], "...\n")  # Optional: Prompt-Preview

    response = client.chat.completions.create(
        model="qwen3-coder-30b-a3b-instruct",
        messages=[
            {
                "role": "user",
                "content": full_prompt
            }
        ],
        temperature=0.0
    )

    return response.choices[0].message.content


def send_with_retry(text, retries=RETRIES, delay=RETRY_DELAY):
    for attempt in range(1, retries + 1):
        try:
            return send_to_qwen(text)
        except Exception as e:
            print(f"[Fehler] Versuch {attempt}/{retries}: {e}")
            if attempt < retries:
                time.sleep(delay)
            else:
                return None

import re
from collections import defaultdict

def merge_duplicate_tags(result_text):
    pattern = r"<([^>]+)>(.*?)</\1>"
    matches = re.findall(pattern, result_text, re.DOTALL)

    merged = defaultdict(str)

    for tag, content in matches:
        merged[tag] += " " + content.strip()

    final_output = ""
    for tag, content in merged.items():
        final_output += f"<{tag}>{content.strip()}</{tag}>\n"

    return final_output
# ==============================
# HAUPTPROGRAMM
# ==============================

def extract_sort_key(filename):
    match = re.search(r'(\d{4}).*?_b(\d+)_.*?page_(\d+)', filename)
    if match:
        year = int(match.group(1))
        band = int(match.group(2))
        page = int(match.group(3))
        return (year, band, page)
    return (0, 0, 0)

def main():
    EXTRACTION_OUTPUT.mkdir(parents=True, exist_ok=True)

    # 🔹 Alle Unterordner im output-Verzeichnis holen
    pdf_folders = [p for p in INPUT_BASE.iterdir() if p.is_dir()]

    if not pdf_folders:
        print("Keine Ordner im output-Verzeichnis gefunden.")
        return

    for folder in pdf_folders:
        print(f"\n=== Verarbeite Ordner: {folder.name} ===")

        xml_files = sorted(
            folder.glob("*.xml"),
            key=lambda x: extract_sort_key(x.name)
        )

        if not xml_files:
            print(f"⚠ Keine XML-Dateien in {folder.name}")
            continue

        # 🔹 CSV pro Ordner
        csv_output_path = EXTRACTION_OUTPUT / f"{folder.name}.csv"

        with open(csv_output_path, mode="w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)

            writer.writerow([
                "Datei",
                "XML_Block_Index",
                "Todeszeit",
                "Todesort/Ursache",
                "Name/Beruf/Vater,Mutter/Zivilstand/Wohn/Heimatort/Konfession",
                "Wohnort/Geburtsdatum"
            ])

            for xml_file in xml_files:
                print(f"  → Verarbeite XML: {xml_file.name}")

                haupttexte = extract_haupttexte_from_xml(xml_file)

                for idx, (region_id, zusatzdata, text) in enumerate(haupttexte, start=1):
                    print(f"    → Sende {region_id} an Qwen")

                    cleaned = clean_text(text)
                    result = send_with_retry(cleaned)

                    if not result:
                        print("⚠ Kein Resultat")
                        continue

                    try:
                        parsed = json.loads(result)

                        writer.writerow([
                            xml_file.name,
                            idx,
                            parsed.get("Todeszeit", ""),
                            parsed.get("Todesort/Ursache", ""),
                            parsed.get("Name/Beruf/Familienverhältnis/Vater/Mutter/Zivilstand/Religion/Heimatort", ""),
                            parsed.get("Wohnort/Geburtsdatum", "")
                        ])

                    except json.JSONDecodeError:
                        print("❌ JSON Fehler bei:", xml_file.name, region_id)
                        print("RAW:", result)

        print(f"✅ CSV gespeichert: {csv_output_path}")

    print("\n=== ALLE ORDNER FERTIG ===")

if __name__ == "__main__":
    main()
