import streamlit as st
import openai
import pandas as pd
import PyPDF2
import io
import json  # Importér JSON-modulet for filhåndtering

st.set_page_config(page_title="AI-assisteret SEO generator", layout="wide")

# Funktion til at gemme profiler til en fil
def save_profiles_to_file():
    with open("profiles.json", "w") as f:
        json.dump(st.session_state["profiles"], f)

# Funktion til at læse profiler fra fil
def load_profiles_from_file():
    try:
        with open("profiles.json", "r") as f:
            st.session_state["profiles"] = json.load(f)
    except FileNotFoundError:
        st.session_state["profiles"] = {}

# Når appen starter, prøv at læse profiler fra filen
load_profiles_from_file()

if "api_key" not in st.session_state:
    st.session_state["api_key"] = ""
if "page" not in st.session_state:
    st.session_state["page"] = "seo"
if "generated_texts" not in st.session_state:
    st.session_state["generated_texts"] = []
if "rerun_flag" not in st.session_state:
    st.session_state["rerun_flag"] = False

if "current_profile" not in st.session_state:
    st.session_state["current_profile"] = "Standard profil"
    st.session_state["generated_texts"] = []

# API-nøgle
if not st.session_state["api_key"]:
    api_input = st.text_input("Indtast OpenAI API-nøgle", type="password")
    if api_input:
        st.session_state["api_key"] = api_input
        st.session_state["rerun_flag"] = True
        st.stop()
    else:
        st.stop()

client = openai.OpenAI(api_key=st.session_state["api_key"])

# Sidebar med navigation
st.sidebar.header("Navigation")
if st.sidebar.button("Skriv SEO-tekst"):
    st.session_state["page"] = "seo"
if st.sidebar.button("Redigér virksomhedsprofil"):
    st.session_state["page"] = "profil"

st.sidebar.markdown("---")
st.sidebar.header("Virksomhedsprofiler")

profile_names = list(st.session_state["profiles"].keys())
# Vis profiler som knapper med slet-funktion
for name in profile_names:
    col1, col2 = st.sidebar.columns([4, 1])
    with col1:
        if st.button(name, key=f"profile_btn_{name}"):
            st.session_state["current_profile"] = name
            st.session_state["page"] = "profil"
            st.session_state["rerun_flag"] = True
            st.experimental_rerun()
    with col2:
        if st.button("🗑", key=f"delete_{name}"):
            st.session_state["profiles"].pop(name)
            if st.session_state["current_profile"] == name:
                st.session_state["current_profile"] = "Standard profil"
            st.experimental_rerun()

if st.sidebar.button("Opret ny profil"):
    new_profile_name = f"Ny profil {len(profile_names) + 1}"
    st.session_state["profiles"][new_profile_name] = {"brand_profile": "", "blacklist": "", "produkt_info": ""}
    st.session_state["current_profile"] = new_profile_name
    st.session_state["page"] = "profil"
    st.experimental_rerun()

current_data = st.session_state["profiles"].get(st.session_state["current_profile"], {"brand_profile": "", "blacklist": "", "produkt_info": ""})
if current_data.get("brand_profile", "").strip():
    st.sidebar.markdown(current_data["brand_profile"])
else:
    st.sidebar.info("Ingen virksomhedsprofil fundet endnu.")

