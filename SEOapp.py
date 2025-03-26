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
    """Loader session_state fra fil, hvis den findes."""
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
    """Gemmer session_state til STATE_FILE."""
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
        "generated_texts": st.session_state.get("generated_texts", []),
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
    inp = st.text_input("Indtast OpenAI API-nøgle", type="password")
    if inp:
        st.session_state["api_key"] = inp
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
    """Henter, beriger og fjerner ###, 'Produktbeskrivelse for ...'"""
    if not raw_text.strip():
        return ""
    prompt = (
        "Du får her en rå produkttekst. Strukturer og berig den let (tilføj evt. manglende data). "
        "Undgå store markdown-overskrifter (###) og 'Produktbeskrivelse for'. "
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
        # Fjern 'Produktbeskrivelse for '
        enriched = enriched.replace("Produktbeskrivelse for ","")
        # Fjern ### overskrifter
        enriched = re.sub(r'^###\s+(.*)$', r'\1', enriched, flags=re.MULTILINE)
        return enriched
    except Exception as e:
        st.error(f"Fejl ved berigelse: {e}")
        return raw_text

def count_words(txt):
    return len(txt.split())

def generate_iterative_seo_text(base_prompt, min_len=700, max_tries=3):
    """
    1) Kald GPT -> tekst
    2) Tjek ordantal -> bed GPT udvide
    3) Returnér endeligt
    """
    final_text = ""
    # Første kald
    resp = openai.ChatCompletion.create(
        model="gpt-4-turbo",
        messages=[{"role":"user","content":base_prompt}],
        max_tokens=min_len*2
    )
    text_draft = resp.choices[0].message.content.strip()
    wcount = count_words(text_draft)

    if wcount >= min_len:
        final_text = text_draft
    else:
        final_text = text_draft
        tries_left = max_tries - 1
        for i in range(tries_left):
            ext_prompt = (
                f"Din tekst er {wcount} ord, men vi ønsker mindst {min_len}. "
                "Uddyb og tilføj flere afsnit, eksempler, FAQ osv.:\n\n"
                f"{final_text}"
            )
            r2 = openai.ChatCompletion.create(
                model="gpt-4-turbo",
                messages=[{"role":"user","content":ext_prompt}],
                max_tokens=min_len*2
            )
            new_text = r2.choices[0].message.content.strip()
            wcount2 = count_words(new_text)
            if wcount2 >= min_len:
                final_text = new_text
                break
            else:
                final_text = new_text
                wcount = wcount2
    return final_text

def check_blacklist_and_rewrite(text, blacklist_words, max_tries=2):
    """Hvis blacklisted ord optræder i text, bed GPT genskrive uden dem."""
    if not blacklist_words.strip():
        return text  # intet at checke

    words_list = [w.strip().lower() for w in blacklist_words.split(",") if w.strip()]

    def contains_blacklisted(t):
        lower_t = t.lower()
        for w in words_list:
            if w in lower_t:
                return True
        return False

    final_text = text
    for attempt in range(max_tries):
        if not contains_blacklisted(final_text):
            break
        # find dem
        found=[]
        lft = final_text.lower()
        for w in words_list:
            if w in lft:
                found.append(w)

        # bed GPT genskrive
        rewrite_prompt=(
            f"Nogle forbudte ord blev brugt: {found}. Fjern eller omformuler dem, "
            "uden at forkorte teksten væsentligt:\n\n"
            f"{final_text}"
        )
        r3=openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[{"role":"user","content":rewrite_prompt}],
            max_tokens=len(final_text.split())*2
        )
        final_text=r3.choices[0].message.content.strip()

    return final_text

# ---- SIDEBAR ----
st.sidebar.header("Navigation")
if st.sidebar.button("Skriv SEO-tekst"):
    st.session_state["page"] = "seo"
    save_state()

st.sidebar.markdown("---")
st.sidebar.header("Virksomhedsprofiler")

pnames = list(st.session_state["profiles"].keys())
for nm in pnames:
    c1, c2=st.sidebar.columns([4,1])
    with c1:
        if st.button(nm, key=f"profile_{nm}"):
            st.session_state["current_profile"]=nm
            st.session_state["page"]="profil"
            save_state()
    with c2:
        if st.button("🗑", key=f"del_{nm}"):
            st.session_state["delete_profile"]=nm
            save_state()

