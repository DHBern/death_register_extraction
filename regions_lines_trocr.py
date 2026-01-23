from ultralytics import YOLO
import cv2
from pathlib import Path
import json
import numpy as np
from PIL import Image
import torch
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
import csv

# PDF-Rendering (kein Poppler nötig)
# pip install pymupdf
import fitz  # PyMuPDF

# ---------------------------------------------------------------------------
# 1) MODEL-PFADE ANPASSEN
# ---------------------------------------------------------------------------

REGION_MODEL_PATH = r"C:\Users\janbl\OneDrive\Desktop\ZH_Projekt_Pipeline\textregion_seg32\weights\best.pt"
LINE_MODEL_PATH   = r"C:\Users\janbl\OneDrive\Desktop\ZH_Projekt_Pipeline\textline_seg\weights\best.pt"

# ORDNER mit BILDERN + PDFs
IMAGE_FOLDER = Path(r"C:\Users\janbl\OneDrive\Desktop\ZH_Projekt_Pipeline\Test_YOLO_pic2")

OUTPUT_DIR = IMAGE_FOLDER / "yolo_ocr_output_2"
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

# DPI fürs PDF-Rastern (300–450 üblich; höher = besser, aber langsamer/mehr RAM)
PDF_DPI = 350

# Optional: gerenderte PDF-Seiten als PNG in OUTPUT_DIR speichern
SAVE_RENDERED_PDF_PAGES = False

# ---------------------------------------------------------------------------
# 2) MODELLE LADEN (YOLO + TrOCR)
# ---------------------------------------------------------------------------

print("Lade YOLO-Modelle...")
region_model = YOLO(REGION_MODEL_PATH)
line_model   = YOLO(LINE_MODEL_PATH)

print("Lade TrOCR-Modell dh-unibe/trocr-kurrent...")
device = "cuda" if torch.cuda.is_available() else "cpu"

# Tokenizer/Processor vom Basismodell
processor = TrOCRProcessor.from_pretrained("microsoft/trocr-base-handwritten")

# Gewichte vom Kurrent-Finetune
trocr_model = VisionEncoderDecoderModel.from_pretrained(
    "dh-unibe/trocr-kurrent"
).to(device)

# ---------------------------------------------------------------------------
# 3) HILFSFUNKTIONEN
# ---------------------------------------------------------------------------

def draw_polygon(img, polygon, color, thickness=2):
    pts = np.array(polygon, np.int32).reshape((-1, 1, 2))
    cv2.polylines(img, [pts], isClosed=True, color=color, thickness=thickness)

def ocr_line_crop(line_crop_bgr):
    """Nimmt ein BGR-Crop (cv2) und gibt OCR-Text via TrOCR zurück."""
    if line_crop_bgr is None or line_crop_bgr.size == 0:
        return ""
    img_rgb = cv2.cvtColor(line_crop_bgr, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)

    # winzige Zeilen ignorieren
    w, h = pil_img.size
    if w < 10 or h < 10:
        return ""

    inputs = processor(images=pil_img, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = trocr_model.generate(**inputs, max_length=256)
    text = processor.batch_decode(outputs, skip_special_tokens=True)[0]
    return text.strip()

def pdf_page_to_bgr(pdf_path: Path, page_index: int, dpi: int = 300):
    """Rendert eine PDF-Seite via PyMuPDF zu OpenCV-BGR (np.ndarray)."""
    doc = fitz.open(str(pdf_path))
    page = doc.load_page(page_index)

    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)  # alpha=False -> RGB

    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    doc.close()

    # PyMuPDF liefert RGB -> wir brauchen BGR
    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

# Globale Liste für CSV-Ausgabe
csv_rows = []

# ---------------------------------------------------------------------------
# 4) HAUPTFUNKTION: VERARBEITET EIN "BILD" (als BGR-Array) + Namen
# ---------------------------------------------------------------------------

