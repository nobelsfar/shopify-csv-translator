import streamlit as st

# SKAL være allerførst
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
            for k, v in s.items():
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
    to_save = {
        "profiles": st.session_state.get("profiles", {}),
        "api_key": st.session_state.get("api_key", ""),
        "page": st.session_state.get("page", "seo"),
        "generated_texts": st.session_state.get("generated_texts", []),
        "current_profile": st.session_state.get("current_profile", "Standard profil"),
        "delete_profile": st.session_state.get("delete_profile", None)
    }
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(to_save, f)
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
    key_in = st.text_input("Indtast OpenAI API-nøgle", type="password")
    if key_in:
        st.session_state["api_key"] = key_in
        save_state()
    else:
        st.stop()

openai.api_key = st.session_state["api_key"]

def fetch_website_content(url):
    """Henter sideindhold som ren tekst, fjerner script/style."""
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for s in soup(["script", "style"]):
            s.decompose()
        return soup.get_text(separator=' ', strip=True)
    except Exception as e:
        st.error(f"Fejl ved {url}: {e}")
        return ""

def fetch_product_links(url):
    links = []
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if href.startswith("/products/"):
                full = "https://noyer.dk" + href
                if full not in links:
                    links.append(full)
    except Exception as e:
        st.error(f"Fejl ved produktlinks: {e}")
    return links

def fetch_product_text_raw(url):
    try:
        rr = requests.get(url, timeout=10)
        rr.raise_for_status()
        soup = BeautifulSoup(rr.text, "html.parser")
        desc = soup.select_one(".product-info__description")
        if desc:
            return desc.get_text(separator=' ', strip=True)
        else:
            return soup.get_text(separator=' ', strip=True)
    except Exception as e:
        st.error(f"Fejl ved henting produktside: {e}")
        return ""

def automatically_enrich_product_text(raw_text):
    if not raw_text.strip():
        return ""
    prompt = (
        "Du får her en rå produkttekst. Strukturer og berig den let (tilføj evt. manglende data). "
        "Undgå store markdown-overskrifter (###) og 'Produktbeskrivelse for'. "
        "Undgå at ændre for meget i ordlyden.\n\n" +
        raw_text[:15000]
    )
    try:
        r2 = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=3000
        )
        enriched = r2.choices[0].message.content.strip()
        enriched = enriched.replace("Produktbeskrivelse for ", "")
        enriched = re.sub(r'^###\s+(.*)$', r'\1', enriched, flags=re.MULTILINE)
        return enriched
    except Exception as e:
        st.error(f"Fejl ved berigelse: {e}")
        return raw_text

def count_words(txt):
    return len(txt.split())

def generate_iterative_seo_text(base_prompt, min_len=700, max_tries=3):
    final_text = ""
    resp = openai.ChatCompletion.create(
        model="gpt-4-turbo",
        messages=[{"role": "user", "content": base_prompt}],
        max_tokens=min_len * 3  # Øget fra *2 til *3
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
                "Uddyb og tilføj ekstra afsnit, eksempler, FAQ osv.:\n\n" +
                final_text
            )
            r2 = openai.ChatCompletion.create(
                model="gpt-4-turbo",
                messages=[{"role": "user", "content": ext_prompt}],
                max_tokens=min_len * 3  # Øget fra *2 til *3
            )
            new_text = r2.choices[0].message.content.strip()
            w2 = count_words(new_text)
            if w2 >= min_len:
                final_text = new_text
                break
            else:
                final_text = new_text
                wcount = w2
    return final_text

def check_blacklist_and_rewrite(text, blacklist_words, max_tries=2):
    if not blacklist_words.strip():
        return text

    words_list = [w.strip().lower() for w in blacklist_words.split(",") if w.strip()]

    def contains_blacklist(t):
        lower_t = t.lower()
        for w in words_list:
            if w in lower_t:
                return True
        return False

    final_text = text
    for attempt in range(max_tries):
        if not contains_blacklist(final_text):
            break
        found = []
        low = final_text.lower()
        for w in words_list:
            if w in low:
                found.append(w)
        rewrite_prompt = (
            f"Nogle forbudte ord blev brugt: {found}. Fjern eller omformuler dem, "
            "uden at forkorte teksten væsentligt:\n\n" +
            final_text
        )
        r3 = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": rewrite_prompt}],
            max_tokens=max(300, len(final_text.split()) * 4)  # Øget fra *3 til *4
        )
        final_text = r3.choices[0].message.content.strip()
    return final_text

# -- NYE FUNKTIONER TIL MULTI-AGENT PROCESSEN --

