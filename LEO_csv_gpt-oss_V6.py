from openai import OpenAI
import json
import pandas as pd
import re
from pathlib import Path
from tqdm import tqdm
import ast
import traceback

# nur für status bar
tqdm.pandas()


client = OpenAI(
    base_url="https://gpustack.unibe.ch/v1-openai",
    api_key="gpustack_a0f67c08841e32f3_04262ea3cb3172504ea071b791d9ea38"
)

model = "gpt-oss-120b"


#region llm promts
def ask_llm(prompt):

    content = ""

    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": "Du bist ein Informationsextraktionssystem für historische Sterberegister."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        content = response.choices[0].message.content
        content = content.replace("```json", "").replace("```", "").strip()

        start = content.find("{")
        end = content.rfind("}")

        if start != -1 and end != -1:
            content = content[start:end + 1]

        return safe_parse(content)

    except Exception as e:
        print("LLM Fehler:", e)
        print(content)
        return None

def extract_person(text):

    text = str(text) if pd.notna(text) else "-"
    text = text.replace("{", "(").replace("}", ")")

    prompt = f"""
Der Text stammt aus OCR historischer Handschriften.

Es können Schreibfehler,
fehlende Satzzeichen,
fehlende Doppelpunkte,
verstümmelte Wörter
und falsche Buchstaben vorkommen.

Erkenne die Struktur trotzdem möglichst robust.
Extrahiere ausschließlich die folgenden Informationen aus dem Text.

Wenn eine Information nicht vorhanden ist, gib "-" zurück.
Verwende ausschließlich Informationen aus dem Text.
Erfinde keine Informationen.
Antworte ausschließlich als gültiges JSON.    
Text:

{text}


Extrahiere ausschließlich:

- Name
- Beruf
- Vater
- Mutter
- Zivilstand
- Religion
- Heimatort

NAME:
- Format: Vorname(n) Nachname
- Falls im Text "Nachname, Vorname" → umdrehen

BERUF:

BERUF

Extrahiere den Beruf, wenn er eindeutig im Text genannt wird.

Mögliche Schreibweisen sind unter anderem:

Beruf:
(Beruf:)
(Beruf)
Beruf

Falls keine Berufsüberschrift vorhanden ist, der Beruf aber eindeutig zwischen Name und Familienangaben steht, extrahiere ihn ebenfalls.


- KEINE Familienbezeichnungen als Beruf:
  - Sohn, Tochter, Töchterlein, Knabe, Mädchen → Beruf = "-"

WICHTIG

Kinder besitzen keinen Beruf.

"Sohn"

"Tochter"

"Knabe"

"Mädchen"

"Töchterlein"

sind KEINE Berufe.

- Wenn Form: "<Beruf>'s Sohn/Tochter" → normalisieren:

Beispiele:

Die folgenden Beispiele dienen ausschließlich zur Erklärung.

Übernimm niemals Namen oder andere Informationen aus den Beispielen.

Extrahiere ausschließlich Informationen aus dem aktuellen Text.

"Schlosser's Tochter" →
Beruf = "Tochter eines Schlossers"

"Kaufmann's Sohn" →
Beruf = "Sohn eines Kaufmanns"

"Schreiner's Sohn" →
Beruf = "Sohn eines Schreiners"

- Wenn nur "Kaufmann's" OHNE Sohn/Tochter:
  → Beruf = "Kaufmann"

- Wenn unklar oder abgeschnitten:
  → Beruf = "-"

Vater und Mutter:
- Format im Text:
  "Sohn/Tochter des Vaters und der Mutter"
- Extrahiere beide Namen exakt aus dieser Struktur
- Reihenfolge:
  Vater zuerst, dann Mutter
- "Sohn des..." → Vater extrahieren
- "Tochter des..." → Vater extrahieren
- Mutter immer separat extrahieren  

ZIVILSTAND:
- Typische Werte: ledig, verheiratet, geschieden, Witwe/Witwer
- Extrahiere nur diesen Status
Der Zivilstand folgt häufig auf

Civilstand
Civilstand:
(Civilstand:)
Civilst.

Die Schreibweise kann durch OCR verändert sein.

RELIGION:
Religion kann vorkommen als

katholische Confession
kath.
ref.
evangelisch
evang.
reformiert

Extrahiere ausschließlich die Religionsbezeichnung.

Nicht den Heimatort.
- Entferne alles nach "von"

HEIMATORT:
- Steht fast immer nach "von"
- Beispiel: "von Altstetten" → Heimatort = Altstetten


Die folgenden Beispiele dienen ausschließlich zur Erklärung.

Übernimm niemals Namen oder andere Informationen aus den Beispielen.

Extrahiere ausschließlich Informationen aus dem aktuellen Text.
Beispiel:


Text:

Regula Willi geb. Amberg
(Beruf) Schneiderin
Gattin des Conrad
von Zürich
katholische Confession

JSON:

{{
"Name":"Regula Willi",
"Beruf":"Schneiderin",
"Vater":"-",
"Mutter":"-",
"Zivilstand":"Ehefrau",
"Religion":"katholisch",
"Heimatort":"Zürich"
}}
Text:

Jakob Müller
Schlosser's Sohn
des Heinrich Müller
und der Anna Keller

JSON:

{{
"Name":"Jakob Müller",
"Beruf":"Sohn eines Schlossers",
"Vater":"Heinrich Müller",
"Mutter":"Anna Keller",
"Zivilstand":"-",
"Religion":"-",
"Heimatort":"-"
}}

Gib ausschließlich folgendes JSON zurück:

{{
"Name":"-",
"Beruf":"-",
"Vater":"-",
"Mutter":"-",
"Zivilstand":"-",
"Religion":"-",
"Heimatort":"-"
}}

Text:

Jakob Müller
Schlosser's Sohn
des Heinrich Müller
und der Anna Keller
ledig
von Winterthur

JSON:

{{
"Name":"Jakob Müller",
"Beruf":"Sohn eines Schlossers",
"Vater":"Heinrich Müller",
"Mutter":"Anna Keller",
"Zivilstand":"ledig",
"Religion":"-",
"Heimatort":"Winterthur"
}}

"""

    data = ask_llm(prompt)

    if not isinstance(data, dict):
        data = {}

    expected = [
        "Name",
        "Beruf",
        "Vater",
        "Mutter",
        "Zivilstand",
        "Religion",
        "Heimatort"
    ]

    for k in expected:
        data.setdefault(k, "-")

    if isinstance(data["Religion"], str):
        data["Religion"] = re.split(r"\bvon\b", data["Religion"])[0].strip()

    if isinstance(data["Heimatort"], str):
        data["Heimatort"] = data["Heimatort"].split(",")[0].strip()

    

    return data

