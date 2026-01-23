import csv
from pathlib import Path
from lxml import etree

CSV_PATH = Path(r"C:\Users\janbl\OneDrive\Desktop\ZH_Projekt_Pipeline\Test_YOLO_pic2\yolo_ocr_output_2\regions_ocr.csv")
OUTPUT_DIR = Path(r"C:\Users\janbl\OneDrive\Desktop\ZH_Projekt_Pipeline\Test_YOLO_pic2\yolo_ocr_output_2\page_xml_output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# TXT-Log mit Seiten, die != 4 Regionen haben
SKIP_LOG_PATH = OUTPUT_DIR / "skipped_pages_not_4_regions.txt"


# ----------------------------------------------------------
# 1) REGIONEN SORTIEREN UND FELD-ROLLEN ZUORDNEN (nur für 4 Regionen gedacht)
# ----------------------------------------------------------

def assign_region_roles(regions):
    """
    Erwartet Liste dicts:
    {
        "bbox": (x1,y1,x2,y2),
        "text": "...",
    }
    Liefert dieselben dicts + role + reading_index
    """

    # Mittelpunkt berechnen
    for r in regions:
        x1, y1, x2, y2 = r["bbox"]
        r["x_center"] = (x1 + x2) / 2
        r["y_center"] = (y1 + y2) / 2
        r["width"] = x2 - x1

    # zuerst Links/Rechts trennen
    regions_sorted_by_x = sorted(regions, key=lambda r: (r["x_center"], r["y_center"]))

    left_group  = regions_sorted_by_x[:2]
    right_group = regions_sorted_by_x[2:]

    # innerhalb der Gruppen oben/unten sortieren
    left_sorted  = sorted(left_group, key=lambda r: r["y_center"])
    right_sorted = sorted(right_group, key=lambda r: r["y_center"])

    # eindeutige Zuordnung
    mapping = [
        (left_sorted[0],  "IDField_1",      0),
        (right_sorted[0], "ContentField_1", 1),
        (left_sorted[1],  "IDField_2",      2),
        (right_sorted[1], "ContentField_2", 3),
    ]

    for region, role, idx in mapping:
        region["role"] = role
        region["reading_index"] = idx

    return regions


# ----------------------------------------------------------
# 2) PAGE-XML für eine Seite erstellen
# ----------------------------------------------------------

def create_pagexml(page_name, regions):
    """
    page_name = "1887_b1.pdf_page_10.png"
    regions = Liste der dicts nach assign_region_roles()
    """

    root = etree.Element("PcGts", xmlns="http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15")
    metadata = etree.SubElement(root, "Metadata")
    creator = etree.SubElement(metadata, "Creator")
    creator.text = "YOLO + TrOCR Pipeline"
    comment = etree.SubElement(metadata, "Comments")
    comment.text = "Automatisch generiert"

    page_el = etree.SubElement(
        root,
        "Page",
        imageFilename=page_name,
        imageWidth="2000",   # placeholder
        imageHeight="3000"   # placeholder
    )

    # Jeder Region einen TextRegion-Knoten geben
    for idx, r in enumerate(regions):
        x1, y1, x2, y2 = r["bbox"]
        role = r["role"]
        ro_index = r["reading_index"]

        region_el = etree.SubElement(
            page_el,
            "TextRegion",
            id=f"r{idx}",
            custom=f"readingOrder {{index:{ro_index};}} structure {{type:{role}; score:0.99;}}"
        )

        etree.SubElement(
            region_el,
            "Coords",
            points=f"{x1},{y1} {x2},{y1} {x2},{y2} {x1},{y2}"
        )

        textequiv = etree.SubElement(region_el, "TextEquiv")
        unicode_el = etree.SubElement(textequiv, "Unicode")
        unicode_el.text = r["text"].strip()

    return etree.tostring(root, pretty_print=True, encoding="utf-8", xml_declaration=True)


# ----------------------------------------------------------
# 3) CSV einlesen, gruppieren & pro Seite XML erzeugen
# ----------------------------------------------------------

pages = {}

with CSV_PATH.open("r", encoding="utf-8") as f:
    reader = csv.DictReader(f, delimiter=";")
    for row in reader:
        page = row["page"]

        region = {
            "bbox": (
                int(row["x1"]),
                int(row["y1"]),
                int(row["x2"]),
                int(row["y2"])
            ),
            "text": row["text"]
        }

        pages.setdefault(page, []).append(region)


# ----------------------------------------------------------
# 4) Jede Seite verarbeiten (!=4 SKIP + Logfile)
# ----------------------------------------------------------

skipped = []  # Liste von (page_name, count)

for page_name, region_list in pages.items():

    if len(region_list) != 4:
        print(f"⚠ SKIP: Seite {page_name} hat {len(region_list)} Regionen statt 4.")
        skipped.append((page_name, len(region_list)))
        continue

    print(f"→ Verarbeite {page_name} (4 Regionen)")

    # rollen zuweisen
    region_list = assign_region_roles(region_list)

    # PAGE-XML erstellen
    xml_bytes = create_pagexml(page_name, region_list)

    out_path = OUTPUT_DIR / f"{page_name}.xml"
    out_path.write_bytes(xml_bytes)

    print("   ✔ XML gespeichert unter:", out_path)


# ----------------------------------------------------------
# 5) Skip-Log schreiben
# ----------------------------------------------------------

with SKIP_LOG_PATH.open("w", encoding="utf-8") as f:
    f.write("Seiten mit != 4 Regionen (wurden geskippt)\n")
    f.write("========================================\n\n")
    f.write(f"CSV: {CSV_PATH}\n")
    f.write(f"Output-Ordner: {OUTPUT_DIR}\n\n")
    f.write(f"Anzahl geskippt: {len(skipped)}\n\n")

    # Sortiert: erst nach Anzahl Regionen, dann Name
    for page_name, count in sorted(skipped, key=lambda x: (x[1], x[0])):
        f.write(f"{page_name}\t{count}\n")

print("\n🎉 Fertig! Alle PAGE-XML-Dateien im Ordner:", OUTPUT_DIR)
print("📝 Skip-Log gespeichert unter:", SKIP_LOG_PATH)