def process_image_array(image_bgr: np.ndarray, page_name: str, out_stem: str):
    """
    image_bgr: OpenCV-BGR-Image
    page_name: Anzeigename für JSON/CSV (z.B. "file.pdf_p001" oder "image.jpg")
    out_stem : Dateiname-Stamm für Outputs (Overlay/JSON)
    """
    print(f"\n➡️ Verarbeite: {page_name}")

    if image_bgr is None or image_bgr.size == 0:
        print(f"❌ Bilddaten leer: {page_name}")
        return

    image = image_bgr.copy()
    H, W = image.shape[:2]
    output_json = {"page": page_name, "regions": []}

    # -----------------------------------------------------------------------
    # 5) REGIONEN SEGMENTIEREN
    # -----------------------------------------------------------------------

    # Ultralytics akzeptiert auch numpy arrays direkt
    region_results = region_model(image, imgsz=1024, verbose=False)[0]
    region_polygons = region_results.masks.xy if region_results.masks is not None else []

    print(f"   Gefundene Regionen: {len(region_polygons)}")

    # Regionen mit BBox vorbereiten
    regions = []
    for poly in region_polygons:
        poly = np.asarray(poly)
        xs = poly[:, 0]
        ys = poly[:, 1]
        x1, y1, x2, y2 = xs.min(), ys.min(), xs.max(), ys.max()
        regions.append({
            "poly": poly,
            "bbox": (int(x1), int(y1), int(x2), int(y2)),
        })

    # Sortierlogik: oben→unten, dann links→rechts
    regions_sorted = sorted(regions, key=lambda r: (r["bbox"][1], r["bbox"][0]))

    # -----------------------------------------------------------------------
    # 6) REGIONEN DURCHGEHEN
    # -----------------------------------------------------------------------

    for ridx, reg in enumerate(regions_sorted):

        region_poly = reg["poly"]
        x1, y1, x2, y2 = reg["bbox"]

        draw_polygon(image, region_poly, (0, 255, 0))

        region_crop = image[y1:y2, x1:x2].copy()
        region_entry = {
            "region_id": int(ridx),
            "bbox": [int(x1), int(y1), int(x2), int(y2)],
            "lines": []
        }

        # -------------------------------------------------------------------
        # 7) LINIEN INNERHALB DER REGION ERKENNEN
        # -------------------------------------------------------------------

        line_results = line_model(region_crop, imgsz=1024, verbose=False)[0]
        line_polygons = line_results.masks.xy if line_results.masks is not None else []

        print(f"      Region {ridx}: erkannte Zeilen → {len(line_polygons)}")

        # Falls wirklich keine Lines erkannt wurden → Region trotzdem speichern
        if not line_polygons:
            output_json["regions"].append(region_entry)
            csv_rows.append({
                "page": page_name,
                "region_id": int(ridx),
                "x1": int(x1),
                "y1": int(y1),
                "x2": int(x2),
                "y2": int(y2),
                "text": ""
            })
            continue

        # Lines mit BBox & Schwerpunkt vorbereiten
        lines = []
        for poly in line_polygons:
            poly = np.asarray(poly)
            xs = poly[:, 0]
            ys = poly[:, 1]
            x1_l, y1_l, x2_l, y2_l = xs.min(), ys.min(), xs.max(), ys.max()
            cy = (y1_l + y2_l) / 2.0
            cx = (x1_l + x2_l) / 2.0
            lines.append({
                "poly": poly,
                "centroid": (float(cx), float(cy)),
            })

        # Sortierlogik: oben→unten nach Schwerpunkt, dann links→rechts
        lines_sorted = sorted(
            lines,
            key=lambda l: (l["centroid"][1], l["centroid"][0])
        )

        # -------------------------------------------------------------------
        # 8) OCR PRO LINE
        # -------------------------------------------------------------------

        for lidx, line in enumerate(lines_sorted):
            line_poly = line["poly"]

            # relative → globale Koordinaten
            abs_poly = [[int(px + x1), int(py + y1)] for px, py in line_poly]

            # Visualisierung
            draw_polygon(image, abs_poly, (0, 165, 255))

            # BBox + Crop
            xs_line = [p[0] for p in abs_poly]
            ys_line = [p[1] for p in abs_poly]
            lx1, ly1, lx2, ly2 = min(xs_line), min(ys_line), max(xs_line), max(ys_line)

            line_crop = image[ly1:ly2, lx1:lx2].copy()
            text = ocr_line_crop(line_crop)

            region_entry["lines"].append({
                "line_id": int(lidx),
                "polygon": abs_poly,
                "bbox": [int(lx1), int(ly1), int(lx2), int(ly2)],
                "text": text,
            })

        # Gesamten Text der Region aus allen Zeilen zusammensetzen
        region_text = "\n".join(
            [ln["text"] for ln in region_entry["lines"] if ln["text"]]
        )

        # Zeile für CSV sammeln
        csv_rows.append({
            "page": page_name,
            "region_id": int(ridx),
            "x1": int(x1),
            "y1": int(y1),
            "x2": int(x2),
            "y2": int(y2),
            "text": region_text
        })

        output_json["regions"].append(region_entry)

    # -----------------------------------------------------------------------
    # 9) AUSGABEN PRO SEITE SPEICHERN
    # -----------------------------------------------------------------------

    out_img = OUTPUT_DIR / f"{out_stem}_overlay.jpg"
    cv2.imwrite(str(out_img), image)

    out_json = OUTPUT_DIR / f"{out_stem}.json"
    out_json.write_text(json.dumps(output_json, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"   ✔ Overlay gespeichert: {out_img.name}")
    print(f"   ✔ JSON+OCR gespeichert: {out_json.name}")

# ---------------------------------------------------------------------------
# 5) WRAPPER: VERARBEITET BILD-DATEI ODER PDF
# ---------------------------------------------------------------------------

def process_image_file(image_path: Path):
    image = cv2.imread(str(image_path))
    if image is None:
        print(f"❌ Datei konnte nicht gelesen werden: {image_path}")
        return
    page_name = image_path.name
    out_stem = image_path.stem
    process_image_array(image, page_name=page_name, out_stem=out_stem)

def process_pdf_file(pdf_path: Path):
    print(f"\n📄 PDF gefunden: {pdf_path.name}")
    doc = fitz.open(str(pdf_path))
    n_pages = doc.page_count
    doc.close()

    for p in range(n_pages):
        page_bgr = pdf_page_to_bgr(pdf_path, p, dpi=PDF_DPI)

        page_name = f"{pdf_path.name}_p{p+1:03d}"
        out_stem = f"{pdf_path.stem}_p{p+1:03d}"

        if SAVE_RENDERED_PDF_PAGES:
            rendered_path = OUTPUT_DIR / f"{out_stem}_render.png"
            cv2.imwrite(str(rendered_path), page_bgr)

        process_image_array(page_bgr, page_name=page_name, out_stem=out_stem)

# ---------------------------------------------------------------------------
# 6) ORDNER DURCHGEHEN UND CSV SCHREIBEN
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    files = list(IMAGE_FOLDER.glob("*.*"))
    image_files = [f for f in files if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".tif", ".tiff"]]
    pdf_files   = [f for f in files if f.suffix.lower() == ".pdf"]

    if not image_files and not pdf_files:
        print("❌ Keine Bilder oder PDFs im Ordner gefunden.")
        raise SystemExit

    print(f"\n📂 Verarbeite {len(image_files)} Bild(er) und {len(pdf_files)} PDF(s) aus: {IMAGE_FOLDER}")
    print(f"Ausgabeordner: {OUTPUT_DIR}\n")

    # Bilder
    for img in image_files:
        process_image_file(img)

    # PDFs (mehrseitig)
    for pdf in pdf_files:
        process_pdf_file(pdf)

    # CSV mit allen Regionen schreiben
    csv_path = OUTPUT_DIR / "regions_ocr.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["page", "region_id", "x1", "y1", "x2", "y2", "text"])
        for row in sorted(csv_rows, key=lambda r: (r["page"], r["y1"], r["x1"])):
            writer.writerow([
                row["page"],
                row["region_id"],
                row["x1"],
                row["y1"],
                row["x2"],
                row["y2"],
                row["text"]
            ])

    print("\n🎉 Fertig! Alle Ergebnisse im Ordner:")
    print("  Overlays & JSON:", OUTPUT_DIR)
    print("  CSV mit Regionstext:", csv_path)
