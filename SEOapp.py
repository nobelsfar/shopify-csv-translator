import streamlit as st

# SKAL være første Streamlit-kald
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

# Vælg korrekt filsti for state
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

load_state()

if not st.session_state.get("api_key"):
    k_in = st.text_input("Indtast OpenAI API-nøgle", type="password")
    if k_in:
        st.session_state["api_key"] = k_in
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
        st.error(f"Fejl ved hentning: {e}")
        return ""

def fetch_product_links(url):
    links=[]
    try:
        resp=requests.get(url,timeout=10)
        resp.raise_for_status()
        soup=BeautifulSoup(resp.text,"html.parser")
        for a_tag in soup.find_all("a", href=True):
            hr=a_tag["href"]
            if hr.startswith("/products/"):
                full="https://noyer.dk"+hr
                if full not in links:
                    links.append(full)
    except Exception as e:
        st.error(f"Fejl ved produktlinks: {e}")
    return links

def fetch_product_text_raw(url):
    try:
        r=requests.get(url,timeout=10)
        r.raise_for_status()
        soup=BeautifulSoup(r.text,"html.parser")
        desc=soup.select_one(".product-info__description")
        if desc:
            return desc.get_text(separator=' ', strip=True)
        else:
            return soup.get_text(separator=' ', strip=True)
    except Exception as e:
        st.error(f"Fejl ved hentning af {url}: {e}")
        return ""

