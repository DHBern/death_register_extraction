import xml.etree.ElementTree as ET
import csv
import re
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import os
import json
from datetime import datetime
import threading
from openai import OpenAI
import requests
import pandas as pd
from collections import defaultdict

#ToDO:  multiple xml for extraktion starten, Format im csv, 


client = OpenAI(
    base_url="https://gpustack.unibe.ch/v1-openai",
    api_key="gpustack_a0f67c08841e32f3_04262ea3cb3172504ea071b791d9ea38"
    ) # Tragen Sie hier Ihren API-Schlüssel ein


# ------------------------ Konstanten ------------------------
CONFIG_FILE = "keywords_tags_storage.json"
namespace = {'pg': 'http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15'}
DEST_DIR = r"C:\Users\janbl\OneDrive\Dokumente\test_xml_api" # Beispielpfad, ggf. anpassen
COLNAME_PREFIX = 'sterbedaten_ZH'
COLNAME_TRAINING = ['']
# ------------------------ Vordefinierte Presets ------------------------
predefined_presets = {
    "Jahrgang_1876": {
        "start_keywords": ["Den", "mittags", "bezeugt", "und der", "geboren den"],
        "end_keywords": ["Uhr", "ärztlich", "und der", "Confession", "Eingetragen den"],
        "tags": ["Todeszeit", "Todesort/Ursache", "Name/Beruf/Vater", "Mutter/Zivilstand/Wohn/Heimatort/Konfession", "Geburtsdatum"]
    },
    "Jahrgang_1877": {
        "start_keywords": ["Den", "mittags", "bezeugt", "und der", "geboren den"],
        "end_keywords": ["Uhr", "ärztlich", "und der", "Confession", "Eingetragen den"],
        "tags": ["Todeszeit", "Todesort/Ursache", "Name/Beruf/Vater", "Mutter/Zivilstand/Wohn/Heimatort/Konfession", "Geburtsdatum"]
    },
    "Jahrgang_1878": {
        "start_keywords": ["Den", "mittags", "bezeugt", "und der", "geboren den"],
        "end_keywords": ["Uhr", "ärztlich", "und der", "Confession", "Eingetragen den"],
        "tags": ["Todeszeit", "Todesort/Ursache", "Name/Beruf/Vater", "Mutter/Zivilstand/Wohn/Heimatort/Konfession", "Geburtsdatum"]
    },
    "Jahrgang_1879": {
        "start_keywords": ["Den", "mittags", "bezeugt", "und der", "geboren den"],
        "end_keywords": ["Uhr", "ärztlich", "und der", "Confession", "Eingetragen den"],
        "tags": ["Todeszeit", "Todesort/Ursache", "Name/Beruf/Vater", "Mutter/Zivilstand/Wohn/Heimatort/Konfession", "Geburtsdatum"]
    },
    "Jahrgang_1880": {
        "start_keywords": ["Den", "mittags", "bezeugt", "und der", "geboren den"],
        "end_keywords": ["Uhr", "ärztlich", "und der", "Confession", "Eingetragen den"],
        "tags": ["Todeszeit", "Todesort/Ursache", "Name/Beruf/Vater", "Mutter/Zivilstand/Wohn/Heimatort/Konfession", "Geburtsdatum"]
    },
    "Jahrgang_1881": {
        "start_keywords": ["Den", "mittags", "bezeugt", "und der", "geboren den"],
        "end_keywords": ["Uhr", "ärztlich", "und der", "Confession", "Eingetragen den"],
        "tags": ["Todeszeit", "Todesort/Ursache", "Name/Beruf/Vater", "Mutter/Zivilstand/Wohn/Heimatort/Konfession", "Geburtsdatum"]
    },
    "Jahrgang_1882": {
        "start_keywords": ["Den", "mittags", "bezeugt", "und der", "geboren den"],
        "end_keywords": ["Uhr", "ärztlich", "und der", "Confession", "Eingetragen den"],
        "tags": ["Todeszeit", "Todesort/Ursache", "Name/Beruf/Vater", "Mutter/Zivilstand/Wohn/Heimatort/Konfession", "Geburtsdatum"]
    },
    "Jahrgang_1883": {
        "start_keywords": ["Den", "mittags", "Bescheinigung", "in"],
        "end_keywords": ["Uhr", "ärztlicher", "Wohnhaft", "Eingetragen"],
        "tags": ["Todeszeit", "Todesort/Ursache", "Name/Beruf/Familienverhältnis/Vater/Mutter/Zivilstand/Religion/Heimatort", "Wohnort/Geburtsdatum"]
    },
    "Jahrgang_1906": {
        "start_keywords": ["Den", "mittags", "Bescheinigung", "in"],
        "end_keywords": ["Uhr", "ärztlicher", "Wohnhaft", "Eingetragen"],
        "tags": ["Todeszeit", "Todesort/Ursache", "Name/Beruf/Familienverhältnis/Vater/Mutter/Zivilstand/Religion/Heimatort", "Wohnort/Geburtsdatum"]
    }
}
# ------------------------ Vordefinierte Text1 für Chatgpt ------------------------
predefined_texts_text1 = {
    "Jahrgang_1876":["Den ersten ten Jener Lachtzehnhundert siebenzig und sechs — um zwei ein halb Uhr — Vor mittags starb in Zürich wühre Nro 13 an Harublasenentzündung _ärztlich bezeugt, Hans Konrad von Orelli (Beruf:) gewesener Laufmann des Hans Jakob von Orelli und der Qua Margaretha Straßer (Civilstand:) ledig von Zürich in Zürich reformirter Confession; geboren den sechs und zwanzigster Novembr. hundert sie benzehn und sieben und achtzig, Eingetragen den ersten Eingetragen den ersten ten Jener — achtzehnhundert siebzig und sechs auf die Angabe des Großnessen Johann Heinrich Zetter Kaufmann von Zürich wohnhaft in Riesbach Flora. straße 19. Abgelesen und bestätigt: Heinrich Zeller Der Civilstandsbeamte: Wyri"],
    "Jahrgang_1877":["Den diese, ten Januar achtzehnhundert fiebenzig üns fieben um halb vier Uhr Vor, mittags starb in Zürich, Neumarkt No 5. an neuter Lungentübereulose. ärztlich bezeugt, Johannes Geßner (Beruf:) Mechaniker. Sohn des Dr: Iuris Hans Gestern und der Kierline Bürgi, (Civilstand:). Ledig, von Zürich, in Zürich, reformierter Confession; geboren den zweiten July rechtzehn hundert vierzig und hiebei, Eingetragen den dies ten Januar achtzehnhundert siebenzig und fieben auf die Angabe der Schwestest Helene Geßner, von und in Zürich. Abgelesen und bestätigt: per Dr. H. Gessner Helene Gessner Der Civilstandsbeamte: Z. E. Wiss."],
    "Jahrgang_1878":["Den dritten Januar achtzehnhundert siedenzig uns achs VIII halb zwei Uhr 4 h mittags starbin Zürich, Stadthausplatz No 26, an Altersschwäche, — ärztlich bezeugt Johannes Mettler. (Beruf:) alt Scheiner, Sohn, des Johann Rudolf Wettler“ und der Elisabetha Reutimann (Civilstand:) Ehemann der Anna Barbara Güttinger,von W in Zürich reformirter Confession; geboren den achtzehnten November achtzehnhundert und eins¬ Eingetragen den dritten Januar. achtzehnhundert hiebenzig und acht - auf die Angabe der Beruftragten Heinrich Zoler, Stadthausabwert von und in Zürich. Abgelesen und bestätigt: Heinrich Isler Der Civilstandsbeamte; H. C. Wirz."],
    "Jahrgang_1879":["Den fünften Januar achtzehnhundert siebenzig unt neun um halb zwölf; Uhr Nach, mittags starb in Zürich, Steingasse No 9. all hornischer Lŭngenschwindsucht. ärztlich bezeugt Johob Schneider (Beruf:) Schüst er, Sohn des Stephan Schneider. und der Katharina Matthes, (Civilstand:) Ehemann der Barbara Single, von Ins in Zürich, reformirter Confession; geboren den achtundzwanzigsten Januar achtzehnhundert zwanzig und eins- Eingetragen den schoten Zimmer¬ achtzehnhundert siebenzig und neun — auf die Angabe der Berüfterzten Wilheim Rösler, Schneider, von und in Züricher Abgelesen und bestätigt: W. Rector Sehnende Der Civilstandsbeamte: H. C. Wirz"],
    "Jahrgang_1880":["Den neunten Genuest achtzehnhundert und achtzig. um halb acht. Uhr dor, mittags starb in Zürich, Kirchgasse Nr. 50. an Alterschwäche, ärztlich bezeugt Regula Brändli geb: Bodmest, (Beruf:) Tochter des Jakob Bodmer und der Anna Barbara Schmid, (Civilstand:) Wiltern des Honord Brändli, Kaufmann, von Großen, - in Zürich „erformirter Confession: geboren den „ofen Julij“ achtzehnhundert und sechs. Eingetragen den neunten Januar Lachtzelmhundert und schätzig — auf die Angabe der Tochter Amalie Beändli. Abgelesen und bestätigt; Brandli Der Civilstandsbeamte:"],
    "Jahrgang_1881":["Den ersten Januar achtzehnhundert sechtzig und eins um halb neun Uhr vor mittags starb in Zürich, Zähringerstraße Nr. 25. an Lebensschwäche, ärztlich bezeugt. Irme Mama, (Beruf:) Tochter des Julius Mama, Kaufmann und der Amalie Güggenheim, (Civilstand:) von Scobotist, Ungarn, in Zürich, israelitische Confession, geboren den ersten Dezember achtzehnhundert und achtzig. Eingetragen den ersten Januar achtzehnhundert achtzig und eins auf die Angabe der Anverwandten Moritz Güggenheim, Kaufmann, in Zürich, Abgelesen und bestätigt: Moritz Guccenheim Mitgetheilt nach Scobotist, Der Civilstandsbeamte: H. C. Wirz"],
    "Jahrgang_1882":["Den ersten Januar achtzehnhundert achtzig und zwei um neün ein viertel. Uhr daß, mittags starb in Zürich, Bärengasse N°14. an Lungentüberwiese. ärztlich bezeugt, von Wyß, Sophie Henriette, — (Beruf:) Tochter des Konrad von Nyß, Kaufmann und der Anna Sophie Kündig, (Civilstand:) Indig, von Ini in Zürich, Reformirten Confession; geboren den aften Mai achtzehnhundert sechszig und acht. Eingetragen den zweiten Januar achtzehnhundert achtzig und zwei- auf die Angabe des Onbels Heinrich david von Wyß, von und in Zürich. Abgelesen und bestätigt: Heinrich David Wyss Der Civilstandsbeamte: H. C. Dist."],
    "Jahrgang_1883":["Den ersten Januar eintausend achthundert achtzig und der al um acht“ Uhr dreißig Minuten auf „mittags ist gestorben zu Zürich, Schöffelgesse d.o 4. an Zionschlaghlüß. laut ärztlicher Bescheinigung. Lüßi. Verena geb: Baus, Beruf: Sesselflochterien Tochter des Hans Jakob Bauß und der Anna Hofstetter Civilstand: Mit war das Hans Jakob Religion: erformirt, von Müssen! er oh, wohnhaft in gleich, — geboren den einuntzwanzigsten Jürg eintausend acht hundert zwanzig und eins. Eingetragen in gegenwärtiges Register den zweiten eintausend achthundert achtzigeind die auf die Anzeige des Sohnes Albert Lußi, Maler, in Aussersihl. Vorgelesen, und bestätigt: Albert Lichsi Maler Der Civilstandsbeamte: H. C. 1151"],
    "Jahrgang_1906":["Den zweiten April eintausendneunhundert und sechs um ein Uhr Minuten ei mittags ist gestorben zu Zürich, Simmalquai N.C.C., an Magenkrebs laut ärztlicher Bescheinigung Besshard Heinrich Beruf: Kaufmann Sehn des Rosshard, David und der Susanna geb: Bachofel Zivilstand: Galle der Barbara geb Religion: Hofmann von Zürich wohnhaft in Zünd geboren den finfundzwanzigsten Augusteintausend acht hundert vierendvrivig Eingetragen in gegenwärtiges Register den Zeilen theil eintausendneunhundert sichs auf die Anzeige des Sohnes Besshard Trud Vorgelesen und besätigt: Ernst Gosshard Der Zivilstandsbeamte:(c. wirt)"]
}
#------------------------ API Verbindung ------------------------
def call_chatgpt(prompt_text):
    try:
        response = client.chat.completions.create(
            model="gpt-oss-120b", 
            messages=[
                {"role": "system", "content": ""},
                {"role": "user", "content": prompt_text}
            ],
            temperature=0.0
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Fehler bei API-Aufruf: {e}")
        return "" # Im Fehlerfall einen leeren String zurückgeben
    

def debug_connectivity():
    try:
        ms = client.models.list()
        print("DEBUG: models.list OK, count =", len(ms.data))
        print("DEBUG: first models =", [m.id for m in ms.data[:10]])
    except Exception as e:
        print("DEBUG: models.list failed:", repr(e))

debug_connectivity()

#------------------------ Keyword/Tag Speicher ------------------------
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        keyword_data = json.load(f)
else:
    keyword_data = {}

def save_keywords_tags():
    name = simpledialog.askstring("Speichern", "Gib einen Namen für die Start-/Stoppwörter und Tags ein:")
    if not name:
        return

    start_input = start_entry.get().strip()
    end_input = end_entry.get().strip()
    tags_input = tag_entry.get().strip()

    if not start_input or not end_input or not tags_input:
        messagebox.showwarning("Fehler", "Bitte gib Start-/Stoppwörter und Tags ein.")
        return

    keyword_data[name] = {
        "start_keywords": [word.strip().strip('"') for word in start_input.split(",") if word.strip()],
        "end_keywords": [word.strip().strip('"') for word in end_input.split(",") if word.strip()],
        "tags": [tag.strip() for tag in tags_input.split(",") if tag.strip()]
    }

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(keyword_data, f)
    messagebox.showinfo("Erfolg", f"Start-/Stoppwörter & Tags unter '{name}' gespeichert!")

def load_keywords_tags():
    if not keyword_data:
        messagebox.showwarning("Fehler", "Keine gespeicherten Start-/Stoppwörter & Tags gefunden.")
        return

    name = simpledialog.askstring("Laden", "Gib den Namen der gespeicherten Einträge ein:")
    if not name or name not in keyword_data:
        messagebox.showwarning("Fehler", f"Kein Eintrag unter '{name}' gefunden.")
        return

    start_entry.delete(0, tk.END)
    end_entry.delete(0, tk.END)
    tag_entry.delete(0, tk.END)

    start_entry.insert(0, ", ".join(keyword_data[name]["start_keywords"]))
    end_entry.insert(0, ", ".join(keyword_data[name]["end_keywords"]))
    tag_entry.insert(0, ", ".join(keyword_data[name]["tags"]))
    messagebox.showinfo("Erfolg", f"Start-/Stoppwörter & Tags von '{name}' geladen!")
#------------------------ Transkribus XML Download ------------------------
def refresh_file_list():
    file_listbox.delete(0, tk.END)
    if not DEST_DIR or not os.path.exists(DEST_DIR): # Überprüfen, ob DEST_DIR existiert
        return
    for root_dir_walk, _, files_walk in os.walk(DEST_DIR):
        for file_walk in files_walk:
            if file_walk.endswith(".xml"):
                file_listbox.insert(tk.END, os.path.join(root_dir_walk, file_walk))
#------------------------ XML Extraktion ------------------------
def upload_files():
    files_selected = filedialog.askopenfilenames(filetypes=[("XML Files", "*.xml")])
    if files_selected:
        file_listbox.delete(0, tk.END)
        for file_item in files_selected:
            file_listbox.insert(tk.END, file_item)

def remove_selected_files():
    selected_indices = file_listbox.curselection()
    if not selected_indices:
        messagebox.showwarning("Hinweis", "Bitte wähle eine oder mehrere Dateien aus, die entfernt werden sollen.")
        return
    for index in reversed(selected_indices):
        file_listbox.delete(index)

def extract_between_keywords_single(text, start_keyword, end_keyword): 
    pattern = rf"\b{re.escape(start_keyword)}\b(.*?)\b{re.escape(end_keyword)}\b"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE) 
    if match:
        return match.group(1).strip()
    return None