def generate_initial_draft(prompt, min_len=700, max_tries=3):
    return generate_iterative_seo_text(prompt, min_len, max_tries)

def humanize_text(text):
    humanize_prompt = (
        "Forbedr følgende tekst, så den lyder mere naturlig og menneskelig, "
        "og juster tone og flow uden at ændre på det centrale indhold:\n\n" + text
    )
    response = openai.ChatCompletion.create(
        model="gpt-4-turbo",
        messages=[{"role": "user", "content": humanize_prompt}],
        max_tokens=max(300, len(text.split()) * 4)  # Øget fra *3 til *4
    )
    return response.choices[0].message.content.strip()

def enhance_seo_text(text, rel_soegeord, extra_instructions):
    seo_prompt = (
        "Forbedr SEO-optimeringen af følgende tekst ved at integrere de relaterede søgeord: " + rel_soegeord + ". " +
        extra_instructions +
        "Her er teksten:\n\n" + text
    )
    response = openai.ChatCompletion.create(
        model="gpt-4-turbo",
        messages=[{"role": "user", "content": seo_prompt}],
        max_tokens=max(300, len(text.split()) * 4)  # Øget fra *3 til *4
    )
    return response.choices[0].message.content.strip()

# -- SIDEBAR
st.sidebar.header("Navigation")
if st.sidebar.button("Skriv SEO-tekst"):
    st.session_state["page"] = "seo"
    save_state()

st.sidebar.markdown("---")
st.sidebar.header("Virksomhedsprofiler")

pnames = list(st.session_state["profiles"].keys())
for nm in pnames:
    c1, c2 = st.sidebar.columns([4, 1])
    with c1:
        if st.button(nm, key=f"pf_{nm}"):
            st.session_state["current_profile"] = nm
            st.session_state["page"] = "profil"
            save_state()
    with c2:
        if st.button("🗑", key=f"del_{nm}"):
            st.session_state["delete_profile"] = nm
            save_state()

if st.session_state.get("delete_profile"):
    prof_del = st.session_state["delete_profile"]
    st.sidebar.warning(f"Slet profil '{prof_del}'?")
    cc1, cc2 = st.sidebar.columns(2)
    with cc1:
        if st.button("Ja, slet"):
            st.session_state["profiles"].pop(prof_del, None)
            if st.session_state["current_profile"] == prof_del:
                st.session_state["current_profile"] = "Standard profil"
            st.session_state["delete_profile"] = None
            save_state()
    with cc2:
        if st.button("Nej"):
            st.session_state["delete_profile"] = None
            save_state()

if st.sidebar.button("Opret ny profil"):
    newp = f"Ny profil {len(pnames) + 1}"
    st.session_state["profiles"][newp] = {"brand_profile": "", "blacklist": "", "produkt_info": ""}
    st.session_state["current_profile"] = newp
    st.session_state["page"] = "profil"
    save_state()

cur_data = st.session_state["profiles"].get(
    st.session_state["current_profile"],
    {"brand_profile": "", "blacklist": "", "produkt_info": ""}
)

if cur_data.get("brand_profile", "").strip():
    st.sidebar.markdown(cur_data["brand_profile"])
else:
    st.sidebar.info("Ingen virksomhedsprofil fundet.")

if not st.session_state.get("page"):
    st.session_state["page"] = "profil"
    save_state()