def automatically_enrich_product_text(raw_text):
    if not raw_text.strip():
        return ""
    prompt=(
        "Du får her en rå produkttekst. Strukturer og berig den let (tilføj evt. manglende data). "
        "Undgå store markdown-overskrifter (###) og ordene 'Produktbeskrivelse for'. "
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
        # Fjern 'Produktbeskrivelse for ':
        enriched = enriched.replace("Produktbeskrivelse for ","")
        # Fjern ### overskrifter
        enriched = re.sub(r'^###\s+(.*)$', r'\1', enriched, flags=re.MULTILINE)
        return enriched
    except Exception as e:
        st.error(f"Fejl ved berigelse: {e}")
        return raw_text

# --- Ordtælling + iterativ approach
def count_words(txt):
    # Split på whitespace for at tælle ord
    return len(txt.split())

def generate_iterative_seo_text(prompt_base, min_len=700, max_tries=3):
    """
    1) Kald GPT -> Få tekst
    2) Tjek ordantal -> Er det < min_len? Bed GPT udvide
    3) Returnér endelige version eller sidste forsøg
    """
    final_text = ""
    current_text = prompt_base
    attempt = 0

    # Første kald
    resp = openai.ChatCompletion.create(
        model="gpt-4-turbo",
        messages=[{"role":"user","content":prompt_base}],
        max_tokens=min_len*2
    )
    text_draft = resp.choices[0].message.content.strip()
    wcount = count_words(text_draft)
    attempt += 1

    # Hvis nok ord => break
    if wcount >= min_len:
        final_text = text_draft
    else:
        # Ellers bed GPT udvide
        final_text = text_draft
        for i in range(max_tries-1):
            extend_prompt = (
                f"Din tekst er {wcount} ord, men vi har brug for mindst {min_len}. "
                "Uddyb, giv flere eksempler, afsnit, FAQ, etc. Uden at gentage for meget:\n\n"
                f"{final_text}"
            )
            r2 = openai.ChatCompletion.create(
                model="gpt-4-turbo",
                messages=[{"role":"user","content":extend_prompt}],
                max_tokens=min_len*2
            )
            new_text = r2.choices[0].message.content.strip()
            wcount_new = count_words(new_text)
            if wcount_new >= min_len:
                final_text = new_text
                break
            else:
                final_text = new_text
                wcount = wcount_new
    return final_text

# --- GUI
st.sidebar.header("Navigation")
if st.sidebar.button("Skriv SEO-tekst"):
    st.session_state["page"]="seo"
    save_state()

st.sidebar.markdown("---")
st.sidebar.header("Virksomhedsprofiler")

pnames = list(st.session_state["profiles"].keys())
for nm in pnames:
    col1, col2=st.sidebar.columns([4,1])
    with col1:
        if st.button(nm,key=f"p_{nm}"):
            st.session_state["current_profile"]=nm
            st.session_state["page"]="profil"
            save_state()
    with col2:
        if st.button("🗑", key=f"d_{nm}"):
            st.session_state["delete_profile"]=nm
            save_state()

# Bekræft slet
if st.session_state.get("delete_profile"):
    pdel=st.session_state["delete_profile"]
    st.sidebar.warning(f"Slet {pdel}?")
    c_ok, c_no = st.sidebar.columns(2)
    with c_ok:
        if st.button("Ja, slet"):
            st.session_state["profiles"].pop(pdel,None)
            if st.session_state["current_profile"]==pdel:
                st.session_state["current_profile"]="Standard profil"
            st.session_state["delete_profile"]=None
            save_state()
    with c_no:
        if st.button("Nej"):
            st.session_state["delete_profile"]=None
            save_state()

if st.sidebar.button("Opret ny profil"):
    newp=f"Ny profil {len(pnames)+1}"
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
    st.sidebar.info("Ingen virksomhedsprofil endnu.")

if not st.session_state.get("page"):
    st.session_state["page"]="profil"
    save_state()

# ====== PROFIL-SIDE ======
if st.session_state["page"]=="profil":
    st.header("Redigér virksomhedsprofil")
    cur_profile_name = st.text_input("Navn på virksomhedsprofil", value=st.session_state["current_profile"])
    if cur_profile_name != st.session_state["current_profile"]:
        old_name=st.session_state["current_profile"]
        if cur_profile_name.strip():
            st.session_state["profiles"][cur_profile_name] = st.session_state["profiles"].pop(old_name)
            st.session_state["current_profile"]=cur_profile_name
            cur_data=st.session_state["profiles"][cur_profile_name]
            save_state()

    st.subheader("AI-genereret brandprofil (uden 'bæredygtighed')")
    url_profile = st.text_input("URL til fx 'Om os'")
    if st.button("Generér brandprofil"):
        if url_profile:
            rawp=fetch_website_content(url_profile)
            if rawp:
                pr_prompt=(
                    "Læs hjemmesideteksten herunder og skriv en fyldig virksomhedsprofil. "
                    "Ingen omtale af 'bæredygtighed'. Returnér kun selve profilteksten.\n\n"
                    f"{rawp[:7000]}"
                )
                try:
                    rp=openai.ChatCompletion.create(
                        model="gpt-4-turbo",
                        messages=[{"role":"user","content":pr_prompt}],
                        max_tokens=1000
                    )
                    brandpf=rp.choices[0].message.content.strip()
                    st.session_state["profiles"][st.session_state["current_profile"]]["brand_profile"]=brandpf
                    cur_data["brand_profile"]=brandpf
                    save_state()
                    st.success("Virksomhedsprofil opdateret!")
                    st.text_area("Virksomhedsprofil (AI)", brandpf, height=150)
                except Exception as e:
                    st.error(f"Fejl ved AI: {e}")
            else:
                st.warning("Tom tekst ved URL.")
        else:
            st.warning("Angiv en URL")

    st.subheader("Hent produktinfo (auto-berig)")
    col_url=st.text_input("URL til kollektion, fx noyer.dk/collections/all")
    if st.button("Hent produktlinks"):
        if col_url.strip():
            flinks=fetch_product_links(col_url.strip())
            st.session_state["collected_links"]=flinks
            st.write(f"Fandt {len(flinks)} links.")
        else:
            st.warning("Angiv URL")

    chosen=[]
    if "collected_links" in st.session_state and st.session_state["collected_links"]:
        st.write("Vælg produkter at hente:")
        for i,lnk in enumerate(st.session_state["collected_links"]):
            cbv=st.checkbox(lnk, key=f"ck_{i}", value=True)
            if cbv:
                chosen.append(lnk)

        if st.button("Hent valgte (auto-berig)"):
            big_raw=""
            for c_link in chosen:
                rtxt=fetch_product_text_raw(c_link)
                big_raw += f"\n\n=== PRODUKT ===\n{c_link}\n{rtxt}"
            if big_raw.strip():
                final_pi=automatically_enrich_product_text(big_raw)
                st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"]=final_pi
                cur_data["produkt_info"]=final_pi
                save_state()
                st.success("Produktinfo hentet & beriget.")
                st.text_area("Produktinfo", final_pi, height=300)
            else:
                st.warning("Ingen rå tekst at berige.")

    st.subheader("Virksomhedsprofil")
    br_txt=st.text_area("Virksomhedsprofil", cur_data.get("brand_profile",""), height=100)
    if st.button("Gem virksomhedsprofil"):
        st.session_state["profiles"][st.session_state["current_profile"]]["brand_profile"]=br_txt
        cur_data["brand_profile"]=br_txt
        save_state()
        st.success("Virksomhedsprofil gemt.")

    st.subheader("Produktinfo")
    pr_txt=st.text_area("Produktinfo", cur_data.get("produkt_info",""), height=150)
    if st.button("Gem produktinfo"):
        st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"]=pr_txt
        cur_data["produkt_info"]=pr_txt
        save_state()
        st.success("Produktinfo gemt.")

    st.markdown("---")
    st.subheader("Upload CSV, XLSX, PDF")
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
            for pg in reader.pages:
                extracted+=pg.extract_text()
        st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"]=extracted
        cur_data["produkt_info"]=extracted
        save_state()
        st.success("Data gemt i produktinfo.")

# ====== SEO-SIDE ======
elif st.session_state["page"]=="seo":
    st.header("Generér SEO-tekst (iterativ approach)")

    data=st.session_state["profiles"].get(
        st.session_state["current_profile"],
        {"brand_profile":"","blacklist":"","produkt_info":""}
    )
    st.write("Virksomhedsprofil:")
    st.markdown(data.get("brand_profile","(ingen)"))

    # A) Målgruppe
    malgruppe=st.selectbox("Målgruppe", ["B2C (forbrugere)","B2B (professionelle)","Design/fagligt interesserede","Andet"])
    # B) Formål
    formaal=st.selectbox("Formål med teksten", ["Salg/landingsside","Informativ blog","Branding/storytelling"])
    # C) Relaterede søgeord
    rel_soegeord=st.text_input("Relaterede søgeord (kommasepareret)", "")
    # D) SEO-check
    col_faq, col_meta, col_interne, col_cta = st.columns(4)
    with col_faq:
        inc_faq = st.checkbox("Inkluder FAQ")
    with col_meta:
        inc_meta = st.checkbox("Tilføj meta-titel+beskrivelse")
    with col_interne:
        inc_links = st.checkbox("Tilføj interne links")
    with col_cta:
        inc_cta = st.checkbox("Tilføj CTA")

    min_len=st.number_input("Minimum ordlængde (fx 700)", min_value=50, max_value=2000, value=700, step=50)
    out_format=st.selectbox("Output-format", ["Ren tekst","Markdown","HTML"])

    # Tone-of-voice
    tone_options=["Neutral","Formel","Venlig","Entusiastisk","Humoristisk","Autoritær","Professionel"]
    tone=st.selectbox("Tone-of-voice", tone_options, 0)

    # Hoved-søgeord
    seo_keyword=st.text_input("Hoved-søgeord / emne", "")
    antal=st.selectbox("Antal SEO-tekster", list(range(1,11)), 0)

    if seo_keyword:
        if st.button("Generér SEO-tekst"):
            with st.spinner("Genererer SEO-tekst..."):
                for i in range(antal):
                    # Byg prompt
                    base_prompt=(
                        f"Skriv en SEO-optimeret tekst på dansk om '{seo_keyword}'. "
                        f"Formål: {formaal}, Målgruppe: {malgruppe}, Tone-of-voice: {tone}.\n"
                        f"Brug brandprofil: {data.get('brand_profile','')} og produktinfo: {data.get('produkt_info','')}.\n"
                        f"Sigt efter mindst {min_len} ord.\n"
                        "Undgå 'bæredygtighed'/'bæredygtig'.\n"
                        "Brug disse relaterede søgeord: "
                        f"{rel_soegeord}.\n"
                    )
                    if inc_faq:
                        base_prompt += "Lav en FAQ-sektion med mindst 3 spørgsmål.\n"
                    if inc_meta:
                        base_prompt += "Tilføj en meta-titel (60 tegn) og meta-beskrivelse (160 tegn).\n"
                    if inc_links:
                        base_prompt += "Tilføj mindst 2 interne links.\n"
                    if inc_cta:
                        base_prompt += "Afslut med en tydelig Call to Action.\n"

                    if out_format=="HTML":
                        base_prompt += "Returnér i HTML med <h2>, <p>, <ul> etc.\n"
                    elif out_format=="Markdown":
                        base_prompt += "Returnér i Markdown med ## overskrifter.\n"
                    else:
                        base_prompt += "Returnér som ren tekst, ingen # overskrifter.\n"

                    if data.get("blacklist","").strip():
                        base_prompt += f" Undgå desuden ord: {data['blacklist']}.\n"

                    # Iterativ approach her:
                    final_seo = generate_iterative_seo_text(base_prompt, min_len=min_len, max_tries=3)

                    # Fjern "### " i output
                    final_seo = final_seo.replace("### ", "")

                    # Gem i session
                    st.session_state["generated_texts"].append(final_seo)
            save_state()

            if st.session_state["generated_texts"]:
                st.subheader("Dine SEO-tekster (iterativ)")
                cpy=st.session_state["generated_texts"][:]
                for i, txt in enumerate(cpy):
                    with st.expander(f"SEO-tekst {i+1}"):
                        st.text_area("Hele SEO-teksten", txt, height=600)
                        # download
                        file_ending = ".txt"
                        mime_type = "text/plain"
                        if out_format=="HTML":
                            file_ending = ".html"
                            mime_type = "text/html"

                        st.download_button(
                            label=f"Download SEO {i+1}",
                            data=txt,
                            file_name=f"seo_text_{i+1}{file_ending}",
                            mime=mime_type
                        )
                        # Slet
                        if st.button(f"Slet tekst {i+1}", key=f"del_{i}"):
                            st.session_state["generated_texts"].pop(i)
                            save_state()
                            st.experimental_rerun()
