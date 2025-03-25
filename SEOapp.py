import streamlit as st
import openai
import pandas as pd
import PyPDF2
import io

st.set_page_config(page_title="AI-assisteret SEO generator", layout="wide")

if "api_key" not in st.session_state:
    st.session_state["api_key"] = ""
if "page" not in st.session_state:
    st.session_state["page"] = "seo"

st.title("📝 Skriv SEO-tekster med AI")

# API-nøgle
if not st.session_state["api_key"]:
    api_input = st.text_input("Indtast OpenAI API-nøgle", type="password")
    if api_input:
        st.session_state["api_key"] = api_input
        st.experimental_rerun()
    st.stop()

client = openai.OpenAI(api_key=st.session_state["api_key"])

# Sidebar med navigation
st.sidebar.header("🔧 Navigation")
if st.sidebar.button("📝 Skriv SEO-tekst"):
    st.session_state["page"] = "seo"
if st.sidebar.button("✏️ Redigér virksomhedsprofil"):
    st.session_state["page"] = "profil"

st.sidebar.markdown("---")
st.sidebar.header("📁 Din virksomhedsprofil")
if "brand_profile" in st.session_state and st.session_state["brand_profile"].strip():
    st.sidebar.markdown(st.session_state["brand_profile"])
else:
    st.sidebar.info("Ingen virksomhedsprofil fundet endnu.")

if st.session_state["page"] == "profil":
    st.subheader("Rediger virksomhedsprofil")
    profil_tekst = st.text_area("Redigér profil her:", st.session_state.get("brand_profile", ""), height=200)
    if st.button("Gem ændringer"):
        st.session_state["brand_profile"] = profil_tekst
        st.success("Profil opdateret!")

    st.markdown("---")
    st.subheader("Upload eller indsæt produktdata")
    produkt_data = st.file_uploader("Upload CSV, Excel eller PDF", type=["csv", "xlsx", "pdf"])
    if produkt_data:
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

        st.text_area("Produktinformation:", extracted, height=200)

elif st.session_state["page"] == "seo":
    if "brand_profile" in st.session_state and st.session_state["brand_profile"].strip():
        st.subheader("Generér SEO-tekst")
        seo_keyword = st.text_input("SEO søgeord/emne for tekst")
        tone = st.text_input("Tone-of-voice (valgfri, fx: venlig, professionel, eksklusiv)")
        laengde = st.number_input("Ønsket tekstlængde (ord)", min_value=100, max_value=1500, value=300)

        if st.button("Generér SEO-tekst"):
            seo_prompt = (
                f"Skriv en SEO-optimeret tekst på dansk om '{seo_keyword}'. "
                f"Brug følgende virksomhedsprofil som reference: {st.session_state['brand_profile']}. "
                f"Strukturer teksten med SEO-venlige overskrifter (h1, h2, h3) og brug relevante nøgleord i overskrifterne. "
                f"Teksten skal være cirka {laengde} ord lang."
            )

            if tone:
                seo_prompt += f" Teksten skal have en '{tone}' tone-of-voice."

            seo_response = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[{"role": "user", "content": seo_prompt}],
                max_tokens=laengde * 2
            )

            seo_text = seo_response.choices[0].message.content.strip()
            st.text_area("Genereret SEO-tekst:", seo_text, height=400)

            if st.download_button("Download tekst", seo_text, "seo_tekst.txt"):
                st.success("Tekst downloadet!")
    else:
        st.info("Start med at oprette en virksomhedsprofil i sidepanelet for at kunne generere SEO-tekster.")