def start_extraction():
    files_to_extract = file_listbox.get(0, tk.END)
    if not files_to_extract:
        messagebox.showwarning("Fehler", "Bitte wähle mindestens eine XML-Datei aus!")
        return

    start_keywords_str = start_entry.get().strip()
    end_keywords_str = end_entry.get().strip()
    tags_str = tag_entry.get().strip()

    if not start_keywords_str or not end_keywords_str or not tags_str:
        messagebox.showwarning("Fehler", "Bitte definiere Start-/Stoppwörter & Tags!")
        return

    start_keywords_list = [word.strip() for word in start_keywords_str.split(",")]
    end_keywords_list = [word.strip() for word in end_keywords_str.split(",")]
    tags_list = [tag.strip() for tag in tags_str.split(",")]

    if not (len(start_keywords_list) == len(end_keywords_list) == len(tags_list)):
        messagebox.showwarning("Fehler", "Die Anzahl der Startwörter, Stoppwörter und Tags muss übereinstimmen!")
        return

    all_extracted_data = []

    for file_index, file_path_extract in enumerate(files_to_extract, start=1):
        try:
            tree = ET.parse(file_path_extract)
            root_element = tree.getroot()
            original_filename = os.path.basename(file_path_extract)

            id_field1 = ""
            id_field2 = ""


            idfield1_region = root_element.find(".//pg:TextRegion[contains(@custom, 'type:IDField_1')]", namespace)
            if idfield1_region is not None:
                text_nodes = idfield1_region.findall(".//pg:TextLine/pg:TextEquiv/pg:Unicode", namespace)
                if not text_nodes:
                    text_nodes = idfield1_region.findall("./pg:TextEquiv/pg:Unicode", namespace)

                id_field1 = " ".join(
                    (unicode_text.text or "").strip()
                    for unicode_text in text_nodes
                    if unicode_text.text
                ).strip()

            idfield2_region = root_element.find(".//pg:TextRegion[contains(@custom, 'type:IDField_2')]", namespace)
            if idfield2_region is not None:
                text_nodes = idfield2_region.findall(".//pg:TextLine/pg:TextEquiv/pg:Unicode", namespace)
                if not text_nodes:
                    text_nodes = idfield2_region.findall("./pg:TextEquiv/pg:Unicode", namespace)

                id_field2 = " ".join(
                    (unicode_text.text or "").strip()
                    for unicode_text in text_nodes
                    if unicode_text.text
                ).strip()

            # Kombinieren (nur einer wird benutzt, falls einer leer ist)
            id_field_combined = id_field1 or id_field2

            # ContentField_1
            for region_index, region in enumerate(
                root_element.findall(".//pg:TextRegion[contains(@custom, 'type:ContentField_1')]", namespace),
                start=1
            ):
                # 1) Versuche erst Zeilen (Transkribus-Fall)
                text_nodes = region.findall(".//pg:TextLine/pg:TextEquiv/pg:Unicode", namespace)

                # 2) Fallback: TextEquiv direkt unter Region (YOLO+TrOCR-Fall)
                if not text_nodes:
                    text_nodes = region.findall("./pg:TextEquiv/pg:Unicode", namespace)

                full_text1 = " ".join(
                    (unicode_text.text or "").strip()
                    for unicode_text in text_nodes
                    if unicode_text.text
                )

                for i, (start_kw, end_kw) in enumerate(zip(start_keywords_list, end_keywords_list)):
                    extracted_text1 = extract_between_keywords_single(full_text1, start_kw, end_kw)
                    if extracted_text1:
                        tag = tags_list[i]
                        all_extracted_data.append({
                            'Datei': original_filename,
                            'XML_Block_Index': region_index,
                            'Segment_Nr': region_index,
                            'Extrahierter_Text_API': extracted_text1,
                            'Tag': tag,
                            'ID_Field': id_field_combined
                        })


            # ContentField_2 (gleiches Prinzip)
            for region_index, region in enumerate(
                root_element.findall(".//pg:TextRegion[contains(@custom, 'type:ContentField_2')]", namespace),
                start=1
            ):
                text_nodes = region.findall(".//pg:TextLine/pg:TextEquiv/pg:Unicode", namespace)
                if not text_nodes:
                    text_nodes = region.findall("./pg:TextEquiv/pg:Unicode", namespace)

                full_text2 = " ".join(
                    (unicode_text.text or "").strip()
                    for unicode_text in text_nodes
                    if unicode_text.text
                )

                for i, (start_kw, end_kw) in enumerate(zip(start_keywords_list, end_keywords_list)):
                    extracted_text2 = extract_between_keywords_single(full_text2, start_kw, end_kw)
                    if extracted_text2:
                        tag = tags_list[i]
                        all_extracted_data.append({
                            'Datei': original_filename,
                            'XML_Block_Index': region_index,
                            'Segment_Nr': region_index,
                            'Extrahierter_Text_API': extracted_text2,
                            'Tag': tag,
                            'ID_Field': id_field_combined
                        })

        except ET.ParseError:
            messagebox.showerror("Fehler", f"Konnte XML-Datei nicht parsen: {file_path_extract}")
        except Exception as e_extract:
            messagebox.showerror("Fehler", f"Ein Fehler ist bei der Extraktion von {file_path_extract} aufgetreten: {e_extract}")

    save_results_to_csv_api(all_extracted_data)