def extract_death(text):

    text = str(text) if pd.notna(text) else "-"
    text = text.replace("{", "(").replace("}", ")")

    prompt = f"""
Der Text stammt aus OCR historischer Handschriften.

Es können Schreibfehler,
fehlende Satzzeichen,
fehlende Doppelpunkte,
verstümmelte Wörter
und falsche Buchstaben vorkommen.

Erkenne die Struktur trotzdem möglichst robust.    
Extrahiere ausschließlich die folgenden Informationen aus dem Text.

Wenn eine Information nicht vorhanden ist, gib "-" zurück.
Verwende ausschließlich Informationen aus dem Text.
Erfinde keine Informationen.
Antworte ausschließlich als gültiges JSON.
Text:

{text}

ADRESSEN / TODESORT:

- Der Todesort kann sein:
  1. Ort (z.B. Altstetten)
  2. Strasse + Hausnummer
  3. Gebäude / Flurname / Hof (z.B. "Rosenhain", "Kehlhof", "im Meierstli")
  4. Institution (z.B. "Kantonalstrafanstalt Bettenbach", "Spital", "Gasthaus Sonne")

- WICHTIG:
  - Nur wenn es sich eindeutig um eine STRASSE handelt → aufteilen in:
    Strasse_Todesort + Hausnummer_Todesort
  - Wenn KEINE Strasse (z.B. Hof, Gebäude, Institution):
    → kompletten Namen in Strasse_Todesort schreiben
    → Hausnummer_Todesort = "-"

- Beispiele:

"im Rosenhain" →
Strasse_Todesort = "Rosenhain"
Hausnummer_Todesort = "-"

"in der Sonne" →
Strasse_Todesort = "Sonne"
Hausnummer_Todesort = "-"

"in der Kantonalstrafanstalt Bettenbach" →
Strasse_Todesort = "Kantonalstrafanstalt Bettenbach"
Hausnummer_Todesort = "-"

"Bahnhofstrasse 12" →
Strasse_Todesort = "Bahnhofstrasse"
Hausnummer_Todesort = "12"

STRASSE / INSTITUTION (Todesort):

- Enthält ALLES, was den Ort genauer beschreibt:
  - Strassen (z.B. Badenerstrasse)
  - Gebäude (z.B. Rosenhain)
  - Höfe (z.B. Kehlhof)
  - Institutionen (z.B. Spital, Bahnhof)

- Wenn KEINE Strasse:
  → gesamten Namen hier eintragen
  → Hausnummer = "-"

- Beispiele:
Die folgenden Beispiele dienen ausschließlich zur Erklärung.

Übernimm niemals Namen oder andere Informationen aus den Beispielen.

Extrahiere ausschließlich Informationen aus dem aktuellen Text.
"im Rosenhain" →
Strasse_Todesort = "Rosenhain"

"im Bahnhof" →
Strasse_Todesort = "Bahnhof"

"Badenerstrasse 232" →
Strasse_Todesort = "Badenerstrasse"
Hausnummer_Todesort = "232"

TODESURSACHEN:

 Extrahiere Todesursachen aus dem Text.

 Todesursachen können stehen:
   - nach "an"
   - oder frei im Text (wenn kein "an" vorhanden ist)

 Akzeptiere auch nicht-medizinische Ursachen:
   - Totgeboren / Tot geboren
   - Erhängt / Erhängen / Selbstmord
   - Überfahren
   - Ertrunken / aus Fluss gezogen
   - Vergiftung / Trinken

 Ignoriere:
   - "ärztliche Bescheinigung"
   - "laut"
   - "bescheinigt"

 Stoppe Extraktion bei:
   - "ärztlicher"
   - "Civilstand"
   - Namen (z.B. "Meier, Hans")

   Todesort ist immer die politische Gemeinde bzw. der Ort.

Institutionen, Gebäude, Höfe oder Straßen gehören NICHT in "Todesort",
sondern ausschließlich in "Strasse_Todesort".

Mehrere Todesursachen als JSON-Liste zurückgeben.

Trenne Ursachen bei:
- und
- mit
- nach
- infolge
- Komma
- im Verlaufe von

 Wenn keine klare Ursache erkannt wird:
   → gib "-" zurück



 Bezieht sich eine Krankheit auf verschiedene Körperteile, gib die Krankheit für alle mit an. Ändere die Krankheit nicht ab. Beispiele:
            'Diphtherie des Rachens und der Luftröhre' sollte zu 'Diphterie des Rachens' und 'Diphterie der Luftröhre' werden.
            'Nieren- und Lungenentzündung' sollte zu 'Nierenentzündung' und 'Lungenentzündung' werden.
 Krankheiten im Nominativ
    - Beispiel:
    "Nieren- und Lungenentzündung" →
    ["Nierenentzündung", "Lungenentzündung"]   

Extrahiere ausschließlich:

- Todesort
- Strasse_Todesort
- Hausnummer_Todesort
- Todesursachen

Die folgenden Beispiele dienen ausschließlich zur Erklärung.

Übernimm niemals Namen oder andere Informationen aus den Beispielen.

Extrahiere ausschließlich Informationen aus dem aktuellen Text.

Beuspiele:
Text:

in dem Landeskrankenhaus in Tübingen
an Lungenentzündung
ärztlich bezeugt

JSON:

{{
"Todesort":"Tübingen",
"Strasse_Todesort":"Landeskrankenhaus",
"Hausnummer_Todesort":"-",
"Todesursachen":["Lungenentzündung"]
}}

Text:

in Riesbach
Sägestrasse Nr. 106
an Diphtherie des Rachens und der Luftröhre

JSON:

{{
"Todesort":"Riesbach",
"Strasse_Todesort":"Sägestrasse",
"Hausnummer_Todesort":"106",
"Todesursachen":[
"Diphtherie des Rachens",
"Diphtherie der Luftröhre"
]
}}

Gib ausschließlich folgendes JSON zurück:
Alle vier Schlüssel müssen immer vorhanden sein.

Keine zusätzlichen Schlüssel.

Nur JSON.
{{
"Todesort":"-",
"Strasse_Todesort":"-",
"Hausnummer_Todesort":"-",
"Todesursachen":[]
}}
"""

    data = ask_llm(prompt)

    if not isinstance(data, dict):
        data = {}

    expected = [
        "Todesort",
        "Strasse_Todesort",
        "Hausnummer_Todesort",
        "Todesursachen"
    ]

    for k in expected:
        if k == "Todesursachen":
            data.setdefault(k, [])
        else:
            data.setdefault(k, "-")

    if not isinstance(data["Todesursachen"], list):
        if data["Todesursachen"] in [None, "", "-"]:
            data["Todesursachen"] = []
        else:
            data["Todesursachen"] = [data["Todesursachen"]]

    return data