if st.session_state["page"] == "profil":
    current_profile_name = st.text_input("Navn på virksomhedsprofil:", value=st.session_state["current_profile"], key="profile_name_display")

    # Opdater navnet live
    if current_profile_name != st.session_state["current_profile"]:
        old_name = st.session_state["current_profile"]
        if current_profile_name.strip():
            st.session_state["profiles"][current_profile_name] = st.session_state["profiles"].pop(old_name)
            st.session_state["current_profile"] = current_profile_name
            current_data = st.session_state["profiles"][current_profile_name]
    st.subheader("Rediger virksomhedsprofil")
    profil_tekst = st.text_area("Redigér profil her:", current_data.get("brand_profile", ""), height=200)
    if st.button("Gem ændringer"):
        old_name = st.session_state["current_profile"]
        new_name = current_profile_name.strip()

        if new_name != old_name:
            old_data = st.session_state["profiles"].pop(old_name)
            st.session_state["profiles"][new_name] = old_data
            st.session_state["current_profile"] = new_name

        st.session_state["profiles"][st.session_state["current_profile"]]["brand_profile"] = profil_tekst
        st.success("Profil opdateret!")

    st.markdown("---")
    st.subheader("Ord/sætninger AI ikke må bruge")
    blacklist = st.text_area("Skriv ord eller sætninger adskilt med komma:", current_data.get("blacklist", ""))
    if st.button("Gem begrænsninger"):
        st.session_state["profiles"][st.session_state["current_profile"]]["blacklist"] = blacklist
        st.success("Begrænsninger gemt!")

    st.markdown("---")
    st.subheader("Upload eller indsæt produktdata")
    if 'produkt_data' not in st.session_state:
        st.session_state['produkt_data'] = None

    produkt_data = st.file_uploader("Upload CSV, Excel eller PDF", type=["csv", "xlsx", "pdf"], key=f"produkt_upload_{st.session_state['current_profile']}")

    if produkt_data:
        st.session_state['produkt_data'] = produkt_data
        st.session_state['profiles'][st.session_state['current_profile']]['produkt_info'] = ''
        st.write(f"🔄 Fil uploadet: {produkt_data.name}")
        extracted = ""
        if produkt_data.name.endswith(".csv"):
            df = pd.read_csv(produkt_data)
            extracted = df.to_string(index=False)
        elif produkt_data.name.endswith(".xlsx"):
            df = pd.read_excel(produkt_data)
            extracted = df.to_string(index=False)
        elif produkt_data.name.endswith(".pdf"):
            reader = PyPDF2.PdfReader(produkt_data)
            for page in reader.pages:
                extracted += page.extract_text()

        st.session_state['profiles'][st.session_state['current_profile']]['produkt_info'] = extracted
        current_data['produkt_info'] = extracted
        col1, col2 = st.columns([3, 1])
        with col1:
            generate = st.button("Generér SEO-tekst")
        with col2:
            antal = st.selectbox("Antal tekster", options=list(range(1, 11)), index=0)

        if generate:
            for i in range(antal):
                produkt_info = st.session_state.get('produkt_info', '')
                seo_prompt = (
                    f"Skriv en SEO-optimeret tekst på dansk om '{seo_keyword}'. "
                    f"Brug følgende virksomhedsprofil som reference: {current_data.get('brand_profile', '')}. "
                    f"Brug også følgende produktinformation: {current_data.get('produkt_info', '')}. "
                    f"Strukturer teksten med SEO-venlige overskrifter (h1, h2, h3) og brug relevante nøgleord i overskrifterne. "
                    f"Teksten skal være cirka {laengde} ord lang."
                )

                if tone:
                    seo_prompt += f" Teksten skal have en '{tone}' tone-of-voice."

                if current_data.get("blacklist", "").strip():
                    seo_prompt += f" Undgå følgende ord eller sætninger i teksten: {current_data['blacklist']}."

                seo_response = client.chat.completions.create(
                    model="gpt-4-turbo",
                    messages=[{"role": "user", "content": seo_prompt}],
                    max_tokens=laengde * 2
                )

                seo_text = seo_response.choices[0].message.content.strip()
                st.session_state["generated_texts"].append(seo_text)

        if st.session_state["generated_texts"]:
            st.subheader("Dine genererede SEO-tekster")
            for idx, txt in enumerate(st.session_state["generated_texts"]):
                with st.expander(f"SEO-tekst {idx+1}"):
                    st.markdown(txt, unsafe_allow_html=True)
                    st.download_button(f"Download tekst {idx+1}", txt, file_name=f"seo_tekst_{idx+1}.txt")
                    if st.button(f"❌ Slet tekst {idx+1}", key=f"delete_{idx}"):
                        st.session_state["generated_texts"].pop(idx)
                        st.experimental_rerun()
    else:
        st.info("Start med at oprette en virksomhedsprofil i sidepanelet for at kunne generere SEO-tekster.")