def save_results_xml(extracted_data): # Umbenannt zur Unterscheidung
    save_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
    if save_path:
        with open(save_path, mode="w", newline='', encoding="utf-8") as file_csv:
            writer = csv.writer(file_csv)
            writer.writerow(["XML_ID", "Dateiname", "TextRegion", "Extrahierter Text", "Tag"])
            writer.writerows(extracted_data)
#------------------------ Auswertung API ------------------------
def process_with_chatgpt():
    jahrgang = jahrgang_combobox.get().strip()
    print(f"DEBUG: Ausgewählter Jahrgang: '{jahrgang}'")

    if not jahrgang:
        messagebox.showwarning("Fehler", "Bitte Jahrgang auswählen.")
        return

    text1_list = predefined_texts_text1.get(jahrgang)
    if not text1_list:
        messagebox.showwarning("Fehler", f"Kein vordefinierter Text Nr. 1 für Jahrgang '{jahrgang}' gefunden.")
        return
    text1 = text1_list[0]
    print(f"DEBUG: Text Nr. 1 (aus predefined_texts_text1): '{text1}'")

    preset = predefined_presets.get(jahrgang, {})
    start_keywords = preset.get("start_keywords", [])
    end_keywords = preset.get("end_keywords", [])
    tags_from_preset = preset.get("tags", [])
    print(f"DEBUG: Start-Keywords (aus predefined_presets): {start_keywords}")
    print(f"DEBUG: End-Keywords (aus predefined_presets): {end_keywords}")
    print(f"DEBUG: Tags (aus predefined_presets): {tags_from_preset}")

    if not (len(start_keywords) == len(end_keywords) == len(tags_from_preset)):
        messagebox.showwarning("Fehler im Preset", f"Für Jahrgang '{jahrgang}' stimmt die Anzahl der Start-Keywords, End-Keywords und Tags nicht überein. Bitte Preset prüfen.")
        return

    all_results_api = []  # Hier die Liste für alle Ergebnisse initialisieren
    files_to_process = file_listbox.get(0, tk.END)
    print(f"DEBUG: Zu verarbeitende Dateien aus der Liste: {files_to_process}")

    if not files_to_process:
        messagebox.showwarning("Fehler", "Bitte wählen Sie XML-Dateien für die Verarbeitung aus.")
        return

    for file_path_api in files_to_process:
        print(f"DEBUG: Verarbeite ausgewählte XML-Datei: '{file_path_api}'")
        extracted_data_from_xml = extract_texts_and_id_from_xml(file_path_api)
        content_texts = extracted_data_from_xml.get('content_texts', [])
        id_field1_text = extracted_data_from_xml.get('id_field1', '')
        id_field2_text = extracted_data_from_xml.get('id_field2', '')
        file_name_for_csv = os.path.basename(file_path_api)
        all_results_api_for_file = [] # Ergebnisse für die aktuelle Datei

        for original_text_index, text2_content in enumerate(content_texts):
            print(f"DEBUG: Verarbeite Content-Text Nr. {original_text_index + 1}: '{text2_content}'")
            prompt = build_prompt(text1, text2_content, start_keywords, end_keywords)
            print(f"DEBUG: Erstellter Prompt:\n'''\n{prompt}\n'''")

            api_response = call_chatgpt(prompt)
            print(f"DEBUG: Antwort von ChatGPT:\n'''\n{api_response}\n'''")

            extracted_segments_from_api = extract_between_keywords_api(api_response, start_keywords, end_keywords)
            print(f"DEBUG: Gefilterte Segmente (nach Keywords aus API-Antwort): {extracted_segments_from_api}")

            for segment_idx, segment_text in enumerate(extracted_segments_from_api):
                if segment_idx < len(tags_from_preset):
                    current_tag = tags_from_preset[segment_idx]
                    all_results_api_for_file.append({
                        "Datei": file_name_for_csv,
                        "XML_Block_Index": original_text_index + 1,
                        "Segment_Nr": segment_idx + 1,
                        "Extrahierter_Text_API": segment_text,
                        "Tag": current_tag
                    })
                else:
                    all_results_api_for_file.append({
                        "Datei": file_name_for_csv,
                        "XML_Block_Index": original_text_index + 1,
                        "Segment_Nr": segment_idx + 1,
                        "Extrahierter_Text_API": segment_text,
                        "Tag": "Tag nicht definiert"
                    })
                    print(f"WARNUNG: Mehr Segmente als Tags für Datei {file_name_for_csv}, Segment {segment_idx+1}")

            # Füge das entsprechende IDField direkt unterhalb des verarbeiteten ContentFields ein
            if original_text_index == 0 and id_field1_text:
                all_results_api_for_file.append({
                    "Datei": file_name_for_csv,
                    "XML_Block_Index": 1, # Bezieht sich auf das erste ContentField
                    "Segment_Nr": 2,     # Direkt darunter
                    "Extrahierter_Text_API": id_field1_text,
                    "Tag": "IDField_1"
                })
            elif original_text_index == 1 and id_field2_text:
                all_results_api_for_file.append({
                    "Datei": file_name_for_csv,
                    "XML_Block_Index": 2, # Bezieht sich auf das zweite ContentField
                    "Segment_Nr": 2,     # Direkt darunter
                    "Extrahierter_Text_API": id_field2_text,
                    "Tag": "IDField_2"
                })
        all_results_api.extend(all_results_api_for_file) # Ergebnisse der aktuellen Datei zu den gesamten Ergebnissen hinzufügen
        print(f"DEBUG: Endergebnisse für Datei {file_name_for_csv}: {all_results_api_for_file}")

    if all_results_api:
        save_results_to_csv_api(all_results_api, predefined_presets, jahrgang) # Speichern aller Ergebnisse NACH der Schleife
    else:
        print("DEBUG: Keine Ergebnisse zum Speichern.")

    messagebox.showinfo("Fertig", "Alle Ergebnisse der API-Verarbeitung wurden gespeichert.")


