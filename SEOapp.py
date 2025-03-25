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

# Vælg den korrekte sti til state-filen. På Streamlit Cloud bruges /mnt/data/state.json, ellers gemmes lokalt.
if os.path.exists("/mnt/data") and os.access("/mnt/data", os.W_OK):
    STATE_FILE = "/mnt/data/state.json"
else:
    STATE_FILE = "state.json"

def load_state():
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

def fetch_all_product_links(url):
    """
    Finder alle /products/ links på en kollektionsside, 
    men undgår duplikerede links. Ex: https://noyer.dk/collections/all
    """
    unique_links = []
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if href.startswith("/products/"):
                full = "https://noyer.dk" + href
                if full not in unique_links:
                    unique_links.append(full)
    except Exception as e:
        st.error(f"Fejl ved hentning af produktlinks: {e}")
    return unique_links

def fetch_raw_product_text(url):
    """
    Henter en produktside og forsøger at finde .product-info__description.
    Hvis den ikke findes, tager vi hele sidens tekst.
    """
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        desc_elem = soup.select_one(".product-info__description")
        if desc_elem:
            return desc_elem.get_text(separator=" ", strip=True)
        else:
            return soup.get_text(separator=" ", strip=True)
    except Exception as e:
        st.error(f"Fejl ved hentning af {url}: {e}")
        return ""

# Indlæs / initialiser app-state
load_state()

if not st.session_state.get("api_key"):
    api_input = st.text_input("Indtast OpenAI API-nøgle", type="password")
    if api_input:
        st.session_state["api_key"] = api_input
        save_state()
    else:
        st.stop()

openai.api_key = st.session_state["api_key"]

# Sidebar
st.sidebar.header("Navigation")
if st.sidebar.button("Skriv SEO-tekst"):
    st.session_state["page"] = "seo"
    save_state()

st.sidebar.markdown("---")
st.sidebar.header("Virksomhedsprofiler")

profile_names = list(st.session_state["profiles"].keys())
for name in profile_names:
    col1, col2 = st.sidebar.columns([4,1])
    with col1:
        if st.button(name, key=f"profile_btn_{name}"):
            st.session_state["current_profile"] = name
            st.session_state["page"] = "profil"
            save_state()
    with col2:
        if st.button("🗑", key=f"delete_{name}"):
            st.session_state["delete_profile"] = name
            save_state()

# Bekræftelsesprompt ved sletning
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
    st.session_state["profiles"][new_profile_name] = {
        "brand_profile": "",
        "blacklist": "",
        "produkt_info": ""
    }
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

