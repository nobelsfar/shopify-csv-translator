import streamlit as st

# VIGTIGT: set_page_config skal være ALLERFØRSTE Streamlit-kald
st.set_page_config(page_title="AI-assisteret SEO generator", layout="wide")

import os
import openai
import pandas as pd
import PyPDF2
import io
import json
import requests
import re
from bs4 import BeautifulSoup

# Vælg korrekt state-fil (Streamlit Cloud vs lokalt)
if os.path.exists("/mnt/data") and os.access("/mnt/data", os.W_OK):
    STATE_FILE = "/mnt/data/state.json"
else:
    STATE_FILE = "state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
            for k,v in state.items():
                st.session_state[k] = v
        except:
            initialize_state()
    else:
        initialize_state()

def save_state():
    folder = os.path.dirname(STATE_FILE)
    if folder and not os.path.exists(folder):
        try:
            os.makedirs(folder, exist_ok=True)
        except:
            st.error("Fejl ved oprettelse af mappe til state")
    data_to_save = {
        "profiles": st.session_state.get("profiles", {}),
        "api_key": st.session_state.get("api_key", ""),
        "page": st.session_state.get("page", "seo"),
        "generated_texts": st.session_state.get("generated_texts", []),
        "current_profile": st.session_state.get("current_profile", "Standard profil"),
        "delete_profile": st.session_state.get("delete_profile", None)
    }
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(data_to_save, f)
    except:
        st.error("Fejl ved gemning af state.")

def initialize_state():
    st.session_state["profiles"] = {}
    st.session_state["api_key"] = ""
    st.session_state["page"] = "seo"
    st.session_state["generated_texts"] = []
    st.session_state["current_profile"] = "Standard profil"
    st.session_state["delete_profile"] = None
    save_state()

# Kør load_state direkte
load_state()

# Hvis ingen API-nøgle, bed bruger om det
if not st.session_state.get("api_key"):
    in_key = st.text_input("Indtast OpenAI API-nøgle", type="password")
    if in_key:
        st.session_state["api_key"] = in_key
        save_state()
    else:
        st.stop()

import openai
openai.api_key = st.session_state["api_key"]

def fetch_website_content(url):
    """Henter rå tekst fra en URL og fjerner script/style."""
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for script in soup(["script","style"]):
            script.decompose()
        return soup.get_text(separator=' ', strip=True)
    except Exception as e:
        st.error(f"Fejl ved hentning af hjemmesideindhold: {e}")
        return ""

def fetch_product_links(url):
    """Finder /products/ links på en kollektionsside, uden dubletter."""
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

def automatically_enrich_product_text(raw_text):
    """
    Kalder GPT for at strukturere og let udvide produktteksten 
    UDEN separate knapper. Fjerner 'Produktbeskrivelse for', 
    erstatter ### med fed, men TIL SIDST fjerner vi al '**'.
    """
    if not raw_text.strip():
        return ""
    prompt=(
        "Du får her en rå produkttekst. Strukturer og berig den let (tilføj evt. manglende data), "
        "men undgå store markdown-overskrifter (###). Du må ikke skrive 'Produktbeskrivelse for'. "
        "Undgå at ændre for meget i ordlyden.\n\n"
        f"{raw_text[:15000]}"
    )
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[{"role":"user","content":prompt}],
            max_tokens=3000
        )
        enriched = resp.choices[0].message.content.strip()
        # Fjern "Produktbeskrivelse for " (hvis GPT alligevel sætter det)
        enriched = enriched.replace("Produktbeskrivelse for ","")
        # Erstat ### ... -> **...** (så GPT's overskrifter bliver fed)
        enriched = re.sub(r'^###\s+(.*)$', r'**\1**', enriched, flags=re.MULTILINE)
        # Nu FJERNER vi alle ** helt, som du bad om:
        enriched = enriched.replace("**", "")
        return enriched
    except Exception as e:
        st.error(f"Fejl ved berigelse: {e}")
        return raw_text  # fallback

st.sidebar.header("Navigation")
if st.sidebar.button("Skriv SEO-tekst"):
    st.session_state["page"] = "seo"
    save_state()

st.sidebar.markdown("---")
st.sidebar.header("Virksomhedsprofiler")

pnames = list(st.session_state["profiles"].keys())
for nm in pnames:
    col1, col2 = st.sidebar.columns([4,1])
    with col1:
        if st.button(nm, key=f"profile_{nm}"):
            st.session_state["current_profile"] = nm
            st.session_state["page"] = "profil"
            save_state()
    with col2:
        if st.button("🗑", key=f"delete_{nm}"):
            st.session_state["delete_profile"] = nm
            save_state()

