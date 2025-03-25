import streamlit as st
import openai
import pandas as pd
import PyPDF2
import io

st.set_page_config(page_title="AI-assisteret SEO generator", layout="wide")

if "api_key" not in st.session_state:
    st.session_state["api_key"] = ""

st.title("AI-assisteret SEO-generator")

# API-nøgle
if not st.session_state["api_key"]:
    api_input = st.text_input("Indtast OpenAI API-nøgle", type="password")
    if api_input:
        st.session_state["api_key"] = api_input
        st.experimental_rerun()
    st.stop()

client = openai.OpenAI(api_key=st.session_state["api_key"])

# Upload materiale
st.header("Upload virksomheds- eller produktinformation")
uploaded_file = st.file_uploader("Upload en CSV-, Excel- eller PDF-fil med information om din virksomhed eller produkter", type=["csv", "xlsx", "pdf"])
extracted_text = ""

if uploaded_file:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
        extracted_text = df.to_string(index=False)
    elif uploaded_file.name.endswith(".xlsx"):
        df = pd.read_excel(uploaded_file)
        extracted_text = df.to_string(index=False)
    elif uploaded_file.name.endswith(".pdf"):
        reader = PyPDF2.PdfReader(uploaded_file)
        for page in reader.pages:
            extracted_text += page.extract_text()

if extracted_text:
    st.subheader("Uddraget tekst fra dit materiale")
    st.text_area("Ekstraheret tekst (redigér hvis nødvendigt)", extracted_text, height=200, key="raw_info")

    if st.button("Analyser og generér virksomhedsprofil med AI"):
        prompt = (
            "Du er en brandingekspert. Brug følgende tekstuddrag til at generere en virksomhedsprofil. "
            "Inkludér brandets kerneværdier, målgruppe, produkttype og en tone-of-voice. "
            f"Her er teksten: {st.session_state['raw_info']}"
        )
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500
        )
        st.session_state["brand_profile"] = response.choices[0].message.content.strip()
        st.success("Profil genereret! Du kan rette den nedenfor.")

# Redigering og SEO-tekstgenerering
if "brand_profile" in st.session_state:
    st.subheader("Virksomhedens profil")
    edited_profile = st.text_area("Virksomhedsprofil:", st.session_state["brand_profile"], height=200)

    if st.button("Opdater profil"):
        st.session_state["brand_profile"] = edited_profile
        st.success("Profil opdateret!")

    st.markdown("---")

    seo_keyword = st.text_input("SEO søgeord/emne for tekst")
    laengde = st.number_input("Ønsket tekstlængde (ord)", min_value=100, max_value=1500, value=300)

    if st.button("Generér SEO-tekst"):
        seo_prompt = (
            f"Skriv en SEO-optimeret tekst på dansk om '{seo_keyword}'. "
            f"Brug følgende virksomhedsprofil som reference: {st.session_state['brand_profile']}. "
            f"Teksten skal være cirka {laengde} ord lang."
        )

        seo_response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": seo_prompt}],
            max_tokens=laengde * 2
        )

        seo_text = seo_response.choices[0].message.content.strip()
        st.text_area("Genereret SEO-tekst:", seo_text, height=400)

        if st.download_button("Download tekst", seo_text, "seo_tekst.txt"):
            st.success("Tekst downloadet!")