if st.session_state.get("delete_profile"):
    pdel=st.session_state["delete_profile"]
    st.sidebar.warning(f"Slet profil '{pdel}'?")
    c_ok, c_no = st.sidebar.columns(2)
    with c_ok:
        if st.button("Ja, slet"):
            st.session_state["profiles"].pop(pdel, None)
            if st.session_state["current_profile"] == pdel:
                st.session_state["current_profile"] = "Standard profil"
            st.session_state["delete_profile"] = None
            save_state()
    with c_no:
        if st.button("Nej"):
            st.session_state["delete_profile"] = None
            save_state()

if st.sidebar.button("Opret ny profil"):
    newp = f"Ny profil {len(pnames)+1}"
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
    st.session_state["page"]="profil"
    save_state()

# ----- PROFIL-SIDE -----
if st.session_state["page"]=="profil":
    st.header("Redigér virksomhedsprofil")

    prof_name=st.text_input("Navn på virksomhedsprofil", value=st.session_state["current_profile"])
    if prof_name != st.session_state["current_profile"]:
        old=st.session_state["current_profile"]
        if prof_name.strip():
            st.session_state["profiles"][prof_name] = st.session_state["profiles"].pop(old)
            st.session_state["current_profile"]=prof_name
            cur_data=st.session_state["profiles"][prof_name]
            save_state()

    st.subheader("Hent AI-genereret brandprofil (uden 'bæredygtighed')")
    url_profile = st.text_input("URL til fx 'Om os'")
    if st.button("Generér brandprofil"):
        if url_profile:
            rawp=fetch_website_content(url_profile)
            if rawp:
                prompt=(
                    "Læs hjemmesideteksten herunder og skriv en fyldig virksomhedsprofil. "
                    "Ingen omtale af 'bæredygtighed'. Returnér kun profilteksten.\n\n"
                    f"{rawp[:7000]}"
                )
                try:
                    rp=openai.ChatCompletion.create(
                        model="gpt-4-turbo",
                        messages=[{"role":"user","content":prompt}],
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
                st.warning("Tom tekst fundet ved URL.")
        else:
            st.warning("Angiv en URL")

    st.subheader("Hent produktinfo (automatisk beriget)")
    coll_url = st.text_input("URL til kollektion (fx https://noyer.dk/collections/all)")
    if st.button("Hent produktlinks"):
        if coll_url.strip():
            links_found=fetch_product_links(coll_url.strip())
            st.session_state["collected_links"]=links_found
            st.write(f"Fandt {len(links_found)} produktlinks.")
        else:
            st.warning("Angiv URL")

    chosen=[]
    if "collected_links" in st.session_state and st.session_state["collected_links"]:
        st.write("Vælg produkter at hente:")
        for i, lnk in enumerate(st.session_state["collected_links"]):
            c_val=st.checkbox(lnk, key=f"ck_{i}", value=True)
            if c_val:
                chosen.append(lnk)

        if st.button("Hent valgte (auto-berig)"):
            big_raw=""
            for c_link in chosen:
                rawt=fetch_product_text_raw(c_link)
                big_raw += f"\n\n=== PRODUKT ===\n{c_link}\n{rawt}"
            if big_raw.strip():
                final_pi=automatically_enrich_product_text(big_raw)
                st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"]=final_pi
                cur_data["produkt_info"]=final_pi
                save_state()
                st.success("Produktinfo hentet + beriget.")
                st.text_area("Produktinfo", final_pi, height=300)
            else:
                st.warning("Ingen tekst at berige.")

    # 2 felter: brandprofile, produktinfo
    st.subheader("Virksomhedsprofil")
    br_txt=st.text_area("Virksomhedsprofil", cur_data.get("brand_profile",""), height=100)
    if st.button("Gem virksomhedsprofil"):
        st.session_state["profiles"][st.session_state["current_profile"]]["brand_profile"]=br_txt
        cur_data["brand_profile"]=br_txt
        save_state()
        st.success("Virksomhedsprofil gemt.")

    st.subheader("Produktinfo")
    pr_tx=st.text_area("Produktinfo", cur_data.get("produkt_info",""), height=150)
    if st.button("Gem produktinfo"):
        st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"]=pr_tx
        cur_data["produkt_info"]=pr_tx
        save_state()
        st.success("Produktinfo gemt.")

    # Filupload
    st.markdown("---")
    st.subheader("Upload CSV, XLSX, PDF til produktinfo")
    upf=st.file_uploader("Vælg fil", type=["csv","xlsx","pdf"])
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
        st.success("Data gemt i produktinfo.")

# ------ SEO-SIDE ------
elif st.session_state["page"]=="seo":
    st.header("Generér SEO-tekst (iterativ + blacklist-check)")

    data=st.session_state["profiles"].get(
        st.session_state["current_profile"],
        {"brand_profile":"","blacklist":"","produkt_info":""}
    )
    st.write("Virksomhedsprofil:")
    st.markdown(data.get("brand_profile","(ingen)"))

    malgruppe=st.selectbox("Målgruppe", ["B2C (forbrugere)","B2B (professionelle)","Design/fagligt interesserede","Andet"])
    formaal=st.selectbox("Formål med teksten", ["Salg/landingsside","Informativ blog","Branding/storytelling"])
    rel_soegeord=st.text_input("Relaterede søgeord (kommasepareret)", "")
    col_faq,col_meta,col_links,col_cta=st.columns(4)
    with col_faq:
        inc_faq=st.checkbox("Inkluder FAQ")
    with col_meta:
        inc_meta=st.checkbox("Meta-titel+beskrivelse")
    with col_links:
        inc_link=st.checkbox("Interne links")
    with col_cta:
        inc_cta=st.checkbox("CTA")

    min_len=st.number_input("Min. ordlængde (fx 700)", min_value=50, max_value=2000, value=700, step=50)
    out_fmt=st.selectbox("Output-format", ["Ren tekst","Markdown","HTML"])
    tone_options=["Neutral","Formel","Venlig","Entusiastisk","Humoristisk","Autoritær","Professionel"]
    tone=st.selectbox("Tone-of-voice", tone_options, 0)

    seo_key=st.text_input("Hoved-søgeord / emne", "")
    antal=st.selectbox("Antal SEO-tekster", list(range(1,11)), 0)

    if seo_key:
        if st.button("Generér SEO-tekst"):
            with st.spinner("Genererer SEO-tekst..."):
                for i in range(antal):
                    base_prompt=(
                        f"Skriv en SEO-optimeret tekst på dansk om '{seo_key}'. "
                        f"Formål: {formaal}, Målgruppe: {malgruppe}, Tone-of-voice: {tone}.\n"
                        f"Brug brandprofil: {data.get('brand_profile','')} og produktinfo: {data.get('produkt_info','')}.\n"
                        f"Sigt efter mindst {min_len} ord.\n"
                        "Undgå 'bæredygtighed'/'bæredygtig'.\n"
                        f"Relaterede søgeord: {rel_soegeord}.\n"
                    )
                    if inc_faq:
                        base_prompt+="Lav en FAQ-sektion med mindst 3 spørgsmål.\n"
                    if inc_meta:
                        base_prompt+="Tilføj en meta-titel (60 tegn) og meta-beskrivelse (160 tegn).\n"
                    if inc_link:
                        base_prompt+="Tilføj mindst 2 interne links.\n"
                    if inc_cta:
                        base_prompt+="Afslut med en tydelig CTA.\n"
                    if out_fmt=="HTML":
                        base_prompt+="Returnér HTML (<h2>, <p>...).\n"
                    elif out_fmt=="Markdown":
                        base_prompt+="Returnér i Markdown med ## overskrifter.\n"
                    else:
                        base_prompt+="Returnér som ren tekst.\n"

                    black_list_words=data.get("blacklist","")  # Brugerens liste, men IKKE vist i profil UI

                    # 1) generér iterativ -> min. ord
                    text_draft=generate_iterative_seo_text(base_prompt, min_len=min_len, max_tries=3)
                    # 2) fjern "### " fra output
                    text_draft=text_draft.replace("### ","")
                    # 3) check blacklist -> genskriv
                    final_txt=check_blacklist_and_rewrite(text_draft, black_list_words, max_tries=2)

                    st.session_state["generated_texts"].append(final_txt)
            save_state()

            if st.session_state["generated_texts"]:
                st.subheader("Dine SEO-tekster")
                cpy=st.session_state["generated_texts"][:]
                for i, doc in enumerate(cpy):
                    with st.expander(f"SEO-tekst {i+1}"):
                        st.text_area("Hele SEO-teksten", doc, height=600)
                        # download
                        file_ending=".txt"
                        mime_type="text/plain"
                        if out_fmt=="HTML":
                            file_ending=".html"
                            mime_type="text/html"
                        st.download_button(
                            label=f"Download SEO {i+1}",
                            data=doc,
                            file_name=f"seo_text_{i+1}{file_ending}",
                            mime=mime_type
                        )
                        if st.button(f"Slet tekst {i+1}", key=f"del_{i}"):
                            st.session_state["generated_texts"].pop(i)
                            save_state()
                            st.experimental_rerun()
