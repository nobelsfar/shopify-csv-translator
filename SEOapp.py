import streamlit as st

# Kald set_page_config ALLERFØRST
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

# Vælg korrekt state-fil
if os.path.exists("/mnt/data") and os.access("/mnt/data", os.W_OK):
    STATE_FILE = "/mnt/data/state.json"
else:
    STATE_FILE = "state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                s = json.load(f)
            for k,v in s.items():
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
            st.error("Fejl ved oprettelse af mappe til state.")
    data_to_save = {
        "profiles": st.session_state.get("profiles", {}),
        "api_key": st.session_state.get("api_key",""),
        "page": st.session_state.get("page","seo"),
        "generated_texts": st.session_state.get("generated_texts",[]),
        "current_profile": st.session_state.get("current_profile","Standard profil"),
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

# Indlæs / initér
load_state()

# API-nøgle
if not st.session_state.get("api_key"):
    key_in = st.text_input("Indtast OpenAI API-nøgle", type="password")
    if key_in:
        st.session_state["api_key"] = key_in
        save_state()
    else:
        st.stop()

import openai
openai.api_key = st.session_state["api_key"]

def fetch_website_content(url):
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
    links=[]
    try:
        resp = requests.get(url,timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for a_tag in soup.find_all("a", href=True):
            hr=a_tag["href"]
            if hr.startswith("/products/"):
                full = "https://noyer.dk"+hr
                if full not in links:
                    links.append(full)
    except Exception as e:
        st.error(f"Fejl ved hentning af produktlinks: {e}")
    return links

def fetch_product_text_raw(url):
    try:
        r=requests.get(url,timeout=10)
        r.raise_for_status()
        soup=BeautifulSoup(r.text,"html.parser")
        desc=soup.select_one(".product-info__description")
        if desc:
            return desc.get_text(separator=' ',strip=True)
        else:
            return soup.get_text(separator=' ',strip=True)
    except Exception as e:
        st.error(f"Fejl ved hentning af produktside: {e}")
        return ""

def automatically_enrich_product_text(raw_text):
    if not raw_text.strip():
        return ""
    prompt = (
        "Du får her en rå produkttekst. Strukturer og berig den let (tilføj evt. manglende data), "
        "men undgå store markdown-overskrifter (###) og ordene 'Produktbeskrivelse for'. "
        "Undgå at ændre for meget i ordlyden.\n\n"
        f"{raw_text[:15000]}"
    )
    try:
        r2=openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[{"role":"user","content":prompt}],
            max_tokens=3000
        )
        enriched = r2.choices[0].message.content.strip()
        # Fjern "Produktbeskrivelse for "
        enriched = enriched.replace("Produktbeskrivelse for ","")
        # Fjern ### overskrifter
        enriched = re.sub(r'^###\s+(.*)$', r'\1', enriched, flags=re.MULTILINE)
        return enriched
    except Exception as e:
        st.error(f"Fejl ved berigelse: {e}")
        return raw_text

# Sidebar
st.sidebar.header("Navigation")
if st.sidebar.button("Skriv SEO-tekst"):
    st.session_state["page"] = "seo"
    save_state()

st.sidebar.markdown("---")
st.sidebar.header("Virksomhedsprofiler")

prof_names = list(st.session_state["profiles"].keys())
for nm in prof_names:
    c1, c2=st.sidebar.columns([4,1])
    with c1:
        if st.button(nm,key=f"prof_{nm}"):
            st.session_state["current_profile"]=nm
            st.session_state["page"]="profil"
            save_state()
    with c2:
        if st.button("🗑",key=f"del_{nm}"):
            st.session_state["delete_profile"]=nm
            save_state()

if st.session_state.get("delete_profile"):
    pdel=st.session_state["delete_profile"]
    st.sidebar.warning(f"Slet profil '{pdel}'?")
    cok, cno = st.sidebar.columns(2)
    with cok:
        if st.button("Ja, slet"):
            st.session_state["profiles"].pop(pdel,None)
            if st.session_state["current_profile"]==pdel:
                st.session_state["current_profile"]="Standard profil"
            st.session_state["delete_profile"]=None
            save_state()
    with cno:
        if st.button("Nej"):
            st.session_state["delete_profile"]=None
            save_state()

if st.sidebar.button("Opret ny profil"):
    newp=f"Ny profil {len(prof_names)+1}"
    st.session_state["profiles"][newp]={"brand_profile":"","blacklist":"","produkt_info":""}
    st.session_state["current_profile"]=newp
    st.session_state["page"]="profil"
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
    st.session_state["page"]="profil"
    save_state()

# ====== Side: Profil ======
if st.session_state["page"]=="profil":
    st.header("Redigér virksomhedsprofil")

    current_profile_name = st.text_input("Navn på virksomhedsprofil", value=st.session_state["current_profile"])
    if current_profile_name != st.session_state["current_profile"]:
        old_n=st.session_state["current_profile"]
        if current_profile_name.strip():
            st.session_state["profiles"][current_profile_name] = st.session_state["profiles"].pop(old_n)
            st.session_state["current_profile"]=current_profile_name
            cur_data=st.session_state["profiles"][current_profile_name]
            save_state()

    st.subheader("Hent AI-genereret virksomhedsprofil (uden bæredygtighed)")
    url_profile = st.text_input("URL til 'Om os'-side")
    if st.button("Generér brandprofil"):
        if url_profile:
            raw_txt=fetch_website_content(url_profile)
            if raw_txt:
                prompt=(
                    "Læs hjemmesideteksten herunder og skriv en fyldig virksomhedsprofil. "
                    "Ingen omtale af 'bæredygtighed'. Returnér kun tekst:\n\n"
                    f"{raw_txt[:7000]}"
                )
                try:
                    resp=openai.ChatCompletion.create(
                        model="gpt-4-turbo",
                        messages=[{"role":"user","content":prompt}],
                        max_tokens=1000
                    )
                    brandp = resp.choices[0].message.content.strip()
                    st.session_state["profiles"][st.session_state["current_profile"]]["brand_profile"]=brandp
                    cur_data["brand_profile"]=brandp
                    save_state()
                    st.success("Virksomhedsprofil opdateret!")
                    st.text_area("Virksomhedsprofil (AI)", brandp, height=150)
                except Exception as e:
                    st.error(f"Fejl ved AI: {e}")
            else:
                st.warning("Tom tekst fundet ved URL.")
        else:
            st.warning("Angiv en URL")

    st.subheader("Hent produktinfo (automatisk beriget)")

    col_url = st.text_input("URL til kollektion, fx https://noyer.dk/collections/all")
    if st.button("Hent produktlinks"):
        if col_url.strip():
            found=fetch_product_links(col_url.strip())
            st.session_state["collected_links"]=found
            st.write(f"Fandt {len(found)} unikke links.")
        else:
            st.warning("Angiv en URL")

    chosen=[]
    if "collected_links" in st.session_state and st.session_state["collected_links"]:
        st.write("Vælg produkter at hente tekst fra:")
        for i, link in enumerate(st.session_state["collected_links"]):
            cb_val=st.checkbox(link, key=f"ck_{i}", value=True)
            if cb_val:
                chosen.append(link)

        if st.button("Hent valgte (auto-berig)"):
            big_raw=""
            for c_link in chosen:
                raw_data = fetch_product_text_raw(c_link)
                big_raw += f"\n\n=== PRODUKT ===\n{c_link}\n{raw_data}"
            if big_raw.strip():
                final_pi = automatically_enrich_product_text(big_raw)
                st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"] = final_pi
                cur_data["produkt_info"] = final_pi
                save_state()
                st.success("Produktinfo hentet + beriget!")
                st.text_area("Produktinfo", final_pi, height=300)
            else:
                st.warning("Ingen rå tekst at berige.")

    # Viser to felter: brand_profile, produkt_info
    st.subheader("Virksomhedsprofil")
    brand_txt = st.text_area("Virksomhedsprofil (manuel redigering)", cur_data.get("brand_profile",""), height=100)
    if st.button("Gem virksomhedsprofil"):
        st.session_state["profiles"][st.session_state["current_profile"]]["brand_profile"] = brand_txt
        cur_data["brand_profile"] = brand_txt
        save_state()
        st.success("Virksomhedsprofil gemt.")

    st.subheader("Produktinfo")
    prod_txt = st.text_area("Produktinfo (manuel redigering)", cur_data.get("produkt_info",""), height=150)
    if st.button("Gem produktinfo"):
        st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"] = prod_txt
        cur_data["produkt_info"] = prod_txt
        save_state()
        st.success("Produktinfo gemt.")

    # Fil upload
    st.markdown("---")
    st.subheader("Upload CSV, XLSX eller PDF til produktinfo")
    upf = st.file_uploader("Vælg fil", type=["csv","xlsx","pdf"])
    if upf:
        st.write(f"Filen {upf.name} uploadet.")
        extracted=""
        if upf.name.endswith(".csv"):
            df=pd.read_csv(upf)
            extracted=df.to_string(index=False)
        elif upf.name.endswith(".xlsx"):
            df=pd.read_excel(upf)
            extracted=df.to_string(index=False)
        elif upf.name.endswith(".pdf"):
            reader=PyPDF2.PdfReader(upf)
            for page in reader.pages:
                extracted+=page.extract_text()
        st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"]=extracted
        cur_data["produkt_info"]=extracted
        save_state()
        st.success("Data gemt til produktinfo.")

# ====== SEO-SIDE =======
elif st.session_state["page"]=="seo":
    st.header("Generér SEO-tekst")

    data=st.session_state["profiles"].get(
        st.session_state["current_profile"],
        {"brand_profile":"","blacklist":"","produkt_info":""}
    )
    st.write("Virksomhedsprofil:")
    st.markdown(data.get("brand_profile","(Ingen profil)"))

    # --- NYE FELTER TIL BEDRE SEO-TEKSTER ---

    # A) Målgruppe
    malgruppe = st.selectbox("Målgruppe", ["B2C (forbrugere)","B2B (professionelle)","Design/fagligt interesserede","Andet"])
    # B) Formål
    formaal = st.selectbox("Formål med teksten", ["Salg/landingsside","Informativ blog","Branding/storytelling"])
    # C) Relaterede søgeord
    rel_soegeord = st.text_input("Relaterede søgeord (kommasepareret)", "")
    # D) SEO-tjekliste
    col_faq, col_meta, col_interne, col_cta = st.columns(4)
    with col_faq:
        inc_faq = st.checkbox("Inkluder FAQ-sektion")
    with col_meta:
        inc_meta = st.checkbox("Tilføj meta-titel+beskrivelse")
    with col_interne:
        inc_links = st.checkbox("Tilføj interne links")
    with col_cta:
        inc_cta = st.checkbox("Tilføj Call to Action")
    # E) Min. ordlængde
    min_len = st.number_input("Minimum ordlængde (ca.)", min_value=50, max_value=2000, value=700, step=50)
    # F) Output-format
    out_format = st.selectbox("Output-format", ["Ren tekst","Markdown","HTML"])

    # -----------
    # TONE-OF-VOICE
    st.write("Tone-of-voice:")
    tone_options = ["Neutral","Formel","Venlig","Entusiastisk","Humoristisk","Autoritær","Professionel"]
    tone = st.selectbox("Vælg tone", tone_options, 0)

    # SØGEORD
    seo_keyword = st.text_input("Hoved-søgeord / emne", "")
    # Antal tekster
    antal = st.selectbox("Antal SEO-tekster", list(range(1,11)), 0)

    if seo_keyword:
        if st.button("Generér SEO-tekst"):
            with st.spinner("Genererer SEO-tekst..."):
                for i in range(antal):
                    prompt=(
                        f"Skriv en SEO-optimeret tekst på dansk om '{seo_keyword}'. "
                        f"Formål: {formaal}, Målgruppe: {malgruppe}, Tone-of-voice: {tone}. "
                        f"Brug brandprofil: {data.get('brand_profile','')} og produktinfo: {data.get('produkt_info','')}. "
                        f"Sigt efter mindst {min_len} ord. "
                        "Undgå 'bæredygtighed'/'bæredygtig'. "

                        # tjekliste:
                        "Inkluder gerne relaterede søgeord: "
                        f"{rel_soegeord}. "
                    )
                    if inc_faq:
                        prompt += "Opret en FAQ-sektion med mindst 3 spørgsmål.\n"
                    if inc_meta:
                        prompt += "Tilføj en meta-titel (60 tegn max) og meta-beskrivelse (160 tegn max).\n"
                    if inc_links:
                        prompt += "Tilføj mindst 2 interne links i teksten.\n"
                    if inc_cta:
                        prompt += "Afslut med en tydelig Call to Action.\n"

                    # Output-format
                    if out_format == "HTML":
                        prompt += "Returnér teksten i HTML med <h2>, <p>, <ul>, etc.\n"
                    elif out_format == "Markdown":
                        prompt += "Returnér teksten i Markdown med ## Overskrifter.\n"
                    else:
                        prompt += "Returnér teksten som ren tekst, uden overskrifter i #.\n"

                    # Blacklist
                    if data.get("blacklist","").strip():
                        prompt += f" Undgå desuden ord: {data['blacklist']}.\n"

                    try:
                        rseo = openai.ChatCompletion.create(
                            model="gpt-4-turbo",
                            messages=[{"role":"user","content":prompt}],
                            max_tokens=min_len*2
                        )
                        txt = rseo.choices[0].message.content.strip()

                        # Evt. fjern ### i output:
                        txt = txt.replace("### ", "")

                        st.session_state["generated_texts"].append(txt)
                    except Exception as e:
                        st.error(f"Fejl ved SEO AI: {e}")
            save_state()

            if st.session_state["generated_texts"]:
                st.subheader("Dine SEO-tekster")
                cpy = st.session_state["generated_texts"][:]
                for i,tex in enumerate(cpy):
                    with st.expander(f"SEO-tekst {i+1}"):
                        st.text_area("Hele SEO-teksten", tex, height=600)
                        st.download_button(
                            label=f"Download SEO {i+1}",
                            data=tex,
                            file_name=f"seo_text_{i+1}.txt",  # eller .html hvis out_format var HTML
                            mime="text/plain"  # eller text/html
                        )
                        if st.button(f"Slet tekst {i+1}", key=f"del_{i}"):
                            st.session_state["generated_texts"].pop(i)
                            save_state()
                            st.experimental_rerun()
