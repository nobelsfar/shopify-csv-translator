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
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
            # Indlæs de gemte værdier i st.session_state
            for key, value in state.items():
                st.session_state[key] = value
        except Exception as e:
            st.error(f"Fejl ved indlæsning af state: {e}")
            initialize_state()
    else:
        initialize_state()

def save_state():
    # Sørg for, at mappen til state-filen findes
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
    st.session_state["profiles"] = {}
    st.session_state["api_key"] = ""
    st.session_state["page"] = "seo"
    st.session_state["generated_texts"] = []
    st.session_state["current_profile"] = "Standard profil"
    st.session_state["delete_profile"] = None
    save_state()

# Funktion til at hente og udtrække tekst fra en hjemmeside
def fetch_website_content(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        # Fjern script- og style-tags
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text(separator=' ', strip=True)
        return text
    except Exception as e:
        st.error(f"Fejl ved hentning af hjemmesideindhold: {e}")
        return None

# Indlæs eller initialiser state ved app-start
load_state()

# Hvis vi ikke har en API-nøgle endnu, beder vi brugeren om at indtaste den
if not st.session_state["api_key"]:
    api_input = st.text_input("Indtast OpenAI API-nøgle", type="password")
    if api_input:
        st.session_state["api_key"] = api_input
        save_state()
    else:
        st.stop()

# Sæt API-nøglen til openai
openai.api_key = st.session_state["api_key"]

# Sidebar navigation
st.sidebar.header("Navigation")
if st.sidebar.button("Skriv SEO-tekst"):
    st.session_state["page"] = "seo"
    save_state()

st.sidebar.markdown("---")
st.sidebar.header("Virksomhedsprofiler")

profile_names = list(st.session_state["profiles"].keys())

# Vis profiler med slet-ikon ved siden af profilnavnet
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

# Hvis der trykkes på slet-ikonet, vis en bekræftelsesboks
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

if st.sidebar.button("Opret ny profil"):
    new_profile_name = f"Ny profil {len(profile_names) + 1}"
    st.session_state["profiles"][new_profile_name] = {"brand_profile": "", "blacklist": "", "produkt_info": ""}
    st.session_state["current_profile"] = new_profile_name
    st.session_state["page"] = "profil"
    save_state()

current_data = st.session_state["profiles"].get(
    st.session_state["current_profile"],
    {"brand_profile": "", "blacklist": "", "produkt_info": ""}
)
if current_data.get("brand_profile", "").strip():
    st.sidebar.markdown(current_data["brand_profile"])
else:
    st.sidebar.info("Ingen virksomhedsprofil fundet endnu.")

# Side: Redigér virksomhedsprofil
if st.session_state["page"] == "profil":
    st.header("Redigér virksomhedsprofil")
    
    # Vælg profilnavn
    current_profile_name = st.text_input("Navn på virksomhedsprofil:",
                                           value=st.session_state["current_profile"],
                                           key="profile_name_display")
    if current_profile_name != st.session_state["current_profile"]:
        old_name = st.session_state["current_profile"]
        if current_profile_name.strip():
            st.session_state["profiles"][current_profile_name] = st.session_state["profiles"].pop(old_name)
            st.session_state["current_profile"] = current_profile_name
            current_data = st.session_state["profiles"][current_profile_name]
            save_state()
    
    # Ny sektion: Automatisk udfyld profil med hjemmesideinformation
    st.subheader("Automatisk udfyld profil")
    website_url = st.text_input("Indtast URL til din hjemmeside for automatisk profilgenerering:")
    if st.button("Hent og generer profil"):
        if website_url:
            website_text = fetch_website_content(website_url)
            if website_text:
                prompt = (
                    "Giv en detaljeret virksomhedsprofil, der beskriver virksomhedens produkter, historie og kerneværdier "
                    "baseret på følgende hjemmesideindhold:\n\n" + website_text
                )
                try:
                    response = openai.ChatCompletion.create(
                        model="gpt-4-turbo",
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=500
                    )
                    generated_profile = response.choices[0].message.content.strip()
                    st.text_area("Genereret virksomhedsprofil", generated_profile, height=200)
                    if st.button("Brug denne profil"):
                        st.session_state["profiles"][st.session_state["current_profile"]]["brand_profile"] = generated_profile
                        current_data["brand_profile"] = generated_profile
                        save_state()
                        st.success("Virksomhedsprofil opdateret med genereret tekst!")
                except Exception as e:
                    st.error(f"Fejl ved generering af virksomhedsprofil: {e}")
        else:
            st.warning("Indtast venligst en gyldig URL.")

    # Redigér profiltekst manuelt
    st.subheader("Redigér profil manuelt")
    profil_tekst = st.text_area("Redigér profil her:", current_data.get("brand_profile", ""), height=200)
    if st.button("Gem ændringer", key="save_profile"):
        st.session_state["profiles"][st.session_state["current_profile"]]["brand_profile"] = profil_tekst
        save_state()
        st.success("Profil opdateret!")
    
    st.markdown("---")
    st.subheader("Ord/sætninger AI ikke må bruge")
    blacklist = st.text_area("Skriv ord eller sætninger adskilt med komma:", current_data.get("blacklist", ""))
    if st.button("Gem begrænsninger", key="save_blacklist"):
        st.session_state["profiles"][st.session_state["current_profile"]]["blacklist"] = blacklist
        save_state()
        st.success("Begrænsninger gemt!")
    
    st.markdown("---")
    st.subheader("Upload eller indsæt produktdata")
    st.info("Upload en CSV, Excel eller PDF-fil med produktdata. Denne information gemmes under din profil.")
    produkt_data = st.file_uploader("Upload CSV, Excel eller PDF",
                                    type=["csv", "xlsx", "pdf"],
                                    key=f"produkt_upload_{st.session_state['current_profile']}")
    if produkt_data:
        st.write(f"🔄 Fil uploadet: {produkt_data.name}")
        extracted = ""
        if produkt_data.name.endswith(".csv"):
            df = pd.read_csv(produkt_data)
            extracted = df.to_string(index=False)
        elif produkt_data.name.endswith(".xlsx"):
            df = pd.read_excel(produkt_data)
            extracted = df.to_string(index=False)
        elif produkt_data.name.endswith(".pdf"):
            reader = PyPDF2.PdfReader(produkt_data)
            for page in reader.pages:
                extracted += page.extract_text()
        st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"] = extracted
        current_data["produkt_info"] = extracted
        save_state()
        st.success("Produktinformation gemt!")
    
    produkt_info_manual = st.text_area("Eller indsæt produktdata manuelt:", current_data.get("produkt_info", ""), height=150)
    if st.button("Gem produktdata", key="save_product_info"):
        st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"] = produkt_info_manual
        current_data["produkt_info"] = produkt_info_manual
        save_state()
        st.success("Produktdata opdateret!")

# Side: Generér SEO-tekst
if st.session_state["page"] == "seo":
    st.header("Generér SEO-tekst")
    
    st.subheader("Virksomhedsprofil")
    st.markdown(current_data.get("brand_profile", "Ingen profiltekst fundet."))
    
    # Inputfelter for SEO-parametre
    seo_keyword = st.text_input("Søgeord / Emne", value="")
    laengde = st.number_input("Ønsket tekstlængde (antal ord)", min_value=50, max_value=2000, value=300, step=50)
    tone = st.selectbox("Vælg tone-of-voice",
                        options=["Neutral", "Formel", "Venlig", "Entusiastisk"],
                        index=0)
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
            # Gem de genererede tekster, så de bevares mellem genindlæsninger
            save_state()
            
            if st.session_state["generated_texts"]:
                st.subheader("Dine genererede SEO-tekster")
                for idx, txt in enumerate(st.session_state["generated_texts"]):
                    with st.expander(f"SEO-tekst {idx+1}"):
                        st.markdown(txt, unsafe_allow_html=True)
                        st.download_button(f"Download tekst {idx+1}",
                                           txt,
                                           file_name=f"seo_tekst_{idx+1}.txt")
                        if st.button(f"❌ Slet tekst {idx+1}", key=f"delete_text_{idx}"):
                            st.session_state["generated_texts"].pop(idx)
                            save_state()