def extract_texts_and_id_from_xml(path):
    extracted_data = {'content_texts': [], 'id_field1': '', 'id_field2': ''}
    try:
        tree = ET.parse(path)
        root_element = tree.getroot()

        # Namespace der Datei dynamisch bestimmen
        tag = root_element.tag  # z.B. "{http://schema.../2019-07-15}PcGts"
        if tag.startswith("{"):
            uri = tag[1:].split("}")[0]
            ns = {'pg': uri}
        else:
            ns = namespace  # Fallback auf globales namespace

        # Hilfsfunktion: Text aus Region holen (Zeilen oder direkt TextEquiv)
        def get_region_text(region):
            # zuerst versuchen wir TextLine -> TextEquiv -> Unicode
            text_nodes = region.findall(".//pg:TextLine/pg:TextEquiv/pg:Unicode", ns)
            if not text_nodes:
                # YOLO: TextEquiv direkt unter TextRegion
                text_nodes = region.findall("./pg:TextEquiv/pg:Unicode", ns)
            return " ".join(
                (u.text or "").strip()
                for u in text_nodes
                if u.text
            ).strip()

        # Alle TextRegion-Elemente holen
        all_regions = root_element.findall(".//pg:TextRegion", ns)

        # ---------- IDField_1 ----------
        for region in all_regions:
            custom = region.get("custom", "")
            if "type:IDField_1" in custom:
                extracted_data['id_field1'] = get_region_text(region)
                break

        # ---------- IDField_2 ----------
        for region in all_regions:
            custom = region.get("custom", "")
            if "type:IDField_2" in custom:
                extracted_data['id_field2'] = get_region_text(region)
                break

        # ---------- ContentField_1 ----------
        for region in all_regions:
            custom = region.get("custom", "")
            if "type:ContentField_1" in custom:
                full_text = get_region_text(region)
                if full_text:
                    extracted_data['content_texts'].append(full_text)

        # ---------- ContentField_2 ----------
        for region in all_regions:
            custom = region.get("custom", "")
            if "type:ContentField_2" in custom:
                full_text = get_region_text(region)
                if full_text:
                    extracted_data['content_texts'].append(full_text)

    except ET.ParseError:
        messagebox.showerror("Fehler", f"Konnte XML-Datei nicht parsen: {path}")
    except Exception as e:
        messagebox.showerror("Fehler", f"Ein Fehler ist beim Extrahieren von Text aus {path} aufgetreten: {e}")
    return extracted_data