# ==== PROFIL-SIDE ====
if st.session_state["page"] == "profil":
    st.header("Redigér virksomhedsprofil")

    cpname = st.text_input("Navn på virksomhedsprofil", value=st.session_state["current_profile"])
    if cpname != st.session_state["current_profile"]:
        oldn = st.session_state["current_profile"]
        if cpname.strip():
            st.session_state["profiles"][cpname] = st.session_state["profiles"].pop(oldn)
            st.session_state["current_profile"] = cpname
            cur_data = st.session_state["profiles"][cpname]
            save_state()

    # Hent AI-genereret brandprofil
    st.subheader("Hent AI-genereret brandprofil (uden 'bæredygtighed')")
    links_text = st.text_area("Indsæt ét link pr. linje til sider med virksomhedsinfo")
    if st.button("Generér brandprofil"):
        lines = links_text.strip().split("\n")
        all_content = ""
        for line in lines:
            line = line.strip()
            if line:
                page_txt = fetch_website_content(line)
                if page_txt:
                    all_content += f"\n\n=== KILDE: {line} ===\n{page_txt}"
        if all_content.strip():
            brand_prompt = (
                "Her er tekst fra flere links. Lav en fyldig virksomhedsprofil "
                "uden at nævne 'bæredygtighed'. Returnér KUN selve profilteksten.\n\n" +
                all_content[:12000]
            )
            try:
                rp = openai.ChatCompletion.create(
                    model="gpt-4-turbo",
                    messages=[{"role": "user", "content": brand_prompt}],
                    max_tokens=2000
                )
                brandp = rp.choices[0].message.content.strip()
                st.session_state["profiles"][st.session_state["current_profile"]]["brand_profile"] = brandp
                cur_data["brand_profile"] = brandp
                save_state()
                st.success("Virksomhedsprofil opdateret!")
                st.text_area("Virksomhedsprofil (AI)", brandp, height=150)
            except Exception as e:
                st.error(f"Fejl ved AI: {e}")
        else:
            st.warning("Fandt ingen tekst ved link(s).")

    st.subheader("Hent produktinfo (auto-berig)")
    coll_url = st.text_input("URL til kollektion, fx noyer.dk/collections/all")
    if st.button("Hent produktlinks"):
        if coll_url.strip():
            found_links = fetch_product_links(coll_url.strip())
            st.session_state["collected_links"] = found_links
            st.write(f"Fandt {len(found_links)} links.")
        else:
            st.warning("Angiv URL")

    chosen = []
    if "collected_links" in st.session_state and st.session_state["collected_links"]:
        st.write("Vælg produkter at hente:")
        for i, lnk in enumerate(st.session_state["collected_links"]):
            cv = st.checkbox(lnk, key=f"cb_{i}", value=True)
            if cv:
                chosen.append(lnk)
        if st.button("Hent valgte (auto-berig)"):
            big_raw = ""
            for c_link in chosen:
                rawp = fetch_product_text_raw(c_link)
                big_raw += f"\n\n=== PRODUKT ===\n{c_link}\n{rawp}"
            if big_raw.strip():
                final = automatically_enrich_product_text(big_raw)
                st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"] = final
                cur_data["produkt_info"] = final
                save_state()
                st.success("Produktinfo hentet + beriget!")
                st.text_area("Produktinfo", final, height=300)
            else:
                st.warning("Ingen tekst at berige.")

    st.subheader("Virksomhedsprofil (manuel redigering)")
    brand_man = st.text_area("Indtast eller rediger virksomhedsprofil", cur_data.get("brand_profile", ""), height=100)
    if st.button("Gem virksomhedsprofil (manuel)"):
        st.session_state["profiles"][st.session_state["current_profile"]]["brand_profile"] = brand_man
        cur_data["brand_profile"] = brand_man
        save_state()
        st.success("Virksomhedsprofil gemt")
    
    # --- Nyt blacklist-felt ---
    st.subheader("Blacklist (forbudte ord)")
    default_blacklist = str(cur_data.get("blacklist") or "")
    blacklist_text = st.text_area(
        "Indtast kommaseparerede ord, der ikke må indgå i SEO-teksten.",
        value=default_blacklist,
        height=68
    )
    if st.button("Gem blacklist"):
        st.session_state["profiles"][st.session_state["current_profile"]]["blacklist"] = blacklist_text
        cur_data["blacklist"] = blacklist_text
        save_state()
        st.success("Blacklist gemt")

    st.subheader("Produktinfo (manuel)")
    prod_man = st.text_area("Indtast eller rediger produktinfo", cur_data.get("produkt_info", ""), height=150)
    if st.button("Gem produktinfo (manuel)"):
        st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"] = prod_man
        cur_data["produkt_info"] = prod_man
        save_state()
        st.success("Produktinfo gemt")

    st.markdown("---")
    st.subheader("Upload CSV, XLSX, PDF til produktinfo")
    upf = st.file_uploader("Vælg fil", type=["csv", "xlsx", "pdf"])
    if upf:
        st.write(f"Filen {upf.name} uploadet.")
        extracted = ""
        if upf.name.endswith(".csv"):
            df = pd.read_csv(upf)
            extracted = df.to_string(index=False)
        elif upf.name.endswith(".xlsx"):
            df = pd.read_excel(upf)
            extracted = df.to_string(index=False)
        elif upf.name.endswith(".pdf"):
            reader = PyPDF2.PdfReader(upf)
            for pg in reader.pages:
                extracted += pg.extract_text()
        st.session_state["profiles"][st.session_state["current_profile"]]["produkt_info"] = extracted
        cur_data["produkt_info"] = extracted
        save_state()
        st.success("Data gemt i produktinfo.")