def extract_birth(text):

    text = str(text) if pd.notna(text) else "-"
    text = text.replace("{", "(").replace("}", ")")

    prompt = f"""
Der Text stammt aus OCR historischer Handschriften.

Es können Schreibfehler,
fehlende Satzzeichen,
fehlende Doppelpunkte,
verstümmelte Wörter
und falsche Buchstaben vorkommen.

Erkenne die Struktur trotzdem möglichst robust.
Extrahiere ausschließlich die folgenden Informationen aus dem Text.

Wenn eine Information nicht vorhanden ist, gib "-" zurück.
Verwende ausschließlich Informationen aus dem Text.
Erfinde keine Informationen.
Antworte ausschließlich als gültiges JSON.    
Text:

{text}


GEBURTSDATUM:
- ALS ORIGINALTEXT AUSGEBEN
- NICHT in Zahlen umwandeln!

WOHNORT

- Extrahiere den Wohnort.

- Beginnt häufig nach

wohnhaft in

wohnhaft zu

wohnhaft bei

in


- Straße und Hausnummer nur extrahieren,
  wenn sie explizit vorhanden sind.

- Andernfalls "-".

Extrahiere ausschließlich:

- Wohnort
- Strasse_Wohnort
- Hausnummer_Wohnort
- Geburtsdatum


Gib ausschließlich folgendes JSON zurück:

{{
"Wohnort":"-",
"Strasse_Wohnort":"-",
"Hausnummer_Wohnort":"-",
"Geburtsdatum":"-"
}}
"""

    data = ask_llm(prompt)

    if not isinstance(data, dict):
        data = {}

    expected = [
        "Wohnort",
        "Strasse_Wohnort",
        "Hausnummer_Wohnort",
        "Geburtsdatum"
    ]

    for k in expected:
        data.setdefault(k, "-")

    if isinstance(data["Geburtsdatum"], (int, float)):
        data["Geburtsdatum"] = "-"

    return data