def extract_texts_from_xml(path):
    extracted_texts = []
    try:
        tree = ET.parse(path)
        root_element = tree.getroot()

        # Namespace dynamisch bestimmen
        tag = root_element.tag
        if tag.startswith("{"):
            uri = tag[1:].split("}")[0]
            ns = {'pg': uri}
        else:
            ns = namespace

        def get_region_text(region):
            text_nodes = region.findall(".//pg:TextLine/pg:TextEquiv/pg:Unicode", ns)
            if not text_nodes:
                text_nodes = region.findall("./pg:TextEquiv/pg:Unicode", ns)
            return " ".join(
                (u.text or "").strip()
                for u in text_nodes
                if u.text
            ).strip()

        all_regions = root_element.findall(".//pg:TextRegion", ns)

        # ContentField_1 & ContentField_2
        for region in all_regions:
            custom = region.get("custom", "")
            if "type:ContentField_1" in custom or "type:ContentField_2" in custom:
                full_text = get_region_text(region)
                if full_text:
                    extracted_texts.append(full_text)

        # IDField_1 & IDField_2 (falls du sie hier auch aufnehmen willst)
        for region in all_regions:
            custom = region.get("custom", "")
            if "type:IDField_1" in custom or "type:IDField_2" in custom:
                full_text_id = get_region_text(region)
                if full_text_id:
                    extracted_texts.append(full_text_id)

    except ET.ParseError:
        messagebox.showerror("Fehler", f"Konnte XML-Datei nicht parsen: {path}")
    except Exception as e:
        messagebox.showerror("Fehler", f"Ein Fehler ist beim Extrahieren von Text aus {path} aufgetreten: {e}")
    return extracted_texts


