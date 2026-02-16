from openai import OpenAI
import json
import pandas as pd
import re
from pathlib import Path
from tqdm import tqdm

# nur für status bar
tqdm.pandas()


client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"
)

model = "gpt-oss:20b"

#region llm promts
def extract_todesort_ursache(text): 
    response = client.responses.create(
        model=model,
        instructions="""
        Du bist ein Informationsextraktionssystem und extrahierst strukturierte Daten aus Text.
        Was du extrahieren musst: Stadt, Strasse oder Instutution und Nummmer des Todesorts und eine oder mehrere Todesursachen.

        Regeln:
        1. Erfinde nichts dazu.
        2. Falls etwas nicht angegeben ist, schreibe '-'.
        3. Inkludiere so viele Informationen wie der Text hergibt.
        4. Der Ort steht vor dem Wort 'an'.
        5. Die Todesursachen sind die Gründe (oder der Grund) warum jemand gestorben ist.
        6. Gib alle Todesursachen einzeln an. Trennwörter können unter Anderem sein: 'nach', 'mit', 'infolge', 'im Verlaufe von', 'und'.
        7. Bezieht sich eine Krankheit auf verschiedene Körperteile, gib die Krankheit für alle mit an. Ändere die Krankheit nicht ab. Beispiele:
            'Diphtherie des Rachens und der Luftröhre' sollte zu 'Diphterie des Rachens' und 'Diphterie der Luftröhre' werden.
            'Nieren- und Lungenentzündung' sollte zu 'Nierenentzündung' und 'Lungenentzündung' werden.
        8. Setze alle Todesursachen in den Nominativ.
        9. Die Todesursachen stehen nach dem Wort 'an'.
        10. Kleine Rechtschreibfehler kannst du ignorieren.
        """,
        input=f"""
        Extrahiere die Informationen aus folgendem Text. 
        \"
        {text}
        \"
        """,
        text = {
            "format": {
                "type": "json_schema",
                "name": "name",
                "schema": {
                    "type": "object",
                    "properties": {
                        "Stadt": {
                            "type": "string"
                        },
                        "Strasse/Institution": {
                            "type": "string"
                        },
                        "Hausnummer": {
                            "type": "string"
                        },
                        "Todesursachen": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        }
                    },
                    "required": ["Stadt", "Strasse/Institution", "Hausnummer", "Todesursachen"],
                    "additionalProperties": False
                },
                #"strict": True
            }
        },
        store=False,
        temperature=0.0
    )
    return json.loads(response.output_text)

def extract_namen_beruf_leben(text): 
    response = client.responses.create(
        model=model,
        instructions="""
        Du bist ein Informationsextraktionssystem und extrahierst strukturierte Daten aus Text.
        Was du extrahieren musst: Name, Beruf, Vater (= Name des Vaters), Mutter (=Name der Mutter), Civilstand, Religion, Heimatort.

        Regeln:
        1. Erfinde nichts dazu.
        2. Falls etwas nicht angegeben ist, schreibe '-'.
        3. Inkludiere so viele Informationen wie der Text hergibt.
        4. Gib Namen (also 'Name', 'Vater', 'Mutter') immer in dieser Reihenfolge an: Vorname(n) Nachname. Falls nur eins von beiden angegeben ist, schreibe nur das.
        5. Beruf nur angeben, wenn er direkt nach 'Beruf:' steht, ohne etwas dazwischen.
        6. 'Sohn', 'Tochter' oder 'ein Knabe' ist kein Beruf, falls das nach 'Beruf:' stehe, schreibe '-'.
        7. Mutter und Vater stehen immer so im Text: 'Sohn/Tochter des/der Vater/Mutter und der/des Mutter/Vater'.
        8. Civilstand kann sein: ledig, ehelich, geschieden, witwe (oder ähnliche Schreibweisen).
        9. Der Heimatort steht nach 'von'.
        10. Kleine Rechtschreibfehler kannst du ignorieren.
        """,
        input=f"""
        Extrahiere die Informationen aus folgendem Text. 
        \"
        {text}
        \"
        """,
        text = {
            "format": {
                "type": "json_schema",
                "name": "name",
                "schema": {
                    "type": "object",
                    "properties": {
                        "Name": {
                            "type": "string"
                        },
                        "Beruf": {
                            "type": "string"
                        },
                        "Vater": {
                            "type": "string"
                        },
                        "Mutter": {
                            "type": "string"
                        },
                        "Civilstand": {
                            "type": "string"
                        },
                        "Religion": {
                            "type": "string"
                        },
                        "Heimatort": {
                            "type": "string"
                        }
                    },
                    "required": ["Name", "Beruf", "Vater", "Mutter", "Civilstand", "Religion", "Heimatort"],
                    "additionalProperties": False
                },
            }
        },
        store=False,
        temperature=0.0
    )
    return json.loads(response.output_text)

