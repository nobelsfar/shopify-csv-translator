import streamlit as st
st.set_page_config(page_title="AI-assisteret SEO generator", layout="wide")

import os
import openai
import pandas as pd
import PyPDF2
import io
import json
import requests
from bs4 import BeautifulSoup

# Vælg den korrekte sti til state-filen. På Streamlit Cloud bruges /mnt/data, ellers gemmes der lokalt.
if os.path.exists("/mnt/data") and os.access("/mnt/data", os.W_OK):
    STATE_FILE = "/mnt/data/state.json"
else:
    STATE_FILE = "state.json"

def load_state():
    """Loader session_state fra STATE_FILE, hvis den findes."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
            for key, value in state.items():
                st.session_state[key] = value
        except Exception as e:
            st.error(f"Fejl ved indlæsning af state: {e}")
            initialize_state()
    else:
        initialize_state()

def save_state():
    """Gemmer session_state til STATE_FILE."""
    folder = os.path.dirname(STATE_FILE)
    if folder and not os.path.exists(folder):
        try:
            os.makedirs(folder, exist_ok=True)
        except Exception as e:
            st.error(f"Fejl ved oprettelse af mappe til state: {e}")
    state = {
        "profiles": st.session_state.get("profiles", {}),
        "api_key": st.session_state.get("api_key", ""),
        "page": st.session_state.get("page", "seo"),
        "generated_texts": st.session_state.get("generated_texts", []),
        "current_profile": st.session_state.get("current_profile", "Standard profil"),
        "delete_profile": st.session_state.get("delete_profile", None)
    }
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception as e:
        st.error(f"Fejl ved gemning af state: {e}")

def initialize_state():
    """Initialiserer session_state med standardværdier."""
    st.session_state["profiles"] = {}
    st.session_state["api_key"] = ""
    st.session_state["page"] = "seo"
    st.session_state["generated_texts"] = []
    st.session_state["current_profile"] = "Standard profil"
    st.session_state["delete_profile"] = None
    save_state()

def fetch_website_content(url):
    """
    Henter tekstindhold fra en given URL, fjerner script- og style-tags
    og returnerer rå tekst.
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style"]):
            script.decompose()
        return soup.get_text(separator=' ', strip=True)
    except Exception as e:
        st.error(f"Fejl ved hentning af hjemmesideindhold: {e}")
        return ""

# 1) Indlæs / initialiser state
load_state()

# 2) Hvis vi ingen API-nøgle har, beder vi brugeren om at indtaste den
if not st.session_state.get("api_key"):
    api_input = st.text_input("Indtast OpenAI API-nøgle", type="password")
    if api_input:
        st.session_state["api_key"] = api_input
        save_state()
    else:
        st.stop()

# 3) Sæt OpenAI API-nøgle
openai.api_key = st.session_state["api_key"]

# 4) Sidebar Navigation
st.sidebar.header("Navigation")
if st.sidebar.button("Skriv SEO-tekst"):
    st.session_state["page"] = "seo"
    save_state()

st.sidebar.markdown("---")
st.sidebar.header("Virksomhedsprofiler")

profile_names = list(st.session_state["profiles"].keys())

# Viser profiler i sidebaren og slet-knap
for name in profile_names:
    col1, col2 = st.sidebar.columns([4, 1])
    with col1:
        if st.button(name, key=f"profile_btn_{name}"):
            st.session_state["current_profile"] = name
            st.session_state["page"] = "profil"
            save_state()
    with col2:
        if st.button("🗑", key=f"delete_{name}"):
            st.session_state["delete_profile"] = name
            save_state()

# Bekræftelsesprompt ved sletning af en profil
if st.session_state.get("delete_profile"):
    profile_to_delete = st.session_state["delete_profile"]
    st.sidebar.warning(f"Er du sikker på, at du vil slette profilen '{profile_to_delete}'?")
    col_confirm, col_cancel = st.sidebar.columns(2)
    with col_confirm:
        if st.button("Ja, slet"):
            st.session_state["profiles"].pop(profile_to_delete, None)
            if st.session_state["current_profile"] == profile_to_delete:
                st.session_state["current_profile"] = "Standard profil"
            st.session_state["delete_profile"] = None
            save_state()
    with col_cancel:
        if st.button("Nej, annuller"):
            st.session_state["delete_profile"] = None
            save_state()

# Mulighed for at oprette ny profil
if st.sidebar.button("Opret ny profil"):
    new_profile_name = f"Ny profil {len(profile_names) + 1}"
    st.session_state["profiles"][new_profile_name] = {
        "brand_profile": "",
        "blacklist": "",
        "produkt_info": ""
    }
    st.session_state["current_profile"] = new_profile_name
    st.session_state["page"] = "profil"
    save_state()