def build_prompt(text1, text2, start_keywords, end_keywords):
    # Die Start-Stop-Wörter-Liste für den Prompt formattieren
    # Beispiel: "Den" (Inhalt bis) "Uhr", "mittags" (Inhalt bis) "ärztlich", ...
    keyword_instructions = ", ".join([f'"{start}" leitet ein Segment ein, das mit "{stop}" endet' for start, stop in zip(start_keywords, end_keywords)])

    prompt_text = f"""
Analysiere die folgenden zwei Texte: Text Nr1 und Text Nr2.

Text Nr1 dient als strikte Vorlage für die korrekte Struktur, Reihenfolge der Informationen und den Satzbau:
'''
{text1}
'''

Text Nr2 enthält die eigentlichen, spezifischen Informationen (Namen, Daten, Orte, Berufe, Todesursachen etc.), die extrahiert und verwendet werden müssen. Dieser Text kann Transkriptionsfehler oder eine falsche Reihenfolge der Wörter enthalten:
'''
{text2}
'''

Deine Aufgabe ist es, einen neuen Text zu erstellen, der ausschließlich auf den **Informationen aus Text Nr2** basiert. Dieser neue Text muss:
1.  Exakt die spezifischen Details (Personennamen, Daten, Orte, berufliche Angaben, familiäre Verhältnisse, Todesursachen etc.) aus Text Nr2 wiedergeben. Diese Details dürfen **NICHT** aus Text Nr1 übernommen oder erfunden werden.
2.  Die Satzstruktur, den Stil und die Reihenfolge der Informationsblöcke von Text Nr1 übernehmen.
3.  Offensichtliche Transkriptionsfehler, die in Text Nr2 vorhanden sein könnten (z.B. falsch erkannte Buchstaben, fehlende Leerzeichen), korrigieren.
4.  Die Informationen gemäß der folgenden Struktur von Start- und Stoppwörtern gliedern. Jedes Paar definiert ein Segment. Fülle die Informationen aus Text Nr2 in diese Segmente ein:
    {keyword_instructions}

Gib als Ergebnis **ausschließlich den neu formulierten Text basierend auf Text Nr2** zurück. Füge keine einleitenden Sätze wie "Text Nr2 korrigiert..." oder andere Erklärungen deinerseits hinzu. Die Antwort soll direkt mit dem ersten Wort des korrigierten Textes (typischerweise einem Start-Keyword wie "Den") beginnen.
"""
    return prompt_text.strip()

