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
- Nur medizinische Ursachen extrahieren
- KEINE Orte, Institutionen oder Zusatztexte als Todesursache
- IGNORIERE:
  - "ärztliche Bescheinigung"
  - "laut"
  - "bescheinigt"
- Mehrere Ursachen → Liste
- Todesursachen stehen IMMER nach dem Wort "an"
- Ignoriere alles vor "an"
- Trennwörter: nach, mit, infolge, im Verlaufe von, und
- mehrere Ursachen einzeln auflisten
- Bezieht sich eine Krankheit auf verschiedene Körperteile, gib die Krankheit für alle mit an. Ändere die Krankheit nicht ab. Beispiele:
            'Diphtherie des Rachens und der Luftröhre' sollte zu 'Diphterie des Rachens' und 'Diphterie der Luftröhre' werden.
            'Nieren- und Lungenentzündung' sollte zu 'Nierenentzündung' und 'Lungenentzündung' werden.
- Krankheiten im Nominativ
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
- Nur wenn explizit nach "Beruf:" angegeben
- KEINE Familienbezeichnungen wie Sohn, Tochter
- Falls dort "Sohn", "Tochter", "Knabe" steht → "-"
- Beispiel:
  "Schlosser's Tochter" → Beruf = "Tochter eines Schlossers"

ELTERN:
- Format im Text:
  "Sohn/Tochter des Vaters und der Mutter"
- Extrahiere beide Namen exakt aus dieser Struktur
- Reihenfolge:
  Vater zuerst, dann Mutter

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

ADRESSEN:
- Strasse und Hausnummer getrennt extrahieren wenn vorhanden

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
    "; ".join([t for t in r["Todesursachen"] if t != "-"])
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
file = Path(__file__).parent / "1890_1892_Hottingen_28-46.csv" #path to file
folderOutput = Path(__file__).parent / "data" / "neues_Format" / "output_llm" #path to folder for output files
df = pd.read_csv(file) #read the csv file
df = main_llm(df) 
output_path = folderOutput / ("gpt-oss_" + file.name) #path + name for output file
df.to_csv(output_path, index=False, encoding="utf-8-sig") #save
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


file = Path(__file__).parent / "Qwent" / "1886_1899_Altstetten_qwen_extraktion_strukturiert.csv"
df = pd.read_csv(file) 
#df = df.loc[[1, 2]]
#df = df.loc[100:104]
#df = df.sample(n=1)
df = main_llm(df) 
report = evaluate_df(df)
for k, v in report.items():
    print(f"{k}: {v}%")
output_path = Path(__file__).parent / ("gpt-oss_" + file.name) 
df.to_csv(output_path, index=False, encoding="utf-8-sig") 