# Hent data for den nuværende profil
current_data = st.session_state["profiles"].get(
    st.session_state["current_profile"],
    {"brand_profile": "", "blacklist": "", "produkt_info": ""}
)
# Viser brand_profile i sidebaren, hvis der findes en
if current_data.get("brand_profile", "").strip():
    st.sidebar.markdown(current_data["brand_profile"])
else:
    st.sidebar.info("Ingen virksomhedsprofil fundet endnu.")

# 5) Redigér profil-side
if st.session_state["page"] == "profil":
    st.header("Redigér virksomhedsprofil")

    # Skift profilnavn
    current_profile_name = st.text_input(
        "Navn på virksomhedsprofil:",
        value=st.session_state["current_profile"],
        key="profile_name_display"
    )
    if current_profile_name != st.session_state["current_profile"]:
        old_name = st.session_state["current_profile"]
        if current_profile_name.strip():
            st.session_state["profiles"][current_profile_name] = st.session_state["profiles"].pop(old_name)
            st.session_state["current_profile"] = current_profile_name
            current_data = st.session_state["profiles"][current_profile_name]
            save_state()

    # A) AUTOMATISK UDFYLD PROFIL (uden produktsøgning)
    st.subheader("Automatisk udfyld profil (Uden produktsøgning)")
    website_url = st.text_input("URL til en side med virksomhedens generelle info (f.eks. 'Om os')")
    if st.button("Hent og generer profil"):
        if website_url:
            raw_text = fetch_website_content(website_url)
            if raw_text:
                prompt = (
                    "Læs hjemmesideteksten herunder og skriv en fyldig virksomhedsprofil. "
                    "Inkluder historie, kerneværdier og vigtigste fokusområder. Returnér KUN profilteksten:\n\n"
                    f"{raw_text[:7000]}"
                )
                try:
                    response = openai.ChatCompletion.create(
                        model="gpt-4-turbo",
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=1000
                    )
                    profile_text = response.choices[0].message.content.strip()
                    
                    st.session_state["profiles"][st.session_state["current_profile"]]["brand_profile"] = profile_text
                    current_data["brand_profile"] = profile_text
                    save_state()
                    
                    st.success("Virksomhedsprofil gemt!")
                    st.text_area("Genereret virksomhedsprofil", profile_text, height=200)
                except Exception as e:
                    st.error(f"Fejl ved generering af virksomhedsprofil: {e}")
        else:
            st.warning("Indtast venligst en URL med virksomhedens info.")

    # B) AUTOMATISK UDFYLD PRODUKTER (gemmes i produkt_info)
    st.subheader("Automatisk udfyld PRODUKTER (lægger data i produkt_info)")
    product_url = st.text_input("URL til en side, hvor produkterne er listet (med detaljer).")
    if st.button("Hent og generer produkter"):
        if product_url:
            raw_text = fetch_website_content(product_url)
            if raw_text:
                # Fjernet 'pris' i prompten
                prompt = (
                    "Analysér teksten herunder og returnér KUN en JSON-liste med 'produkter'. "
                    "Hver liste-post skal indeholde mindst: navn, kort beskrivelse, materialer (hvis muligt). "
                    "Returnér kun valid JSON. Ingen ekstra tekst.\n\n"
                    f"{raw_text[:7000]}"
                )
                try:
                    response = openai.ChatCompletion.create(
                        model="gpt-4-turbo",
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=2000
                    )
                    raw_response = response.choices[0].message.content.strip()
                    
                    # Parse JSON-svaret
                    try:
                        product_list = json.loads(raw_response)
                        product_str = json.dumps(product_list, ensure_ascii=False, indent=2)
                        
                        st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"] = product_str
                        current_data["produkt_info"] = product_str
                        save_state()
                        
                        st.success("Gemte produktlisten i 'produkt_info'!")
                        st.text_area("Produkter (JSON fra AI)", product_str, height=250)
                    except Exception as parse_err:
                        st.error("Kunne ikke parse JSON-svaret. Her er AI-svaret:")
                        st.text_area("AI-svar", raw_response, height=300)
                except Exception as e:
                    st.error(f"Fejl ved generering af produktliste: {e}")
        else:
            st.warning("Indtast venligst en URL med produkterne.")

    # C) Redigér profil manuelt
    st.subheader("Redigér profil manuelt")
    edited_profile = st.text_area("Virksomhedsprofil", current_data.get("brand_profile", ""), height=200)
    if st.button("Gem ændringer i profil"):
        st.session_state["profiles"][st.session_state["current_profile"]]["brand_profile"] = edited_profile
        current_data["brand_profile"] = edited_profile
        save_state()
        st.success("Profil opdateret manuelt!")

    # D) Redigér produktinfo manuelt
    st.subheader("Produktinfo (manuelt)")
    edited_products = st.text_area("Redigér produktinfo (JSON eller tekst)", current_data.get("produkt_info", ""), height=200)
    if st.button("Gem ændringer i produktinfo"):
        st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"] = edited_products
        current_data["produkt_info"] = edited_products
        save_state()
        st.success("Produktdata opdateret manuelt!")

    # E) Blacklist
    st.markdown("---")
    st.subheader("Ord/sætninger AI ikke må bruge")
    edited_blacklist = st.text_area(
        "Skriv ord eller sætninger adskilt med komma:",
        current_data.get("blacklist", "")
    )
    if st.button("Gem begrænsninger"):
        st.session_state["profiles"][st.session_state["current_profile"]]["blacklist"] = edited_blacklist
        current_data["blacklist"] = edited_blacklist
        save_state()
        st.success("Begrænsninger gemt!")

    # F) Upload filer med produktdata
    st.markdown("---")
    st.subheader("Upload filer med produktdata")
    prod_file = st.file_uploader("CSV, Excel eller PDF", type=["csv", "xlsx", "pdf"])
    if prod_file:
        st.write(f"🔄 Fil uploadet: {prod_file.name}")
        extracted = ""
        if prod_file.name.endswith(".csv"):
            df = pd.read_csv(prod_file)
            extracted = df.to_string(index=False)
        elif prod_file.name.endswith(".xlsx"):
            df = pd.read_excel(prod_file)
            extracted = df.to_string(index=False)
        elif prod_file.name.endswith(".pdf"):
            reader = PyPDF2.PdfReader(prod_file)
            for page in reader.pages:
                extracted += page.extract_text()
        st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"] = extracted
        current_data["produkt_info"] = extracted
        save_state()
        st.success("Produktinformation gemt fra fil!")