def extract_between_keywords_api(text, start_keywords, end_keywords): # Umbenannt zur Klarheit
    sections = []
    for start, end in zip(start_keywords, end_keywords):
        # Pattern angepasst, um flexibler auf Leerzeichen und Wortgrenzen zu reagieren
        # und um sicherzustellen, dass Start- und End-Keywords als ganze Wörter behandelt werden.
        pattern = rf"{re.escape(start)}(.*?){re.escape(end)}"
        try:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE) # IGNORECASE beibehalten
            if match:
                # strip() entfernt führende/nachfolgende Leerzeichen aus dem extrahierten Inhalt
                sections.append(match.group(1).strip())
            else:
                sections.append("") # Konsistent leere Strings für nicht gefundene Sektionen
        except re.error as e:
            print(f"Regex-Fehler für Start: '{start}', Ende: '{end}': {e}")
            sections.append("[Regex Fehler]")
    return sections

def save_results_to_csv_api(results_data, predefined_presets, jahrgang):
    if not results_data:
        print("Keine Daten zum Speichern.")
        return

    if jahrgang not in predefined_presets:
        print(f"Jahrgang '{jahrgang}' nicht in predefined_presets gefunden.")
        return

    tag_spalten = predefined_presets[jahrgang]["tags"]

    grouped_entries = defaultdict(lambda: {
        #"ID_Field": "",
        "Datei": "",
        "XML_Block_Index": "",
        **{tag: "" for tag in tag_spalten}
    })

    for entry in results_data:
        datei = entry.get("Datei", "")
        block_index = entry.get("XML_Block_Index", "")
        tag = entry.get("Tag", "")
        text = entry.get("Extrahierter_Text_API", "")

        key = (datei, block_index) 

        grouped_entries[key]["Datei"] = datei
        grouped_entries[key]["XML_Block_Index"] = block_index

#        if tag == "IDField_1" or tag == "IDField_2":
#            if not grouped_entries[key]["ID_Field"]: 
#                 grouped_entries[key]["ID_Field"] = text
        if tag in tag_spalten: 
            grouped_entries[key][tag] = text

    final_rows = list(grouped_entries.values())

    column_order = ["Datei", "XML_Block_Index"] + tag_spalten

    df = pd.DataFrame(final_rows, columns=column_order)
    save_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
    if save_path:
        try:
            df.to_csv(save_path, index=False, encoding="utf-8-sig")
            print(f"Ergebnisse erfolgreich in {save_path} gespeichert.")
            messagebox.showinfo("Speicherpfad", f"Der Speicherpfad ist:\n{save_path}")
        except Exception as e_save:
            messagebox.showerror("Fehler beim Speichern", f"Konnte die CSV nicht speichern: {e_save}")

