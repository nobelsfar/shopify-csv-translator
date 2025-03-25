import streamlit as st
import openai

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

# Initial opsætning af brand-profil
if "brand_profile" not in st.session_state:
    st.header("Opsætning af din virksomhedsprofil")

    dna = st.text_area("Kort beskrivelse af din virksomheds DNA og målgruppe")
    produkter = st.text_area("Hvilke typer produkter sælger du?")
    tone = st.selectbox("Foretrukken tone-of-voice", ["Professionel", "Informativ", "Inspirerende", "Humoristisk", "Salg"])

    if st.button("Generér virksomhedsprofil"):
        prompt = (
            f"Udarbejd en kort, klar profiltekst for en virksomhed med følgende DNA: '{dna}', "
            f"som sælger '{produkter}' med en '{tone}' tone-of-voice."
        )
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )
        st.session_state["brand_profile"] = response.choices[0].message.content.strip()
        st.success("Profil genereret! Du kan rette nedenfor.")
        st.experimental_rerun()

else:
    st.subheader("Virksomhedens gemte profil (klik for at ændre)")
    edited_profile = st.text_area("Virksomhedsprofil:", st.session_state["brand_profile"], height=200)

    if st.button("Opdater profil"):
        st.session_state["brand_profile"] = edited_profile
        st.success("Profil opdateret!")

    st.markdown("---")

    # SEO-tekstgenerering med profil
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