# Bekræft sletning
if st.session_state.get("delete_profile"):
    prof_to_del = st.session_state["delete_profile"]
    st.sidebar.warning(f"Slet profilen '{prof_to_del}'?")
    cconf, ccanc = st.sidebar.columns(2)
    with cconf:
        if st.button("Ja, slet"):
            st.session_state["profiles"].pop(prof_to_del,None)
            if st.session_state["current_profile"]==prof_to_del:
                st.session_state["current_profile"] = "Standard profil"
            st.session_state["delete_profile"] = None
            save_state()
    with ccanc:
        if st.button("Nej"):
            st.session_state["delete_profile"] = None
            save_state()

# Opret ny profil
if st.sidebar.button("Opret ny profil"):
    newpf = f"Ny profil {len(pnames)+1}"
    st.session_state["profiles"][newpf] = {"brand_profile":"","blacklist":"","produkt_info":""}
    st.session_state["current_profile"] = newpf
    st.session_state["page"] = "profil"
    save_state()

cur_data = st.session_state["profiles"].get(
    st.session_state["current_profile"],
    {"brand_profile":"","blacklist":"","produkt_info":""}
)

if cur_data.get("brand_profile","").strip():
    st.sidebar.markdown(cur_data["brand_profile"])
else:
    st.sidebar.info("Ingen virksomhedsprofil fundet endnu.")

if not st.session_state.get("page"):
    st.session_state["page"] = "profil"
    save_state()

# ----- Page: Profil -----
if st.session_state["page"]=="profil":
    st.header("Redigér virksomhedsprofil")

    # Redigér navnet
    cur_profile_name = st.text_input("Navn på virksomhedsprofil",
                                     value=st.session_state["current_profile"])
    if cur_profile_name != st.session_state["current_profile"]:
        oldp = st.session_state["current_profile"]
        if cur_profile_name.strip():
            st.session_state["profiles"][cur_profile_name] = st.session_state["profiles"].pop(oldp)
            st.session_state["current_profile"] = cur_profile_name
            cur_data = st.session_state["profiles"][cur_profile_name]
            save_state()

    # AI brandprofil (uden bæredygtighed)
    st.subheader("Hent AI-genereret virksomhedsprofil")
    url_profile = st.text_input("URL til fx 'Om os'")
    if st.button("Generér brandprofil (uden bæredygtighed)"):
        if url_profile:
            rawp = fetch_website_content(url_profile)
            if rawp:
                prompt = (
                    "Læs hjemmesideteksten herunder og skriv en fyldig virksomhedsprofil. "
                    "Ingen omtale af 'bæredygtighed'. Returnér KUN profilteksten.\n\n"
                    f"{rawp[:7000]}"
                )
                try:
                    r = openai.ChatCompletion.create(
                        model="gpt-4-turbo",
                        messages=[{"role":"user","content":prompt}],
                        max_tokens=1000
                    )
                    brandp = r.choices[0].message.content.strip()
                    st.session_state["profiles"][st.session_state["current_profile"]]["brand_profile"] = brandp
                    cur_data["brand_profile"] = brandp
                    save_state()
                    st.success("Virksomhedsprofil opdateret!")
                    st.text_area("Virksomhedsprofil (AI)", brandp, height=150)
                except Exception as e:
                    st.error(f"Fejl ved AI: {e}")
            else:
                st.warning("Tom tekst fundet ved URL")
        else:
            st.warning("Angiv en URL")

    # Hent produktlinks -> automatisk beriget
    st.subheader("Hent produktinfo (automatisk)")

    col_url = st.text_input("URL til kollektion (fx noyer.dk/collections/all)")
    if st.button("Hent links"):
        if col_url.strip():
            linklist = fetch_product_links(col_url.strip())
            st.session_state["collected_links"] = linklist
            st.write(f"Fandt {len(linklist)} unikke produktlinks.")
        else:
            st.warning("Angiv kollektions-URL")

    chosen=[]
    if "collected_links" in st.session_state and st.session_state["collected_links"]:
        st.write("Vælg produktsider at hente")
        for i, link in enumerate(st.session_state["collected_links"]):
            val = st.checkbox(link, key=f"cb_{i}", value=True)
            if val:
                chosen.append(link)

        if st.button("Hent valgte (autoberig)"):
            big_raw=""
            for c_link in chosen:
                rawt=fetch_product_text_raw(c_link)
                big_raw += f"\n\n=== PRODUKT ===\n{c_link}\n{rawt}"
            if big_raw.strip():
                # Kald GPT + efterbehandling
                final_product_info = automatically_enrich_product_text(big_raw)
                st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"]=final_product_info
                cur_data["produkt_info"]=final_product_info
                save_state()
                st.success("Produktinfo hentet og beriget automatisk!")
                st.text_area("Produktinfo", final_product_info, height=300)
            else:
                st.warning("Ingen rå tekst at berige")

    # Nu KUN to felter at redigere:
    # 1) Virksomhedsprofil
    # 2) Produktinfo
    st.subheader("Virksomhedsprofil")
    brand_txt = st.text_area("Virksomhedsprofil", cur_data.get("brand_profile",""), height=100)
    if st.button("Gem virksomhedsprofil"):
        st.session_state["profiles"][st.session_state["current_profile"]]["brand_profile"]=brand_txt
        cur_data["brand_profile"]=brand_txt
        save_state()
        st.success("Virksomhedsprofil gemt.")

    st.subheader("Produktinfo")
    pr_txt=st.text_area("Produktinfo", cur_data.get("produkt_info",""), height=150)
    if st.button("Gem produktinfo"):
        st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"]=pr_txt
        cur_data["produkt_info"]=pr_txt
        save_state()
        st.success("Produktinfo gemt.")

    # Fil upload (CSV, XLSX, PDF)
    st.markdown("---")
    st.subheader("Upload filer (valgfrit): CSV, XLSX eller PDF")
    fup = st.file_uploader("Vælg fil", type=["csv","xlsx","pdf"])
    if fup:
        st.write(f"Filen {fup.name} uploadet.")
        extracted=""
        if fup.name.endswith(".csv"):
            df=pd.read_csv(fup)
            extracted=df.to_string(index=False)
        elif fup.name.endswith(".xlsx"):
            df=pd.read_excel(fup)
            extracted=df.to_string(index=False)
        elif fup.name.endswith(".pdf"):
            reader=PyPDF2.PdfReader(fup)
            for pg in reader.pages:
                extracted+=pg.extract_text()
        st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"] = extracted
        cur_data["produkt_info"] = extracted
        save_state()
        st.success("Data gemt i 'produkt_info' fra fil.")