#------------------------ GUI ------------------------
root = tk.Tk()
root.title("XML Text Extraktion mit Transkribus & API")

progress_bar = ttk.Progressbar(root, mode='indeterminate')

frame_files = tk.Frame(root)
frame_files.pack(pady=10, padx=10, fill=tk.X)

tk.Label(frame_files, text="XML-Dateien:").pack(anchor=tk.W)
file_listbox_frame = tk.Frame(frame_files)
file_listbox_frame.pack(fill=tk.X)
file_listbox = tk.Listbox(file_listbox_frame, width=100, height=6) # Breite angepasst
file_listbox_scrollbar = ttk.Scrollbar(file_listbox_frame, orient="vertical", command=file_listbox.yview)
file_listbox.configure(yscrollcommand=file_listbox_scrollbar.set)
file_listbox_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)


buttons_files_frame = tk.Frame(frame_files)
buttons_files_frame.pack(fill=tk.X, pady=5)
tk.Button(buttons_files_frame, text="Dateien hochladen", command=upload_files).pack(side=tk.LEFT, padx=2)
tk.Button(buttons_files_frame, text="Ausgewählte entfernen", command=remove_selected_files).pack(side=tk.LEFT, padx=2)

# Transkribus Download Optionen
transkribus_frame = tk.LabelFrame(frame_files, text="Transkribus Download")
transkribus_frame.pack(fill=tk.X, pady=5)
download_option = tk.StringVar(value="all")
tk.Radiobutton(transkribus_frame, text="Alle Dateien der Collection(s)", variable=download_option, value="all").pack(anchor=tk.W)
tk.Radiobutton(transkribus_frame, text="Einzelne Datei (nach Name)", variable=download_option, value="single").pack(anchor=tk.W)



frame_keywords = tk.LabelFrame(root, text="Keyword-basierte Extraktion & Presets")
frame_keywords.pack(pady=10, padx=10, fill=tk.X)

tk.Label(frame_keywords, text="Vordefiniertes Preset:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
preset_combobox = ttk.Combobox(frame_keywords, values=list(predefined_presets.keys()) + [""] , state="readonly", width=47) # "" für leere Auswahl
preset_combobox.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)
preset_combobox.set("") # Standardmäßig leer

def load_preset_from_dropdown(event=None):
    selected = preset_combobox.get()
    if selected in predefined_presets:
        preset = predefined_presets[selected]
        start_entry.delete(0, tk.END)
        start_entry.insert(0, ", ".join(preset.get("start_keywords", [])))
        end_entry.delete(0, tk.END)
        end_entry.insert(0, ", ".join(preset.get("end_keywords", [])))
        tag_entry.delete(0, tk.END)
        tag_entry.insert(0, ", ".join(preset.get("tags", [])))
    elif selected == "": # Leere Auswahl löscht Felder
        start_entry.delete(0, tk.END)
        end_entry.delete(0, tk.END)
        tag_entry.delete(0, tk.END)

preset_combobox.bind("<<ComboboxSelected>>", load_preset_from_dropdown)

tk.Label(frame_keywords, text="Startwörter (kommagetrennt):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
start_entry = tk.Entry(frame_keywords, width=50)
start_entry.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=2)

tk.Label(frame_keywords, text="Stoppwörter (kommagetrennt):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
end_entry = tk.Entry(frame_keywords, width=50)
end_entry.grid(row=2, column=1, sticky=tk.EW, padx=5, pady=2)

tk.Label(frame_keywords, text="Tags (kommagetrennt):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
tag_entry = tk.Entry(frame_keywords, width=50)
tag_entry.grid(row=3, column=1, sticky=tk.EW, padx=5, pady=2)

frame_keywords.columnconfigure(1, weight=1) # Erlaubt dem Entry-Feld zu wachsen

button_frame_keywords = tk.Frame(frame_keywords)
button_frame_keywords.grid(row=4, column=0, columnspan=2, pady=5)
tk.Button(button_frame_keywords, text="Speichern (Preset)", command=save_keywords_tags).pack(side=tk.LEFT, padx=5)
tk.Button(button_frame_keywords, text="Laden (Preset)", command=load_keywords_tags).pack(side=tk.LEFT, padx=5)
tk.Button(frame_keywords, text="XML Keyword-Extraktion starten", command=start_extraction).grid(row=5, column=0, columnspan=2, pady=10)


frame_api = tk.LabelFrame(root, text="API-basierte Auswertung (GPT)")
frame_api.pack(pady=10, padx=10, fill=tk.X)

tk.Label(frame_api, text="Jahrgang für Text Nr.1 & Keywords/Tags Preset:").pack(anchor=tk.W, padx=5, pady=2)
jahrgang_combobox = ttk.Combobox(frame_api, values=[""] + list(predefined_texts_text1.keys()), width=47, state="readonly") # "" für leere Auswahl
jahrgang_combobox.pack(fill=tk.X, padx=5, pady=2)
jahrgang_combobox.set("") # Standardmäßig leer

gpt_button = tk.Button(frame_api, text="GPT-Verarbeitung starten", command=lambda: threading.Thread(target=process_with_chatgpt, daemon=True).start())
gpt_button.pack(pady=10)

if not os.path.exists(DEST_DIR):
    os.makedirs(DEST_DIR, exist_ok=True)
root.mainloop()