# PROFIL-SIDE
if st.session_state["page"] == "profil":
    st.header("Redigér virksomhedsprofil")

    current_profile_name = st.text_input("Navn på virksomhedsprofil:",
                                         value=st.session_state["current_profile"])
    if current_profile_name != st.session_state["current_profile"]:
        old_name = st.session_state["current_profile"]
        if current_profile_name.strip():
            st.session_state["profiles"][current_profile_name] = st.session_state["profiles"].pop(old_name)
            st.session_state["current_profile"] = current_profile_name
            current_data = st.session_state["profiles"][current_profile_name]
            save_state()

    st.subheader("Automatisk udfyld profil (Uden produktsøgning)")
    url_profile = st.text_input("URL til en side med virksomhedens generelle info")
    if st.button("Hent og generer profil"):
        # Du kan stadig bruge AI hvis du vil – men hvis du bare vil have rå tekst, 
        # kan du gemme den direkte. Eksempel med AI:
        if url_profile:
            response = requests.get(url_profile)
            soup = BeautifulSoup(response.text, "html.parser")
            # Gem f.eks. hele brødteksten
            text = soup.get_text(separator=' ', strip=True)
            # Her kan du eventuelt kalde GPT for at skrive en profil,
            # men nu holder vi det simpelt og gemmer bare:
            st.session_state["profiles"][st.session_state["current_profile"]]["brand_profile"] = text
            save_state()
            st.text_area("Gemte profiltekst (råt)", text, height=200)
            st.success("Gemt rå tekst fra profil-URL!")
        else:
            st.warning("Indtast en URL for at generere profil")

    # Nu: Rå tekst for produkter
    st.subheader("Automatisk udfyld PRODUKTER med rå tekst")
    url_collection = st.text_input("URL til fx https://noyer.dk/collections/all")
    if st.button("Hent links"):
        if url_collection.strip():
            all_links = fetch_all_product_links(url_collection.strip())
            st.session_state["collected_links"] = all_links
            st.write(f"Fandt {len(all_links)} unikke produktlinks")
        else:
            st.warning("Indtast URL til kollektion")
    # Viser checkbokse for de links, der er fundet
    chosen_links = []
    if "collected_links" in st.session_state and st.session_state["collected_links"]:
        st.markdown("**Vælg de produkter, du vil hente tekst for**")
        for i, link in enumerate(st.session_state["collected_links"]):
            val = st.checkbox(link, key=f"link_{i}", value=True)
            if val:
                chosen_links.append(link)

        if st.button("Hent valgt produkttekst (rå)"):
            # Saml al rå tekst i en stor streng
            big_raw_text = ""
            for link in chosen_links:
                desc = fetch_raw_product_text(link)
                # Du kan tilføje en overskrift/marker, hvis du vil
                big_raw_text += f"\n\n=== PRODUKT ===\n{link}\n{desc}"

            # Gem i produkt_info
            st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"] = big_raw_text
            current_data["produkt_info"] = big_raw_text
            save_state()

            st.success("Gemte rå produkttekst i 'produkt_info'.")
            st.text_area("Rå tekst for valgte produkter", big_raw_text, height=300)

    # Manuel redigering
    st.subheader("Redigér profil manuelt")
    edited_profile = st.text_area("Virksomhedsprofil", current_data.get("brand_profile", ""), height=150)
    if st.button("Gem ændringer i profil"):
        st.session_state["profiles"][st.session_state["current_profile"]]["brand_profile"] = edited_profile
        current_data["brand_profile"] = edited_profile
        save_state()
        st.success("Profil opdateret manuelt!")

    st.subheader("Redigér produktinfo (rå tekst)")
    edited_info = st.text_area("Produktinfo (rå tekst)", current_data.get("produkt_info", ""), height=150)
    if st.button("Gem ændringer i produktinfo"):
        st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"] = edited_info
        current_data["produkt_info"] = edited_info
        save_state()
        st.success("Produktinfo opdateret manuelt!")

    # Blacklist
    st.markdown("---")
    st.subheader("Ord/sætninger AI ikke må bruge")
    edited_blacklist = st.text_area("Skriv ord/sætninger adskilt med komma:",
                                    current_data.get("blacklist", ""), height=100)
    if st.button("Gem begrænsninger"):
        st.session_state["profiles"][st.session_state["current_profile"]]["blacklist"] = edited_blacklist
        current_data["blacklist"] = edited_blacklist
        save_state()
        st.success("Begrænsninger gemt!")

    # Fil-upload
    st.markdown("---")
    st.subheader("Upload filer med produktdata (CSV, Excel, PDF)")
    prod_file = st.file_uploader("Upload", type=["csv", "xlsx", "pdf"])
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
            from PyPDF2 import PdfReader
            reader = PdfReader(prod_file)
            for page in reader.pages:
                extracted += page.extract_text()
        st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"] = extracted
        current_data["produkt_info"] = extracted
        save_state()
        st.success("Produktinformation gemt fra fil!")

# SEO-tekst side
elif st.session_state["page"] == "seo":
    st.header("Generér SEO-tekst")

    current_data = st.session_state["profiles"].get(
        st.session_state["current_profile"],
        {"brand_profile": "", "blacklist": "", "produkt_info": ""}
    )
    st.subheader("Virksomhedsprofil")
    st.markdown(current_data.get("brand_profile", "Ingen profiltekst fundet."))

    # (Her kan du stadig lave AI-baseret tekstgenerering, hvis du vil)
    # Men du har nu rå data i 'produkt_info' fremfor JSON.

    st.write("Her kunne du bruge GPT til at generere SEO-tekst, hvis du ønsker.")
