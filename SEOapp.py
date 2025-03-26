import streamlit as st
import os
import openai
import pandas as pd
import PyPDF2
import io
import json
import requests
from bs4 import BeautifulSoup

if os.path.exists("/mnt/data") and os.access("/mnt/data", os.W_OK):
    STATE_FILE = "/mnt/data/state.json"
else:
    STATE_FILE = "state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE,"r") as f:
                state = json.load(f)
            for k,v in state.items():
                st.session_state[k]=v
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
    to_save = {
        "profiles": st.session_state.get("profiles",{}),
        "api_key": st.session_state.get("api_key",""),
        "page": st.session_state.get("page","seo"),
        "generated_texts": st.session_state.get("generated_texts",[]),
        "current_profile": st.session_state.get("current_profile","Standard profil"),
        "delete_profile": st.session_state.get("delete_profile", None)
    }
    with open(STATE_FILE,"w") as f:
        json.dump(to_save,f)

def initialize_state():
    st.session_state["profiles"]={}
    st.session_state["api_key"]=""
    st.session_state["page"]="seo"
    st.session_state["generated_texts"]=[]
    st.session_state["current_profile"]="Standard profil"
    st.session_state["delete_profile"]=None
    save_state()

load_state()

import openai
import requests
from bs4 import BeautifulSoup

if not st.session_state.get("api_key"):
    key_in = st.text_input("Indtast OpenAI API-nøgle", type="password")
    if key_in:
        st.session_state["api_key"] = key_in
        save_state()
    else:
        st.stop()

openai.api_key = st.session_state["api_key"]

def fetch_website_content(url):
    try:
        r=requests.get(url,timeout=10)
        r.raise_for_status()
        soup=BeautifulSoup(r.text,"html.parser")
        for s in soup(["script","style"]):
            s.decompose()
        return soup.get_text(separator=' ',strip=True)
    except Exception as e:
        st.error(f"Fejl: {e}")
        return ""

def fetch_product_links(url):
    links=[]
    try:
        r=requests.get(url,timeout=10)
        r.raise_for_status()
        soup=BeautifulSoup(r.text,"html.parser")
        for a in soup.find_all("a",href=True):
            href=a["href"]
            if href.startswith("/products/"):
                full="https://noyer.dk"+href
                if full not in links:
                    links.append(full)
    except Exception as e:
        st.error(f"Fejl: {e}")
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
        st.error(f"Fejl: {e}")
        return ""

st.set_page_config(page_title="AI-assisteret SEO generator",layout="wide")

st.sidebar.header("Navigation")
if st.sidebar.button("Skriv SEO-tekst"):
    st.session_state["page"]="seo"
    save_state()

st.sidebar.markdown("---")
st.sidebar.header("Virksomhedsprofiler")

pnames=list(st.session_state["profiles"].keys())
for nm in pnames:
    c1,c2=st.sidebar.columns([4,1])
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
    prof_del=st.session_state["delete_profile"]
    st.sidebar.warning(f"Slet {prof_del}?")
    cc1,cc2=st.sidebar.columns(2)
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
    newp=f"Ny profil {len(pnames)+1}"
    st.session_state["profiles"][newp]={"brand_profile":"","blacklist":"","produkt_info":""}
    st.session_state["current_profile"]=newp
    st.session_state["page"]="profil"
    save_state()