# 6) SEO-tekst side
elif st.session_state["page"] == "seo":
    st.header("Generér SEO-tekst")
    
    # Hent data for profilen
    current_data = st.session_state["profiles"].get(
        st.session_state["current_profile"],
        {"brand_profile": "", "blacklist": "", "produkt_info": ""}
    )

    st.subheader("Virksomhedsprofil")
    st.markdown(current_data.get("brand_profile", "Ingen profiltekst fundet."))

    # SEO-parametre
    seo_keyword = st.text_input("Søgeord / Emne", value="")
    laengde = st.number_input("Ønsket tekstlængde (antal ord)", min_value=50, max_value=2000, value=300, step=50)
    tone = st.selectbox(
        "Vælg tone-of-voice",
        options=["Neutral", "Formel", "Venlig", "Entusiastisk"],
        index=0
    )
    antal = st.selectbox("Antal tekster", options=list(range(1, 11)), index=0)
    
    if seo_keyword:
        generate = st.button("Generér SEO-tekst")
        if generate:
            with st.spinner("Genererer SEO-tekst..."):
                for i in range(antal):
                    seo_prompt = (
                        f"Skriv en SEO-optimeret tekst på dansk om '{seo_keyword}'. "
                        f"Brug følgende virksomhedsprofil som reference: {current_data.get('brand_profile', '')}. "
                        f"Brug også følgende produktinformation: {current_data.get('produkt_info', '')}. "
                        f"Strukturer teksten med klare overskrifter (fx en stor overskrift til titlen, mellemoverskrifter til afsnit og underoverskrifter til detaljer). "
                        f"Inkluder en meta-titel, en meta-beskrivelse, relevante nøgleord og foreslå interne links, hvor det er muligt. "
                        f"Teksten skal være cirka {laengde} ord lang."
                    )
                    if tone:
                        seo_prompt += f" Teksten skal have en '{tone}' tone-of-voice."
                    if current_data.get("blacklist", "").strip():
                        seo_prompt += f" Undgå følgende ord eller sætninger: {current_data['blacklist']}."
                    
                    try:
                        seo_response = openai.ChatCompletion.create(
                            model="gpt-4-turbo",
                            messages=[{"role": "user", "content": seo_prompt}],
                            max_tokens=laengde * 2
                        )
                        seo_text = seo_response.choices[0].message.content.strip()
                        st.session_state["generated_texts"].append(seo_text)
                    except Exception as e:
                        st.error(f"Fejl ved generering af tekst: {e}")
            # Gem de genererede tekster
            save_state()
            
            # Vis de genererede tekster
            if st.session_state["generated_texts"]:
                st.subheader("Dine genererede SEO-tekster")
                for idx, txt in enumerate(st.session_state["generated_texts"]):
                    with st.expander(f"SEO-tekst {idx+1}"):
                        st.markdown(txt, unsafe_allow_html=True)
                        st.download_button(
                            f"Download tekst {idx+1}",
                            txt,
                            file_name=f"seo_tekst_{idx+1}.txt"
                        )
                        if st.button(f"❌ Slet tekst {idx+1}", key=f"delete_text_{idx}"):
                            st.session_state["generated_texts"].pop(idx)
                            save_state()
                            st.experimental_rerun()