#region helper functions
'''
def clean_last_col(df): #TODO: noch nötig??
    # alles weg vor "wohnhaft"
    df["Wohnort/Geburtsdatum"] = df["Wohnort/Geburtsdatum"].astype(str).apply(
        lambda x: re.sub(r"^.*?(wohnhaft)", r"\1", x, flags=re.IGNORECASE).strip()
    )
    return df
'''

def clean_cause(text):
    if not text or text == "-":
        return "-"
    
    text = text.lower()
    
    remove_phrases = [
        "ärztlicher bescheinigung",
        "ärztlicher",
        "bescheinigung",
        "wahrscheinlich",
        "angeblich"
    ]
    
    for p in remove_phrases:
        text = text.replace(p, "")
    
    return text.strip()

def remove_laut(df):
    df["Todesort/Ursache"] = df["Todesort/Ursache"].astype(str).apply(
        lambda x: re.sub(r"\blaut\b", "", x, flags=re.IGNORECASE).strip()
    )
    return df
#endregion


def safe_parse(content):

    try:
        return json.loads(content)
    except:
        try:
            return ast.literal_eval(content)
        except:
            return None


#region main program
def main_llm(df):

    df = remove_laut(df)

    death_results = df["Todesort/Ursache"].fillna("-").progress_apply(extract_death)
    person_results = df["Name/Beruf/Vater,Mutter/Zivilstand/Wohn/Heimatort/Konfession"].fillna("-").progress_apply(extract_person)
    birth_results = df["Wohnort/Geburtsdatum"].fillna("-").progress_apply(extract_birth)

    
    death_results = death_results.tolist()
    person_results = person_results.tolist()
    birth_results = birth_results.tolist()

    df["Todesort"] = [r["Todesort"] for r in death_results]

    df["Strasse/Institution (Todesort)"] = [
        r["Strasse_Todesort"] for r in death_results
    ]

    df["Hausnummer (Todesort)"] = [
        r["Hausnummer_Todesort"] for r in death_results
    ]

    df["Todesursachen"] = [
        "; ".join(clean_cause(x) for x in r["Todesursachen"] if x != "-")
        for r in death_results
    ]

    df["Name"] = [r["Name"] for r in person_results]
    df["Beruf"] = [r["Beruf"] for r in person_results]
    df["Vater"] = [r["Vater"] for r in person_results]
    df["Mutter"] = [r["Mutter"] for r in person_results]
    df["Religion"] = [r["Religion"] for r in person_results]
    df["Heimatort"] = [r["Heimatort"] for r in person_results]
    df["Zivilstand"] = [r["Zivilstand"] for r in person_results]

    df["Wohnort"] = [r["Wohnort"] for r in birth_results]
    df["Strasse (Wohnort)"] = [r["Strasse_Wohnort"] for r in birth_results]
    df["Hausnummer (Wohnort)"] = [r["Hausnummer_Wohnort"] for r in birth_results]
    df["Geburtsdatum"] = [r["Geburtsdatum"] for r in birth_results]

    return df