cur_data=st.session_state["profiles"].get(
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

#-- PAGE: PROFIL
if st.session_state["page"]=="profil":
    st.header("Redigér virksomhedsprofil")
    cur_profile_name = st.text_input("Navn på virksomhedsprofil",
                                     value=st.session_state["current_profile"])
    if cur_profile_name != st.session_state["current_profile"]:
        old=st.session_state["current_profile"]
        if cur_profile_name.strip():
            st.session_state["profiles"][cur_profile_name]=st.session_state["profiles"].pop(old)
            st.session_state["current_profile"]=cur_profile_name
            cur_data=st.session_state["profiles"][cur_profile_name]
            save_state()

    st.subheader("AI-genereret virksomhedsprofil (uden bæredygtighed)")
    url_profile = st.text_input("URL til 'Om os'-side")
    if st.button("Hent og lav brandprofil med AI"):
        if url_profile:
            raw_txt=fetch_website_content(url_profile)
            if raw_txt:
                prompt=(
                    "Læs hjemmesideteksten herunder og skriv en fyldig virksomhedsprofil. "
                    "Må IKKE nævne 'bæredygtighed'. Returnér KUN profilteksten.\n\n"
                    f"{raw_txt[:7000]}"
                )
                try:
                    resp=openai.ChatCompletion.create(
                        model="gpt-4-turbo",
                        messages=[{"role":"user","content":prompt}],
                        max_tokens=1000
                    )
                    brand=resp.choices[0].message.content.strip()
                    st.session_state["profiles"][st.session_state["current_profile"]]["brand_profile"]=brand
                    cur_data["brand_profile"]=brand
                    save_state()
                    st.success("Virksomhedsprofil opdateret!")
                    st.text_area("Genereret profil",brand,height=150)
                except Exception as e:
                    st.error(f"Fejl ved AI: {e}")
            else:
                st.warning("Tom tekst fundet ved URL.")
        else:
            st.warning("Angiv en URL")

    st.subheader("Hent rå produkttekster")
    coll_url=st.text_input("URL til kollektion, fx https://noyer.dk/collections/all")
    if st.button("Hent produktlinks"):
        if coll_url.strip():
            found=fetch_product_links(coll_url.strip())
            st.session_state["collected_links"]=found
            st.write(f"Fandt {len(found)} links.")
        else:
            st.warning("Angiv kollektions-URL")

    chosen=[]
    if "collected_links" in st.session_state and st.session_state["collected_links"]:
        st.markdown("**Vælg produkter**")
        for i,lnk in enumerate(st.session_state["collected_links"]):
            val=st.checkbox(lnk,key=f"ch_{i}",value=True)
            if val:
                chosen.append(lnk)

        if st.button("Hent tekst fra valgte"):
            big_raw=""
            for c in chosen:
                txt=fetch_product_text_raw(c)
                big_raw+=f"\n\n=== PRODUKT ===\n{c}\n{txt}"
            st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"]=big_raw
            cur_data["produkt_info"]=big_raw
            save_state()
            st.success("Rå tekst gemt i produkt_info.")
            st.text_area("Rå tekst",big_raw,height=300)

    # Berig med AI men ikke for meget
    st.subheader("Berig produktinfo med AI")
    if st.button("Berig produktinfo"):
        raw_prods=cur_data.get("produkt_info","")
        if raw_prods.strip():
            prompt=(
                "Du får her en rå produkttekst. Strukturer og berig den med evt. manglende data "
                "men lad originalordlyden stå så vidt muligt. Fjern '**' og sæt ikke 'Produktbeskrivelse for'.\n\n"
                f"{raw_prods[:15000]}"
            )
            try:
                r2=openai.ChatCompletion.create(
                    model="gpt-4-turbo",
                    messages=[{"role":"user","content":prompt}],
                    max_tokens=3000
                )
                enriched=r2.choices[0].message.content.strip()
                # Filtrer "Produktbeskrivelse for" og "**"
                enriched=enriched.replace("Produktbeskrivelse for ","")
                enriched=enriched.replace("**","")

                st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"]=enriched
                cur_data["produkt_info"]=enriched
                save_state()
                st.success("Produktinfo beriget - uden ** og 'Produktbeskrivelse for'")
                st.text_area("Beriget produktinfo",enriched,height=300)
            except Exception as e:
                st.error(f"Fejl ved AI-berigelse: {e}")
        else:
            st.warning("Ingen rå produktinfo at berige. Hent først tekst.")

    st.subheader("Redigér profil manuelt")
    br_txt=st.text_area("Virksomhedsprofil",cur_data.get("brand_profile",""),height=150)
    if st.button("Gem profilændringer"):
        st.session_state["profiles"][st.session_state["current_profile"]]["brand_profile"]=br_txt
        cur_data["brand_profile"]=br_txt
        save_state()
        st.success("Profil opdateret manuelt.")

    st.subheader("Redigér produktinfo")
    pr_txt=st.text_area("Produktinfo",cur_data.get("produkt_info",""),height=150)
    if st.button("Gem produktinfo"):
        st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"]=pr_txt
        cur_data["produkt_info"]=pr_txt
        save_state()
        st.success("Produktinfo opdateret manuelt.")

    st.subheader("Ord/sætninger AI ikke må bruge (Blacklist)")
    bl=st.text_area("Bruges ved SEO (ikke rå hentning).",cur_data.get("blacklist",""))
    if st.button("Gem blacklist"):
        st.session_state["profiles"][st.session_state["current_profile"]]["blacklist"]=bl
        cur_data["blacklist"]=bl
        save_state()
        st.success("Blacklist gemt.")

    st.markdown("---")
    st.subheader("Upload filer (CSV, XLSX, PDF)")
    upf=st.file_uploader("Vælg fil",type=["csv","xlsx","pdf"])
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

#-- SEO PAGE
elif st.session_state["page"]=="seo":
    st.header("Generér SEO-tekst")
    data=st.session_state["profiles"].get(
        st.session_state["current_profile"],
        {"brand_profile":"","blacklist":"","produkt_info":""}
    )
    st.subheader("Virksomhedsprofil")
    st.markdown(data.get("brand_profile","Ingen profil"))

    seo_key=st.text_input("Søgeord / Emne")
    length=st.number_input("Antal ord",min_value=50,max_value=2000,value=300,step=50)
    tone=st.selectbox("Tone-of-voice",["Neutral","Formel","Venlig","Entusiastisk"],0)
    ant=st.selectbox("Antal tekster",list(range(1,11)),0)

    if seo_key:
        if st.button("Generér SEO-tekst"):
            with st.spinner("Genererer..."):
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
                        rseo=openai.ChatCompletion.create(
                            model="gpt-4-turbo",
                            messages=[{"role":"user","content":prompt}],
                            max_tokens=length*2
                        )
                        txt=rseo.choices[0].message.content.strip()
                        st.session_state["generated_texts"].append(txt)
                    except Exception as e:
                        st.error(f"Fejl: {e}")
            save_state()

            if st.session_state["generated_texts"]:
                st.subheader("Dine SEO-tekster")
                # Lav en kopi, så kun én slettes ad gangen
                cpy=st.session_state["generated_texts"][:]
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
