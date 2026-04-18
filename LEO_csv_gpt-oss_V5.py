from openai import OpenAI
import json
import pandas as pd
import re
from pathlib import Path
from tqdm import tqdm
import ast

# nur für status bar
tqdm.pandas()


client = OpenAI(
    base_url="https://gpustack.unibe.ch/v1-openai",
    api_key="gpustack_a0f67c08841e32f3_04262ea3cb3172504ea071b791d9ea38"
)

model = "gpt-oss-120b"

#region llm promts
def extract_all(text1, text2, text3):
    # Sicherstellen, dass die Texte Strings sind (behebt 'float' Fehler)
    text1 = str(text1) if pd.notna(text1) else "-"
    text2 = str(text2) if pd.notna(text2) else "-"
    text3 = str(text3) if pd.notna(text3) else "-"

    content = ""
    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0.0,
            messages=[
                {"role": "system", "content": "Du bist ein Informationsextraktionssystem für historische Sterberegister."},
                {"role": "user", "content": f"""
Todesort/Ursache:
{text1.replace('{', '(').replace('}', ')')}

Name/Beruf/Familie:
{text2.replace('{', '(').replace('}', ')')}

Wohnort/Geburtsdatum:
{text3.replace('{', '(').replace('}', ')')}

Extrahiere die Informationen als JSON.

WICHTIGE REGELN:

ALLGEMEIN:
- Erfinde nichts
- Wenn unbekannt → "-"
- Keine Interpretation über den Text hinaus


TODESURSACHEN:

1. Extrahiere Todesursachen aus dem Text.

2. Todesursachen können stehen:
   - nach "an"
   - oder frei im Text (wenn kein "an" vorhanden ist)

3. Akzeptiere auch nicht-medizinische Ursachen:
   - Totgeboren / Tot geboren
   - Erhängt / Erhängen / Selbstmord
   - Überfahren
   - Ertrunken / aus Fluss gezogen
   - Vergiftung / Trinken

4. Ignoriere:
   - "ärztliche Bescheinigung"
   - "laut"
   - "bescheinigt"

5. Stoppe Extraktion bei:
   - "ärztlicher"
   - "Civilstand"
   - Namen (z.B. "Meier, Hans")

6. Mehrere Ursachen → Liste

7. Trennwörter:
   - und
   - mit
   - nach
   - infolge
   - Komma

8. Wenn keine klare Ursache erkannt wird:
   → gib "-" zurück

9. Trennwörter können sein: nach, mit, infolge, im Verlaufe von, und
10. mehrere Ursachen einzeln auflisten
11. Bezieht sich eine Krankheit auf verschiedene Körperteile, gib die Krankheit für alle mit an. Ändere die Krankheit nicht ab. Beispiele:
            'Diphtherie des Rachens und der Luftröhre' sollte zu 'Diphterie des Rachens' und 'Diphterie der Luftröhre' werden.
            'Nieren- und Lungenentzündung' sollte zu 'Nierenentzündung' und 'Lungenentzündung' werden.
12. Krankheiten im Nominativ
    - Beispiel:
    "Nieren- und Lungenentzündung" →
    ["Nierenentzündung", "Lungenentzündung"]   
    

HEIMATORT:
- Steht fast immer nach "von"
- Beispiel: "von Altstetten" → Heimatort = Altstetten

RELIGION:
- NUR Religion extrahieren (z.B. "ref.", "kath.")
- NICHT den Heimatort!
- Entferne alles nach "von"

BERUF:

- Nur extrahieren wenn explizit "Beruf:" im Text steht

- KEINE Familienbezeichnungen als Beruf:
  - Sohn, Tochter, Töchterlein, Knabe, Mädchen → Beruf = "-"

- Kinder haben KEINEN Beruf 

- Wenn Form: "<Beruf>'s Sohn/Tochter" → normalisieren:

Beispiele:

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

ELTERN:
- Format im Text:
  "Sohn/Tochter des Vaters und der Mutter"
- Extrahiere beide Namen exakt aus dieser Struktur
- Reihenfolge:
  Vater zuerst, dann Mutter
- "Sohn des..." → Vater extrahieren
- "Tochter des..." → Vater extrahieren
- Mutter immer separat extrahieren  

NAME:
- Format: Vorname(n) Nachname
- Falls im Text "Nachname, Vorname" → umdrehen

ZIVILSTAND:
- Typische Werte: ledig, verheiratet, geschieden, Witwe/Witwer
- Extrahiere nur diesen Status

GEBURTSDATUM:
- ALS ORIGINALTEXT AUSGEBEN
- NICHT in Zahlen umwandeln!

ORTE:
- OCR-Fehler korrigieren wenn eindeutig:
  Allstetten → Altstetten

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

"im Rosenhain" →
Strasse_Todesort = "Rosenhain"

"im Bahnhof" →
Strasse_Todesort = "Bahnhof"

"Badenerstrasse 232" →
Strasse_Todesort = "Badenerstrasse"
Hausnummer_Todesort = "232"

FORMAT:
- Todesursachen IMMER als Liste
- KEINE zusätzlichen Texte

ANTWORT:
- Gib AUSSCHLIESSLICH gültiges JSON zurück
- KEIN Text vor oder nach dem JSON

JSON FORMAT (Gib exakt diese Struktur zurück):
{{
"Todesort": "...",
"Strasse_Todesort": "...",
"Hausnummer_Todesort": "...",
"Todesursachen": ["..."],
"Name": "...",
"Beruf": "...",
"Vater": "...",
"Mutter": "...",
"Zivilstand": "...",
"Religion": "...",
"Heimatort": "...",
"Wohnort": "...",
"Strasse_Wohnort": "...",
"Hausnummer_Wohnort": "...",
"Geburtsdatum": "..."
}}
"""}
            ]
        )


        content = response.choices[0].message.content
        content = content.replace("```json","").replace("```","").strip()

        # nur JSON extrahieren
        matches = re.findall(r"\{[\s\S]*?\}", content)
        if matches:
            content = matches[0]

        data = safe_parse(content)
        if data is None:
            raise ValueError("Parsing failed")
        # Geburtsdatum NICHT numerisch erlauben
        if isinstance(data.get("Geburtsdatum"), (int, float)):
            data["Geburtsdatum"] = "-"

        # Religion säubern
        if isinstance(data.get("Religion"), str):
            data["Religion"] = re.split(r"\bvon\b", data["Religion"])[0].strip()

        # Heimatort säubern
        if isinstance(data.get("Heimatort"), str):
            data["Heimatort"] = data["Heimatort"].split(",")[0].strip()    

        expected_keys = [
"Todesort","Strasse_Todesort","Hausnummer_Todesort","Todesursachen",
"Name","Beruf","Vater","Mutter","Zivilstand","Religion","Heimatort",
"Wohnort","Strasse_Wohnort","Hausnummer_Wohnort","Geburtsdatum"
]

        for k in expected_keys:
            if k not in data:
                data[k] = "-" if k != "Todesursachen" else []

        # sicherstellen dass Todesursachen immer Liste ist
        if not isinstance(data.get("Todesursachen"), list):
            if data.get("Todesursachen") in [None, "-", ""]:
                data["Todesursachen"] = []
            else:
                data["Todesursachen"] = [data["Todesursachen"]]

        return data

    except Exception as e:
        print("LLM Fehler:", e)
        print("RAW OUTPUT:", content)

        return {
            "Todesort": "-",
            "Strasse_Todesort": "-",
            "Hausnummer_Todesort": "-",
            "Todesursachen": [],
            "Name": "-",
            "Beruf": "-",
            "Vater": "-",
            "Mutter": "-",
            "Zivilstand": "-",
            "Religion": "-",
            "Heimatort": "-",
            "Wohnort": "-",
            "Strasse_Wohnort": "-",
            "Hausnummer_Wohnort": "-",
            "Geburtsdatum": "-"
        }
    #endregion



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

    results = df.progress_apply(
        lambda row: extract_all(
            row["Todesort/Ursache"],
            row["Name/Beruf/Vater,Mutter/Zivilstand/Wohn/Heimatort/Konfession"],
            row["Wohnort/Geburtsdatum"]
        ),
        axis=1
    )

    results = results.tolist()

    df["Todesort"] = [r["Todesort"] for r in results]
    df["Strasse/Institution (Todesort)"] = [r["Strasse_Todesort"] for r in results]
    df["Hausnummer (Todesort)"] = [r["Hausnummer_Todesort"] for r in results]
    df["Todesursachen"] = [
        "; ".join([
            clean_cause(t) for t in r["Todesursachen"] if t != "-"
        ])
        for r in results
    ] 

    df["Name"] = [r["Name"] for r in results]
    df["Beruf"] = [r["Beruf"] for r in results]
    df["Vater"] = [r["Vater"] for r in results]
    df["Mutter"] = [r["Mutter"] for r in results]
    df["Zivilstand"] = [r["Zivilstand"] for r in results]
    df["Religion"] = [r["Religion"] for r in results]
    df["Heimatort"] = [r["Heimatort"] for r in results]

    df["Wohnort"] = [r["Wohnort"] for r in results]
    df["Strasse (Wohnort)"] = [r["Strasse_Wohnort"] for r in results]
    df["Hausnummer (Wohnort)"] = [r["Hausnummer_Wohnort"] for r in results]
    df["Geburtsdatum"] = [r["Geburtsdatum"] for r in results]

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
    
        except Exception as e:
            print(f"❌ Fehler bei Datei {file.name}: {e}")