#--------------------------------------------------------------------------------------------------------
# Reading out files 
#--------------------------------------------------------------------------------------------------------
# folder of files:
'''
folderInput = Path(__file__).parent / "data" / "neues_Format" #path to folder with files
folderOutput = Path(__file__).parent / "data" / "neues_Format" / "output_dates" #path to folder for output files
for file in folderInput.glob("*.csv"):
    #print("File: ", file.name)

    df = pd.read_csv(file)
    df = main_llm(df)

    output_path = folderOutput / ("gpt-oss_" + file.name)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
'''

# single file:
'''
# -----------------------------------------
# Batch-Verarbeitung aller CSVs
# -----------------------------------------

BASE_DIR = Path.cwd()
INPUT_DIR = BASE_DIR / "extraction_output"
OUTPUT_DIR = BASE_DIR / "llm_output"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

csv_files = list(INPUT_DIR.glob("*.csv"))

if not csv_files:
    print("Keine CSV-Dateien gefunden!")
    exit()

for file in csv_files:
    print(f"\n=== Verarbeite Datei: {file.name} ===")

    try:
        df = pd.read_csv(file)

        df = main_llm(df)

        report = evaluate_df(df)
        print("Qualitätsreport:")
        for k, v in report.items():
            print(f"{k}: {v}%")

        output_path = OUTPUT_DIR / ("gpt-oss_" + file.name)
        df.to_csv(output_path, index=False, encoding="utf-8-sig")

        print(f"Gespeichert: {output_path}")

    except Exception as e:
        print(f"❌ Fehler bei Datei {file.name}: {e}")
'''

