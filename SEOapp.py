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
    Henter rå tekst fra en URL og fjerner script/style.
    Bruges til AI-generering af brandprofil.
    """
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text(separator=' ', strip=True)
        return text
    except Exception as e:
        st.error(f"Fejl ved hentning af hjemmesideindhold: {e}")
        return ""

def fetch_product_links(url):
    """
    Finder alle /products/ links på en kollektionsside, 
    men undgår duplikerede links.
    """
    links = []
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if href.startswith("/products/"):
                full = "https://noyer.dk" + href
                if full not in links:
                    links.append(full)
    except Exception as e:
        st.error(f"Fejl ved hentning af produktlinks: {e}")
    return links

def fetch_product_text_raw(url):
    """
    Henter en produktside og tager enten .product-info__description
    eller hele siden som fallback. Returnerer rå tekst.
    """
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        desc = soup.select_one(".product-info__description")
        if desc:
            return desc.get_text(separator=' ', strip=True)
        else:
            return soup.get_text(separator=' ', strip=True)
    except Exception as e:
        st.error(f"Fejl ved hentning af {url}: {e}")
        return ""

# -- Indlæs / initialiser state
load_state()

if not st.session_state.get("api_key"):
    user_key = st.text_input("Indtast OpenAI API-nøgle", type="password")
    if user_key:
        st.session_state["api_key"] = user_key
        save_state()
    else:
        st.stop()

openai.api_key = st.session_state["api_key"]

# -- Sidebar
st.sidebar.header("Navigation")
if st.sidebar.button("Skriv SEO-tekst"):
    st.session_state["page"] = "seo"
    save_state()

st.sidebar.markdown("---")
st.sidebar.header("Virksomhedsprofiler")

profile_names = list(st.session_state["profiles"].keys())
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

# Bekræftelsesprompt ved sletning
if st.session_state.get("delete_profile"):
    profile_to_delete = st.session_state["delete_profile"]
    st.sidebar.warning(f"Er du sikker på, at du vil slette profilen '{profile_to_delete}'?")
    c_ok, c_cancel = st.sidebar.columns(2)
    with c_ok:
        if st.button("Ja, slet"):
            st.session_state["profiles"].pop(profile_to_delete, None)
            if st.session_state["current_profile"] == profile_to_delete:
                st.session_state["current_profile"] = "Standard profil"
            st.session_state["delete_profile"] = None
            save_state()
    with c_cancel:
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

# == Profil-side
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

    # -- AI-baseret generering af brand-profil, UDEN "bæredygtighed"
    st.subheader("AI-genereret virksomhedsprofil (uden 'bæredygtighed')")
    url_profile = st.text_input("URL til fx 'Om os' side")
    if st.button("Hent og lav brandprofil med AI"):
        if url_profile:
            raw_txt = fetch_website_content(url_profile)
            if raw_txt:
                prompt = (
                    "Læs hjemmesideteksten herunder og skriv en fyldig virksomhedsprofil. "
                    "Inkluder historie, kerneværdier og vigtigste fokusområder. "
                    "Du må IKKE nævne ord som 'bæredygtighed' eller 'bæredygtig'. "
                    "Returnér KUN profilteksten.\n\n"
                    f"{raw_txt[:7000]}"
                )
                try:
                    resp = openai.ChatCompletion.create(
                        model="gpt-4-turbo",
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=1000
                    )
                    brand = resp.choices[0].message.content.strip()

                    st.session_state["profiles"][st.session_state["current_profile"]]["brand_profile"] = brand
                    current_data["brand_profile"] = brand
                    save_state()

                    st.success("Virksomhedsprofil opdateret (uden bæredygtighed)!")
                    st.text_area("Genereret profil", brand, height=200)
                except Exception as e:
                    st.error(f"Fejl ved AI: {e}")
            else:
                st.warning("Tom tekst fundet på URL.")
        else:
            st.warning("Indtast en URL.")

    # -- Rå produkttekster
    st.subheader("Hent rå produkttekster (uden AI)")
    col_url = st.text_input("URL til en kollektion, f.eks. https://noyer.dk/collections/all")
    if st.button("Hent produktlinks"):
        if col_url.strip():
            found_links = fetch_product_links(col_url.strip())
            st.session_state["collected_links"] = found_links
            st.write(f"Fandt {len(found_links)} unikke links.")
        else:
            st.warning("Angiv URL.")

    chosen_links = []
    if "collected_links" in st.session_state and st.session_state["collected_links"]:
        st.markdown("**Vælg de produkter, du vil hente tekst fra**")
        for i, link in enumerate(st.session_state["collected_links"]):
            val = st.checkbox(link, key=f"prod_cb_{i}", value=True)
            if val:
                chosen_links.append(link)

        if st.button("Hent tekst fra valgte produkter"):
            big_raw = ""
            for link in chosen_links:
                txt = fetch_product_text_raw(link)
                big_raw += f"\n\n=== PRODUKT ===\n{link}\n{txt}"
            st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"] = big_raw
            current_data["produkt_info"] = big_raw
            save_state()

            st.success("Rå tekst er gemt i produkt_info.")
            st.text_area("Rå tekst", big_raw, height=300)

    # Manuelle felter
    st.subheader("Redigér profil manuelt")
    brand_txt = st.text_area("Virksomhedsprofil:", current_data.get("brand_profile", ""), height=150)
    if st.button("Gem ændringer i profil"):
        st.session_state["profiles"][st.session_state["current_profile"]]["brand_profile"] = brand_txt
        current_data["brand_profile"] = brand_txt
        save_state()
        st.success("Profil opdateret manuelt.")

    st.subheader("Redigér produktinfo (rå tekst)")
    prod_txt = st.text_area("Produktinfo (rå):", current_data.get("produkt_info", ""), height=150)
    if st.button("Gem ændringer i produktinfo"):
        st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"] = prod_txt
        current_data["produkt_info"] = prod_txt
        save_state()
        st.success("Produktinfo opdateret manuelt.")

    st.subheader("Ord/sætninger AI ikke må bruge (Blacklist)")
    bl = st.text_area("Bruges ved SEO-generering, ikke ved rå hentning", current_data.get("blacklist", ""), height=80)
    if st.button("Gem blacklist"):
        st.session_state["profiles"][st.session_state["current_profile"]]["blacklist"] = bl
        current_data["blacklist"] = bl
        save_state()
        st.success("Blacklist gemt.")

    # Upload filer
    st.markdown("---")
    st.subheader("Upload filer med produktdata (CSV, XLSX, PDF)")
    up_file = st.file_uploader("Upload", type=["csv","xlsx","pdf"])
    if up_file:
        st.write(f"🔄 Fil uploadet: {up_file.name}")
        ext = ""
        if up_file.name.endswith(".csv"):
            df = pd.read_csv(up_file)
            ext = df.to_string(index=False)
        elif up_file.name.endswith(".xlsx"):
            df = pd.read_excel(up_file)
            ext = df.to_string(index=False)
        elif up_file.name.endswith(".pdf"):
            from PyPDF2 import PdfReader
            reader = PdfReader(up_file)
            for page in reader.pages:
                ext += page.extract_text()
        st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"] = ext
        current_data["produkt_info"] = ext
        save_state()
        st.success("Produktdata gemt fra fil!")

# -- SEO-side
elif st.session_state["page"] == "seo":
    st.header("Generér SEO-tekst")

    data = st.session_state["profiles"].get(
        st.session_state["current_profile"],
        {"brand_profile": "", "blacklist": "", "produkt_info": ""}
    )
    st.subheader("Virksomhedsprofil")
    st.markdown(data.get("brand_profile", "Ingen profiltekst."))

    seo_keyword = st.text_input("Søgeord / emne")
    laengde = st.number_input("Antal ord (længde)", min_value=50, max_value=2000, value=300, step=50)
    tone = st.selectbox("Tone-of-voice", ["Neutral","Formel","Venlig","Entusiastisk"], index=0)
    antal = st.selectbox("Antal tekster", list(range(1,11)), 0)

    if seo_keyword:
        if st.button("Generér SEO-tekst"):
            with st.spinner("Genererer SEO-tekst..."):
                for i in range(antal):
                    # Hardcode constraints:
                    # 1) Ingen "bæredygtighed"
                    # 2) Normal dansk overskrift (ikke Title Case)
                    # 3) Inkluder brand_profil + produkt_info
                    # 4) Overhold blacklist
                    prompt = (
                        f"Skriv en SEO-optimeret tekst på dansk om '{seo_keyword}'. "
                        "Skriv overskrifter på normal dansk (ikke Title Case). "
                        "Du må ikke nævne 'bæredygtighed' eller 'bæredygtig'. "
                        f"Brug følgende virksomhedsprofil: {data.get('brand_profile','')}. "
                        f"Brug også følgende rå produktinfo: {data.get('produkt_info','')}. "
                        f"Inkluder en meta-titel, meta-beskrivelse og relevante nøgleord i overskrifter. "
                        f"Teksten skal være ca. {laengde} ord."
                    )
                    if tone:
                        prompt += f" Teksten skal have en '{tone}' tone-of-voice."
                    if data.get("blacklist","").strip():
                        prompt += f" Undgå desuden disse ord: {data['blacklist']}."

                    try:
                        resp = openai.ChatCompletion.create(
                            model="gpt-4-turbo",
                            messages=[{"role":"user","content":prompt}],
                            max_tokens=laengde*2
                        )
                        seo_text = resp.choices[0].message.content.strip()
                        st.session_state["generated_texts"].append(seo_text)
                    except Exception as e:
                        st.error(f"Fejl: {e}")
            save_state()

            if st.session_state["generated_texts"]:
                st.subheader("Dine SEO-tekster")
                for idx, txt in enumerate(st.session_state["generated_texts"]):
                    with st.expander(f"SEO-tekst {idx+1}"):
                        st.markdown(txt, unsafe_allow_html=True)
                        # Download as HTML
                        st.download_button(
                            label=f"Download SEO-tekst {idx+1} som HTML",
                            data=txt,
                            file_name=f"seo_text_{idx+1}.html",
                            mime="text/html"
                        )
                        if st.button(f"Slet tekst {idx+1}", key=f"del_{idx}"):
                            st.session_state["generated_texts"].pop(idx)
                            save_state()
                            st.experimental_rerun()
