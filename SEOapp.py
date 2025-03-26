import streamlit as st

# 1) Side-konfiguration SKAL være første Streamlit-kald
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

# Vælg korrekt sti til state-fil
if os.path.exists("/mnt/data") and os.access("/mnt/data", os.W_OK):
    STATE_FILE = "/mnt/data/state.json"
else:
    STATE_FILE = "state.json"

def load_state():
    """Loader gemt session_state fra STATE_FILE, hvis den findes."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                loaded = json.load(f)
            for k, v in loaded.items():
                st.session_state[k] = v
        except:
            initialize_state()
    else:
        initialize_state()

def save_state():
    """Gemmer session_state til STATE_FILE."""
    folder = os.path.dirname(STATE_FILE)
    if folder and not os.path.exists(folder):
        try:
            os.makedirs(folder, exist_ok=True)
        except:
            st.error("Fejl ved oprettelse af mappe til state.")
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

# Kør load_state ved opstart
load_state()

# Hvis ingen API-nøgle, bed bruger om den
if not st.session_state.get("api_key"):
    key_input = st.text_input("Indtast OpenAI API-nøgle", type="password")
    if key_input:
        st.session_state["api_key"] = key_input
        save_state()
    else:
        st.stop()

openai.api_key = st.session_state["api_key"]

def fetch_website_content(url):
    """Henter rå tekst fra en URL (fjerner script/style)."""
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for s in soup(["script","style"]):
            s.decompose()
        return soup.get_text(separator=' ', strip=True)
    except Exception as e:
        st.error(f"Fejl ved hentning af hjemmesideindhold: {e}")
        return ""

def fetch_product_links(url):
    """Finder alle /products/ -links, undgår dubletter."""
    links = []
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            hr = a["href"]
            if hr.startswith("/products/"):
                full_link = "https://noyer.dk" + hr
                if full_link not in links:
                    links.append(full_link)
    except Exception as e:
        st.error(f"Fejl ved hentning af produktlinks: {e}")
    return links

def fetch_product_text_raw(url):
    """Henter .product-info__description eller hele sideindholdet som fallback."""
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
        st.error(f"Fejl ved hentning af produktside: {e}")
        return ""

def automatically_enrich_product_text(raw_text):
    """
    Kalder GPT for at "berige" tekst:
    - Undgår 'Produktbeskrivelse for '
    - Erstatter ### med normal tekst
    - Fjerner dem til slut
    """
    if not raw_text.strip():
        return ""
    prompt = (
        "Du får her en rå produkttekst. Strukturer og berig den let (tilføj evt. manglende data), "
        "men undgå store markdown-overskrifter (###). Du må ikke skrive 'Produktbeskrivelse for'. "
        "Undgå at ændre for meget i ordlyden.\n\n"
        f"{raw_text[:15000]}"
    )
    try:
        r2 = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[{"role":"user","content":prompt}],
            max_tokens=3000
        )
        enriched = r2.choices[0].message.content.strip()
        # Fjern 'Produktbeskrivelse for ' hvis GPT skrev det
        enriched = enriched.replace("Produktbeskrivelse for ","")
        # Evt. erstat ### -> ingenting
        enriched = re.sub(r'^###\s+(.*)$', r'\1', enriched, flags=re.MULTILINE)
        return enriched
    except Exception as e:
        st.error(f"Fejl ved berigelse: {e}")
        return raw_text

# --- Sidebar
st.sidebar.header("Navigation")
if st.sidebar.button("Skriv SEO-tekst"):
    st.session_state["page"] = "seo"
    save_state()

st.sidebar.markdown("---")
st.sidebar.header("Virksomhedsprofiler")

profile_names = list(st.session_state["profiles"].keys())
for nm in profile_names:
    c1, c2 = st.sidebar.columns([4,1])
    with c1:
        if st.button(nm, key=f"prof_{nm}"):
            st.session_state["current_profile"] = nm
            st.session_state["page"] = "profil"
            save_state()
    with c2:
        if st.button("🗑", key=f"del_{nm}"):
            st.session_state["delete_profile"] = nm
            save_state()

if st.session_state.get("delete_profile"):
    prof_del = st.session_state["delete_profile"]
    st.sidebar.warning(f"Slet profilen '{prof_del}'?")
    col_conf, col_cancel = st.sidebar.columns(2)
    with col_conf:
        if st.button("Ja, slet"):
            st.session_state["profiles"].pop(prof_del, None)
            if st.session_state["current_profile"] == prof_del:
                st.session_state["current_profile"] = "Standard profil"
            st.session_state["delete_profile"] = None
            save_state()
    with col_cancel:
        if st.button("Nej"):
            st.session_state["delete_profile"] = None
            save_state()

if st.sidebar.button("Opret ny profil"):
    newp = f"Ny profil {len(profile_names)+1}"
    st.session_state["profiles"][newp] = {"brand_profile":"","blacklist":"","produkt_info":""}
    st.session_state["current_profile"] = newp
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
if st.session_state["page"] == "profil":
    st.header("Redigér virksomhedsprofil")

    current_profile_name = st.text_input(
        "Navn på virksomhedsprofil",
        value=st.session_state["current_profile"]
    )
    if current_profile_name != st.session_state["current_profile"]:
        old_n = st.session_state["current_profile"]
        if current_profile_name.strip():
            st.session_state["profiles"][current_profile_name] = st.session_state["profiles"].pop(old_n)
            st.session_state["current_profile"] = current_profile_name
            cur_data = st.session_state["profiles"][current_profile_name]
            save_state()

    # AI brandprofil
    st.subheader("Hent AI-genereret virksomhedsprofil (uden 'bæredygtighed')")
    url_profile = st.text_input("URL til fx 'Om os'")
    if st.button("Generér brandprofil"):
        if url_profile:
            raw_pr = fetch_website_content(url_profile)
            if raw_pr:
                prompt = (
                    "Læs hjemmesideteksten herunder og skriv en fyldig virksomhedsprofil. "
                    "Ingen omtale af 'bæredygtighed'. Returnér kun selve profilteksten.\n\n"
                    f"{raw_pr[:7000]}"
                )
                try:
                    resp = openai.ChatCompletion.create(
                        model="gpt-4-turbo",
                        messages=[{"role":"user","content":prompt}],
                        max_tokens=1000
                    )
                    brand = resp.choices[0].message.content.strip()
                    st.session_state["profiles"][st.session_state["current_profile"]]["brand_profile"] = brand
                    cur_data["brand_profile"] = brand
                    save_state()
                    st.success("Virksomhedsprofil opdateret!")
                    st.text_area("Virksomhedsprofil (AI)", brand, height=150)
                except Exception as e:
                    st.error(f"Fejl ved AI: {e}")
            else:
                st.warning("Tom tekst fundet fra URL.")
        else:
            st.warning("Angiv en URL.")

    # Hent produktinfo -> Berig
    st.subheader("Hent produktinfo (automatisk beriget)")

    coll_url = st.text_input("URL til kollektion, fx 'https://noyer.dk/collections/all'")
    if st.button("Hent produktlinks"):
        if coll_url.strip():
            links_found = fetch_product_links(coll_url.strip())
            st.session_state["collected_links"] = links_found
            st.write(f"Fandt {len(links_found)} unikke produktlinks.")
        else:
            st.warning("Angiv kollektions-URL")

    chosen=[]
    if "collected_links" in st.session_state and st.session_state["collected_links"]:
        st.write("Vælg produkter at hente tekst fra:")
        for i, lnk in enumerate(st.session_state["collected_links"]):
            cval = st.checkbox(lnk, key=f"ck_{i}", value=True)
            if cval:
                chosen.append(lnk)

        if st.button("Hent valgte (auto-berig)"):
            all_raw = ""
            for c_link in chosen:
                rtxt = fetch_product_text_raw(c_link)
                all_raw += f"\n\n=== PRODUKT ===\n{c_link}\n{rtxt}"

            if all_raw.strip():
                # Kør GPT for at "berige"
                final_pi = automatically_enrich_product_text(all_raw)
                st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"] = final_pi
                cur_data["produkt_info"] = final_pi
                save_state()
                st.success("Produktinfo hentet + beriget!")
                st.text_area("Produktinfo", final_pi, height=300)
            else:
                st.warning("Ingen rå tekst at berige.")

    # 2 felter: Virksomhedsprofil, Produktinfo
    st.subheader("Virksomhedsprofil")
    brand_txt = st.text_area("Virksomhedsprofil (manuel redigering)", cur_data.get("brand_profile",""), height=100)
    if st.button("Gem virksomhedsprofil"):
        st.session_state["profiles"][st.session_state["current_profile"]]["brand_profile"] = brand_txt
        cur_data["brand_profile"] = brand_txt
        save_state()
        st.success("Virksomhedsprofil gemt.")

    st.subheader("Produktinfo")
    pr_txt = st.text_area("Produktinfo (manuel redigering)", cur_data.get("produkt_info",""), height=150)
    if st.button("Gem produktinfo"):
        st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"] = pr_txt
        cur_data["produkt_info"] = pr_txt
        save_state()
        st.success("Produktinfo gemt.")

    # Fil upload (valgfrit)
    st.markdown("---")
    st.subheader("Upload CSV, XLSX eller PDF (valgfrit)")
    up = st.file_uploader("Vælg fil", type=["csv","xlsx","pdf"])
    if up:
        st.write(f"Filen {up.name} uploadet.")
        ex=""
        if up.name.endswith(".csv"):
            df = pd.read_csv(up)
            ex = df.to_string(index=False)
        elif up.name.endswith(".xlsx"):
            df = pd.read_excel(up)
            ex = df.to_string(index=False)
        elif up.name.endswith(".pdf"):
            reader=PyPDF2.PdfReader(up)
            for pg in reader.pages:
                ex+=pg.extract_text()
        st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"]=ex
        cur_data["produkt_info"]=ex
        save_state()
        st.success("Data gemt i 'produkt_info'.")

# ----- SEO PAGE
elif st.session_state["page"]=="seo":
    st.header("Generér SEO-tekst")
    data = st.session_state["profiles"].get(
        st.session_state["current_profile"],
        {"brand_profile":"","blacklist":"","produkt_info":""}
    )
    st.write("Virksomhedsprofil:")
    st.markdown(data.get("brand_profile","Ingen profil."))

    # Udvidet tone-of-voice
    tone_options = ["Neutral","Formel","Venlig","Entusiastisk","Humoristisk","Autoritær","Professionel"]
    seo_keyword = st.text_input("Søgeord / emne", "")
    laengde = st.number_input("Antal ord (ca.)", min_value=50, max_value=2000, value=300, step=50)
    tone = st.selectbox("Tone-of-voice", tone_options, 0)
    antal = st.selectbox("Antal SEO-tekster", list(range(1,11)), 0)

    if seo_keyword:
        if st.button("Generér SEO-tekst"):
            with st.spinner("Genererer SEO-tekst..."):
                for i in range(antal):
                    # Prompt med SEO-tjekliste
                    prompt=(
                        f"Skriv en SEO-optimeret artikel på dansk om '{seo_keyword}'. "
                        f"Den skal være mindst {laengde} ord, hvis muligt. "
                        "Brug normal dansk i overskrifter (ikke Title Case), "
                        "lav en meta-titel (max 60 tegn) og meta-beskrivelse (max 160 tegn). "
                        "Tilføj evt. FAQ, interne links og en konklusion med call-to-action. "
                        f"Undgå 'bæredygtighed' eller 'bæredygtig'. "
                        f"Brug brandprofil: {data.get('brand_profile','')} "
                        f"og produktinfo: {data.get('produkt_info','')}. "
                        "Hvis teksten mangler stof for at nå længden, så uddyber du pointer, eksempler og cases. "
                        "Tone-of-voice: {tone}."
                    )
                    if data.get("blacklist","").strip():
                        prompt += f" Undgå desuden ord: {data['blacklist']}."

                    try:
                        rseo = openai.ChatCompletion.create(
                            model="gpt-4-turbo",
                            messages=[{"role":"user","content":prompt}],
                            max_tokens=laengde*2
                        )
                        txt = rseo.choices[0].message.content.strip()
                        st.session_state["generated_texts"].append(txt)
                    except Exception as e:
                        st.error(f"Fejl ved SEO AI: {e}")
            save_state()

            if st.session_state["generated_texts"]:
                st.subheader("Dine SEO-tekster")
                cpy = st.session_state["generated_texts"][:]
                for i,tex in enumerate(cpy):
                    # Evt. fjerne "### " i SEO-output
                    cleaned = tex.replace("### ", "")

                    with st.expander(f"SEO-tekst {i+1}"):
                        st.text_area("Hele SEO-teksten:", cleaned, height=800)
                        st.download_button(
                            label=f"Download SEO {i+1} (HTML)",
                            data=cleaned,
                            file_name=f"seo_text_{i+1}.html",
                            mime="text/html"
                        )
                        if st.button(f"Slet {i+1}", key=f"del_{i}"):
                            st.session_state["generated_texts"].pop(i)
                            save_state()
                            st.experimental_rerun()