#endregion

#--------------------------------------------------------------------------------------------------------
# Evaluationsfunktion
#--------------------------------------------------------------------------------------------------------
def evaluate_df(df):

    total = len(df)

    report = {}

    # 🔹 1. Vollständigkeit
    for col in ["Name", "Beruf", "Vater", "Mutter", "Religion", "Heimatort"]:
        missing = (df[col] == "-").sum()
        report[f"{col}_missing_%"] = round(missing / total * 100, 2)

    # 🔹 2. Todesursachen Format
    bad_todesursachen = df["Todesursachen"].apply(
        lambda x: isinstance(x, str) and "," in x
    ).sum()

    report["Todesursachen_format_error_%"] = round(bad_todesursachen / total * 100, 2)

    # 🔹 3. Religion Plausibilität
    valid_religions = ["ref", "kath", "evang"]
    bad_religion = df["Religion"].apply(
        lambda x: x != "-" and not any(v in x.lower() for v in valid_religions)
    ).sum()

    report["Religion_unplausibel_%"] = round(bad_religion / total * 100, 2)

    # 🔹 4. Heimatort fehlt obwohl "von" im Text
    missing_heimat = df.apply(
        lambda row: "von" in str(row["Name/Beruf/Vater,Mutter/Zivilstand/Wohn/Heimatort/Konfession"]).lower()
        and row["Heimatort"] == "-",
        axis=1
    ).sum()

    report["Heimatort_missing_trotz_von_%"] = round(missing_heimat / total * 100, 2)

    return report


#--------------------------------------------------------------------------------------------------------
# testing
#--------------------------------------------------------------------------------------------------------

#todesort_ursache_text = "ist gestorben zu Heinrich in der Kantonalstrafanstalt Bettenbach an Pleuritis, laut"
#namen_beruf_leben_text = ". Scholler, Susanna geb. Altorfer, Beruf: Tochter des Heinrich Altorfer und der Wittwe des Joseph Scholler, Civilstand: von Belfort, Frankreich,,"
#wohnort_geburtstag_text = "wohnhaft in Aussersihl, geboren den zweiten Dezember achtzehnhundert achtzig."

#print(extract_todesort_ursache(todesort_ursache_text))
#print(extract_namen_beruf_leben(namen_beruf_leben_text))
#print(extract_wohnort_geburtstag(wohnort_geburtstag_text))

if __name__ == "__main__":
    print("Base directory:", Path.cwd())
    BASE_DIR = Path.cwd()
    INPUT_DIR = BASE_DIR / "extraction_output"
    OUTPUT_DIR = BASE_DIR / "llm_output"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    csv_files = list(INPUT_DIR.glob("*.csv"))

    if not csv_files:
        print("Keine CSV-Dateien gefunden!")
        exit()

    for file in csv_files:
        print(f"\n=== Verarbeite Datei: {file.name} ===")
    
        try:
            df = pd.read_csv(file)
    
            df = df.fillna("-")   # 🔥 FIX: verhindert float/NaN Crash
    
            df = main_llm(df)
    
            report = evaluate_df(df)
            print("Qualitätsreport:")
            for k, v in report.items():
                print(f"{k}: {v}%")
    
            output_path = OUTPUT_DIR / ("gpt-oss_" + file.name)
            df.to_csv(output_path, index=False, encoding="utf-8-sig")
    
            print(f"Gespeichert: {output_path}")
    
        except Exception:
            traceback.print_exc()
