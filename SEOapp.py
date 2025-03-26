import streamlit as st

# VIGTIGT: set_page_config SKAL være første Streamlit-kald
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

# Vælg korrekt state-fil sti (Streamlit Cloud / lokalt)
if os.path.exists("/mnt/data") and os.access("/mnt/data", os.W_OK):
    STATE_FILE = "/mnt/data/state.json"
else:
    STATE_FILE = "state.json"

def load_state():
    """Loader eventuelt gemt session_state fra STATE_FILE."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                s = json.load(f)
            for k,v in s.items():
                st.session_state[k]=v
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
            st.error("Fejl ved oprettelse af mappe til state")
    to_save = {
        "profiles":st.session_state.get("profiles",{}),
        "api_key":st.session_state.get("api_key",""),
        "page":st.session_state.get("page","seo"),
        "generated_texts":st.session_state.get("generated_texts",[]),
        "current_profile":st.session_state.get("current_profile","Standard profil"),
        "delete_profile":st.session_state.get("delete_profile",None)
    }
    try:
        with open(STATE_FILE,"w") as f:
            json.dump(to_save,f)
    except:
        st.error("Fejl ved gemning af state.")

def initialize_state():
    """Initierer session_state med standardværdier."""
    st.session_state["profiles"]={}
    st.session_state["api_key"]=""
    st.session_state["page"]="seo"
    st.session_state["generated_texts"]=[]
    st.session_state["current_profile"]="Standard profil"
    st.session_state["delete_profile"]=None
    save_state()

load_state()

if not st.session_state.get("api_key"):
    key_in = st.text_input("Indtast OpenAI API-nøgle", type="password")
    if key_in:
        st.session_state["api_key"]=key_in
        save_state()
    else:
        st.stop()

openai.api_key = st.session_state["api_key"]

def fetch_website_content(url):
    """Henter rå tekst fra en URL og fjerner script/style."""
    try:
        r = requests.get(url,timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text,"html.parser")
        for s in soup(["script","style"]):
            s.decompose()
        return soup.get_text(separator=' ', strip=True)
    except Exception as e:
        st.error(f"Fejl ved hentning af hjemmesideindhold: {e}")
        return ""

def fetch_product_links(url):
    """Finder /products/ -links på en kollektionsside, uden dubletter."""
    links=[]
    try:
        r=requests.get(url,timeout=10)
        r.raise_for_status()
        soup=BeautifulSoup(r.text,"html.parser")
        for a_tag in soup.find_all("a", href=True):
            href=a_tag["href"]
            if href.startswith("/products/"):
                full="https://noyer.dk"+href
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
        r=requests.get(url,timeout=10)
        r.raise_for_status()
        soup=BeautifulSoup(r.text,"html.parser")
        desc = soup.select_one(".product-info__description")
        if desc:
            return desc.get_text(separator=' ',strip=True)
        else:
            return soup.get_text(separator=' ',strip=True)
    except Exception as e:
        st.error(f"Fejl ved hentning af {url}: {e}")
        return ""

def automatically_enrich_product_text(raw_text):
    """
    Kalder GPT for at strukturere og let udvide produkt-teksten,
    uden separate knapper. Undgår '###' overskrifter, 
    og fjerner 'Produktbeskrivelse for '.
    """
    if not raw_text.strip():
        return ""
    prompt=(
        "Du får her en rå produkttekst. Strukturer og berig den let (tilføj evt. manglende data), "
        "men undgå store markdown-overskrifter (###). Brug i stedet fed skrift **. "
        "Fjern 'Produktbeskrivelse for ' hvis det findes, "
        "og undgå at ændre for meget i ordlyden.\n\n"
        f"{raw_text[:15000]}"
    )
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[{"role":"user","content":prompt}],
            max_tokens=3000
        )
        enriched=resp.choices[0].message.content.strip()
        # Fjern 'Produktbeskrivelse for '
        enriched = enriched.replace("Produktbeskrivelse for ","")
        # Erstat ### Overskrift -> **overskrift**
        enriched = re.sub(r'^###\s+(.*)$', r'**\1**', enriched, flags=re.MULTILINE)
        return enriched
    except Exception as e:
        st.error(f"Fejl ved berigelse: {e}")
        return raw_text  # fallback

# --- Sidebar Navigation ---
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
        if st.button(nm, key=f"profile_{nm}"):
            st.session_state["current_profile"]=nm
            st.session_state["page"]="profil"
            save_state()
    with c2:
        if st.button("🗑", key=f"delete_{nm}"):
            st.session_state["delete_profile"]=nm
            save_state()

if st.session_state.get("delete_profile"):
    prof_del=st.session_state["delete_profile"]
    st.sidebar.warning(f"Er du sikker på at du vil slette '{prof_del}'?")
    cc1, cc2 = st.sidebar.columns(2)
    with cc1:
        if st.button("Ja, slet"):
            st.session_state["profiles"].pop(prof_del,None)
            if st.session_state["current_profile"]==prof_del:
                st.session_state["current_profile"]="Standard profil"
            st.session_state["delete_profile"]=None
            save_state()
    with cc2:
        if st.button("Nej"):
            st.session_state["delete_profile"]=None
            save_state()

if st.sidebar.button("Opret ny profil"):
    newp = f"Ny profil {len(profile_names)+1}"
    st.session_state["profiles"][newp] = {"brand_profile":"","blacklist":"","produkt_info":""}
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
    st.session_state["page"] = "profil"
    save_state()

# == PROFIL-SIDE
if st.session_state["page"]=="profil":
    st.header("Redigér virksomhedsprofil")

    current_profile_name = st.text_input("Navn på virksomhedsprofil",
                                         value=st.session_state["current_profile"])
    if current_profile_name != st.session_state["current_profile"]:
        old_name = st.session_state["current_profile"]
        if current_profile_name.strip():
            st.session_state["profiles"][current_profile_name] = st.session_state["profiles"].pop(old_name)
            st.session_state["current_profile"] = current_profile_name
            cur_data = st.session_state["profiles"][current_profile_name]
            save_state()

    # --- AI-baseret brandprofil (uden bæredygtighed)
    st.subheader("AI-genereret virksomhedsprofil (uden 'bæredygtighed')")
    url_profile = st.text_input("URL til fx 'Om os'-side")
    if st.button("Hent og lav brandprofil med AI"):
        if url_profile:
            raw_txt = fetch_website_content(url_profile)
            if raw_txt:
                prompt = (
                    "Læs hjemmesideteksten herunder og skriv en fyldig virksomhedsprofil. "
                    "Du må IKKE nævne ordet 'bæredygtighed'. Returnér KUN profilteksten.\n\n"
                    f"{raw_txt[:7000]}"
                )
                try:
                    resp = openai.ChatCompletion.create(
                        model="gpt-4-turbo",
                        messages=[{"role":"user","content":prompt}],
                        max_tokens=1000
                    )
                    brand = resp.choices[0].message.content.strip()
                    st.session_state["profiles"][st.session_state["current_profile"]]["brand_profile"]=brand
                    cur_data["brand_profile"]=brand
                    save_state()
                    st.success("Virksomhedsprofil opdateret (uden bæredygtighed)!")
                    st.text_area("Genereret profil", brand, height=150)
                except Exception as e:
                    st.error(f"Fejl ved AI: {e}")
            else:
                st.warning("Tom tekst fundet ved URL.")
        else:
            st.warning("Angiv en URL.")

    # --- Hent produkttekster (automatisk beriget)
    st.subheader("Hent produkttekster (automatisk beriget)")
    coll_url = st.text_input("URL til kollektion (fx https://noyer.dk/collections/all)")

    if st.button("Hent produktlinks"):
        if coll_url.strip():
            found = fetch_product_links(coll_url.strip())
            st.session_state["collected_links"] = found
            st.write(f"Fandt {len(found)} unikke produktlinks.")
        else:
            st.warning("Angiv en kollektions-URL.")

    chosen=[]
    if "collected_links" in st.session_state and st.session_state["collected_links"]:
        st.markdown("**Vælg produkter at hente**")
        for i, link in enumerate(st.session_state["collected_links"]):
            val = st.checkbox(link, key=f"chbox_{i}", value=True)
            if val:
                chosen.append(link)

        # Alt sker her, ingen separat berig-knap
        if st.button("Hent tekst (og berig) fra valgte produkter"):
            big_raw=""
            for c_link in chosen:
                raw_prod_txt = fetch_product_text_raw(c_link)
                big_raw += f"\n\n=== PRODUKT ===\n{c_link}\n{raw_prod_txt}"

            if big_raw.strip():
                # Kald GPT for at "berige"
                enriched_text = automatically_enrich_product_text(big_raw)
                st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"] = enriched_text
                cur_data["produkt_info"] = enriched_text
                save_state()
                st.success("Rå tekst hentet og automatisk beriget!")
                st.text_area("Beriget produktinfo", enriched_text, height=300)
            else:
                st.warning("Ingen tekst at berige – linklisten kan være tom.")

    # -- Redigér profil manuelt
    st.subheader("Redigér profil manuelt")
    br_txt=st.text_area("Virksomhedsprofil", cur_data.get("brand_profile",""), height=150)
    if st.button("Gem ændringer i profil"):
        st.session_state["profiles"][st.session_state["current_profile"]]["brand_profile"] = br_txt
        cur_data["brand_profile"] = br_txt
        save_state()
        st.success("Profil opdateret manuelt.")

    # -- Redigér produktinfo
    st.subheader("Redigér produktinfo (beriget tekst)")
    pr_txt = st.text_area("Produktinfo", cur_data.get("produkt_info",""), height=150)
    if st.button("Gem produktinfo"):
        st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"] = pr_txt
        cur_data["produkt_info"] = pr_txt
        save_state()
        st.success("Produktinfo opdateret manuelt.")

    st.subheader("Ord/sætninger AI ikke må bruge (Blacklist)")
    bl = st.text_area("Bruges ved SEO-generering, ikke rå hentning", cur_data.get("blacklist",""), height=80)
    if st.button("Gem blacklist"):
        st.session_state["profiles"][st.session_state["current_profile"]]["blacklist"]=bl
        cur_data["blacklist"]=bl
        save_state()
        st.success("Blacklist gemt.")

    # Upload fil
    st.markdown("---")
    st.subheader("Upload filer (CSV, XLSX, PDF)")
    upf = st.file_uploader("Vælg fil", type=["csv","xlsx","pdf"])
    if upf:
        st.write(f"Filen {upf.name} uploadet.")
        ex=""
        if upf.name.endswith(".csv"):
            df=pd.read_csv(upf)
            ex=df.to_string(index=False)
        elif upf.name.endswith(".xlsx"):
            df=pd.read_excel(upf)
            ex=df.to_string(index=False)
        elif upf.name.endswith(".pdf"):
            reader=PyPDF2.PdfReader(upf)
            for page in reader.pages:
                ex+=page.extract_text()
        st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"]=ex
        cur_data["produkt_info"]=ex
        save_state()
        st.success("Data gemt fra fil.")

# -- SEO PAGE --
elif st.session_state["page"]=="seo":
    st.header("Generér SEO-tekst")
    data = st.session_state["profiles"].get(
        st.session_state["current_profile"],
        {"brand_profile":"","blacklist":"","produkt_info":""}
    )
    st.subheader("Virksomhedsprofil")
    st.markdown(data.get("brand_profile","Ingen profil."))

    seo_key = st.text_input("Søgeord / emne")
    length = st.number_input("Antal ord (længde)", min_value=50,max_value=2000,value=300,step=50)
    tone = st.selectbox("Tone-of-voice",["Neutral","Formel","Venlig","Entusiastisk"],0)
    ant = st.selectbox("Antal tekster", list(range(1,11)),0)

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
                        f"Teksten skal være ca. {length} ord."
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
                        st.error(f"Fejl ved SEO AI: {e}")
            save_state()

            if st.session_state["generated_texts"]:
                st.subheader("Dine SEO-tekster")
                cpy = st.session_state["generated_texts"][:]
                for i,tex in enumerate(cpy):
                    with st.expander(f"SEO-tekst {i+1}"):
                        st.markdown(tex,unsafe_allow_html=True)
                        st.download_button(
                            label=f"Download SEO {i+1}",
                            data=tex,
                            file_name=f"seo_text_{i+1}.html",
                            mime="text/html"
                        )
                        if st.button(f"Slet {i+1}",key=f"del_{i}"):
                            st.session_state["generated_texts"].pop(i)
                            save_state()
                            st.experimental_rerun()