def extract_wohnort_geburtstag(text): 
    response = client.responses.create(
        model=model,
        instructions="""
        Du bist ein Informationsextraktionssystem und extrahierst strukturierte Daten aus Text.
        Was du extrahieren musst: Stadt, Strasse und Nummmer des Wohnorts und Geburtsdatum.

        Regeln:
        1. Erfinde nichts dazu.
        2. Falls etwas nicht angegeben ist, schreibe '-'.
        3. Inkludiere so viele Informationen wie der Text hergibt.
        4. Der Wohnort steht nach 'wohnhaft'.
        5. Das Geburtsdatum steht nach 'geboren'.
        6. Schreibe das Geburtsdatum genau so wie es im Text steht (ohne 'den'). 
        7. Kleine Rechtschreibfehler kannst du ignorieren.
        """,
        input=f"""
        Extrahiere die Informationen aus folgendem Text. 
        \"
        {text}
        \"
        """,
        text = {
            "format": {
                "type": "json_schema",
                "name": "name",
                "schema": {
                    "type": "object",
                    "properties": {
                        "Stadt": {
                            "type": "string"
                        },
                        "Strasse": {
                            "type": "string"
                        },
                        "Hausnummer": {
                            "type": "string"
                        },
                        "Geburtsdatum": {
                            "type": "string"
                        }
                    },
                    "required": ["Stadt", "Strasse", "Hausnummer", "Geburtsdatum"],
                    "additionalProperties": False
                },
            }
        },
        store=False,
        temperature=0.0
    )
    return json.loads(response.output_text)
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



#region main program
def main_llm(df):
    # call helper functions
    #df = clean_last_col(df)
    df = remove_laut(df)

    # apply llm stuff (ohne Statusbar: "apply" anstatt "progress_apply")
    todesort_ursache = df["Todesort/Ursache"].astype(str).progress_apply(extract_todesort_ursache).tolist()
    df["Todesort"] = [data["Stadt"] for data in todesort_ursache]
    df["Strasse/Institution (Todesort)"] = [data["Strasse/Institution"] for data in todesort_ursache]
    df["Hausnummer (Todesort)"] = [data["Hausnummer"] for data in todesort_ursache]
    df["Todesursachen"] = [data["Todesursachen"] for data in todesort_ursache]

    namen_beruf_leben = df["Name/Beruf/Familienverhältnis/Vater/Mutter/Zivilstand/Religion/Heimatort"].astype(str).progress_apply(extract_namen_beruf_leben).tolist()
    df["Name"] = [data["Name"] for data in namen_beruf_leben]
    df["Beruf"] = [data["Beruf"] for data in namen_beruf_leben]
    df["Vater"] = [data["Vater"] for data in namen_beruf_leben]
    df["Mutter"] = [data["Mutter"] for data in namen_beruf_leben]
    df["Zivilstand"] = [data["Civilstand"] for data in namen_beruf_leben]
    df["Religion"] = [data["Religion"] for data in namen_beruf_leben]
    df["Heimatort"] = [data["Heimatort"] for data in namen_beruf_leben]

    wohnort_geburtstag = df["Wohnort/Geburtsdatum"].astype(str).progress_apply(extract_wohnort_geburtstag).tolist()
    df["Wohnort"] = [data["Stadt"] for data in wohnort_geburtstag]
    df["Strasse (Wohnort)"] = [data["Strasse"] for data in wohnort_geburtstag]
    df["Hausnummer (Wohnort)"] = [data["Hausnummer"] for data in wohnort_geburtstag]
    df["Geburtsdatum"] = [data["Geburtsdatum"] for data in wohnort_geburtstag]

    # remove old columns
    #cols = df.columns.tolist()
    #cols.remove("Todesort/Ursache")
    #cols.remove("Name/Beruf/Familienverhältnis/Vater/Mutter/Zivilstand/Religion/Heimatort")
    #cols.remove("Wohnort/Geburtsdatum")
    #df = df[cols]

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
# testing
#--------------------------------------------------------------------------------------------------------

#todesort_ursache_text = "ist gestorben zu Heinrich in der Kantonalstrafanstalt Bettenbach an Pleuritis, laut"
#namen_beruf_leben_text = ". Scholler, Susanna geb. Altorfer, Beruf: Tochter des Heinrich Altorfer und der Wittwe des Joseph Scholler, Civilstand: von Belfort, Frankreich,,"
#wohnort_geburtstag_text = "wohnhaft in Aussersihl, geboren den zweiten Dezember achtzehnhundert achtzig."

#print(extract_todesort_ursache(todesort_ursache_text))
#print(extract_namen_beruf_leben(namen_beruf_leben_text))
#print(extract_wohnort_geburtstag(wohnort_geburtstag_text))


file = Path(__file__).parent / "data" / "neues_Format" / "1890_1892_Hottingen.csv" 
df = pd.read_csv(file) 
#df = df.loc[[1, 2]]
#df = df.loc[100:104]
df = df.sample(n=1)
df = main_llm(df) 
output_path = Path(__file__).parent / ("gpt-oss_" + file.name) 
df.to_csv(output_path, index=False, encoding="utf-8-sig") 