# == SEO-SIDE
elif st.session_state["page"]=="seo":
    st.header("Generér SEO-tekst")
    data = st.session_state["profiles"].get(
        st.session_state["current_profile"],
        {"brand_profile":"","blacklist":"","produkt_info":""}
    )
    st.write("Virksomhedsprofil:")
    st.markdown(data.get("brand_profile","Ingen profil."))

    seo_key = st.text_input("Søgeord / emne", "")
    length = st.number_input("Antal ord (ca.)", min_value=50, max_value=2000, value=300, step=50)
    tone = st.selectbox("Tone-of-voice", ["Neutral","Formel","Venlig","Entusiastisk"], 0)
    ant = st.selectbox("Antal SEO-tekster", list(range(1,11)), 0)

    if seo_key:
        if st.button("Generér SEO-tekst"):
            with st.spinner("Genererer SEO-tekst..."):
                for i in range(ant):
                    prompt=(
                        f"Skriv en SEO-optimeret tekst på dansk om '{seo_key}'. "
                        "Skriv overskrifter på normal dansk (ikke Title Case). "
                        "Du må ikke nævne 'bæredygtighed' eller 'bæredygtig'. "
                        f"Brug brandprofil: {data.get('brand_profile','')}. "
                        f"Brug produktinfo: {data.get('produkt_info','')}. "
                        f"Teksten skal være cirka {length} ord."
                    )
                    if tone:
                        prompt += f" Tone-of-voice: {tone}."
                    if data.get("blacklist","").strip():
                        prompt += f" Undgå disse ord: {data['blacklist']}."

                    try:
                        rseo = openai.ChatCompletion.create(
                            model="gpt-4-turbo",
                            messages=[{"role":"user","content":prompt}],
                            max_tokens=length*2
                        )
                        txt = rseo.choices[0].message.content.strip()
                        st.session_state["generated_texts"].append(txt)
                    except Exception as e:
                        st.error(f"Fejl: {e}")
            save_state()

            if st.session_state["generated_texts"]:
                st.subheader("Dine SEO-tekster")
                cpy = st.session_state["generated_texts"][:]
                for i,tex in enumerate(cpy):
                    with st.expander(f"SEO-tekst {i+1}"):
                        st.markdown(tex, unsafe_allow_html=True)
                        st.download_button(
                            label=f"Download SEO {i+1}",
                            data=tex,
                            file_name=f"seo_text_{i+1}.html",
                            mime="text/html"
                        )
                        if st.button(f"Slet {i+1}", key=f"del_{i}"):
                            st.session_state["generated_texts"].pop(i)
                            save_state()
                            st.experimental_rerun()