# ---- SEO-SIDE ----
elif st.session_state["page"] == "seo":
    st.header("Generér SEO-tekst (HTML + forhåndsvisning)")

    data = st.session_state["profiles"].get(
        st.session_state["current_profile"],
        {"brand_profile": "", "blacklist": "", "produkt_info": ""}
    )

    st.write("Virksomhedsprofil:")
    st.markdown(data.get("brand_profile", "(ingen)"))

    malgruppe = st.selectbox("Målgruppe", ["B2C (forbrugere)", "B2B (professionelle)", "Design/fagligt interesserede", "Andet"])
    formaal = st.selectbox("Formål", ["Salg/landingsside", "Informativ blog", "Branding/storytelling"])
    rel_soegeord = st.text_input("Relaterede søgeord (kommasep)", "")
    cfaq, cmeta, cints, ccta = st.columns(4)
    with cfaq:
        inc_faq = st.checkbox("Inkluder FAQ")
    with cmeta:
        inc_meta = st.checkbox("Meta-titel+beskrivelse")
    with cints:
        inc_links = st.checkbox("Interne links")
    with ccta:
        inc_cta = st.checkbox("CTA")

    min_len = st.number_input("Min. ordlængde", min_value=50, max_value=2000, value=700, step=50)
    tone_opts = ["Neutral", "Formel", "Venlig", "Entusiastisk", "Humoristisk", "Autoritær", "Professionel"]
    tone = st.selectbox("Tone-of-voice", tone_opts, 0)

    seo_key = st.text_input("Hoved-søgeord / emne", "")
    antal = st.selectbox("Antal SEO-tekster", list(range(1, 11)), 0)

    if seo_key:
        if st.button("Generér SEO-tekst"):
            with st.spinner("Genererer SEO-tekst..."):
                for i in range(antal):
                    # Byg basisprompt ud fra de valgte indstillinger
                    base_prompt = (
                        f"Skriv en SEO-optimeret tekst på dansk om '{seo_key}'.\n"
                        f"Formål: {formaal}, Målgruppe: {malgruppe}, Tone-of-voice: {tone}.\n"
                        f"Brug brandprofil: {data.get('brand_profile', '')} og produktinfo: {data.get('produkt_info', '')}.\n"
                        f"Min. {min_len} ord.\n"
                        "Undgå 'bæredygtighed'/'bæredygtig'.\n"
                        f"Relaterede søgeord: {rel_soegeord}.\n"
                        "Returnér i HTML med <h2>, <h3>, <h4> overskrifter.\n"
                    )
                    if inc_faq:
                        base_prompt += "Lav en FAQ-sektion med mindst 3 spørgsmål.\n"
                    if inc_meta:
                        base_prompt += "Tilføj meta-titel (60 tegn) og meta-beskrivelse (160 tegn).\n"
                    if inc_links:
                        base_prompt += "Tilføj mindst 2 interne links.\n"
                    if inc_cta:
                        base_prompt += "Afslut med en tydelig CTA.\n"

                    # 1) Generer første udkast
                    initial_draft = generate_initial_draft(base_prompt, min_len=min_len)
                    # 2) Humaniser teksten
                    humanized = humanize_text(initial_draft)
                    
                    # Saml ekstra instruktioner ud fra de markerede indstillinger
                    extra_instructions = ""
                    if inc_faq:
                        extra_instructions += "Tilføj en FAQ-sektion med mindst 3 spørgsmål. "
                    if inc_meta:
                        extra_instructions += "Tilføj meta-titel (60 tegn) og meta-beskrivelse (160 tegn). "
                    if inc_links:
                        extra_instructions += "Tilføj mindst 2 interne links. "
                    if inc_cta:
                        extra_instructions += "Afslut med en tydelig CTA. "
                    
                    # 3) Forfin SEO-elementer med de ekstra instruktioner
                    enhanced_seo = enhance_seo_text(humanized, rel_soegeord, extra_instructions)
                    # 4) Kør blacklist-check
                    final_txt = check_blacklist_and_rewrite(enhanced_seo, data.get("blacklist", ""), max_tries=2)
                    
                    st.session_state["generated_texts"].append(final_txt)
            save_state()

            if st.session_state["generated_texts"]:
                st.subheader("Dine SEO-tekster - forhåndsvisning (HTML)")
                cpy = st.session_state["generated_texts"][:]
                for idx, doc in enumerate(cpy):
                    with st.expander(f"SEO-tekst {idx+1}"):
                        st.markdown(doc, unsafe_allow_html=True)
                        st.download_button(
                            label=f"Download SEO {idx+1} (HTML)",
                            data=doc,
                            file_name=f"seo_{idx+1}.html",
                            mime="text/html"
                        )
                        if st.button(f"Slet tekst {idx+1}", key=f"del_{idx}"):
                            st.session_state["generated_texts"].pop(idx)
                            save_state()
                            st.experimental_rerun()
