import streamlit as st
import openai
import pandas as pd
import PyPDF2
import io

st.set_page_config(page_title="AI-assisteret SEO generator", layout="wide")

if "api_key" not in st.session_state:
    st.session_state["api_key"] = ""

st.title("📝 Skriv SEO-tekster med AI")

# API-nøgle
if not st.session_state["api_key"]:
    api_input = st.text_input("Indtast OpenAI API-nøgle", type="password")
    if api_input:
        st.session_state["api_key"] = api_input
        st.experimental_rerun()
    st.stop()

client = openai.OpenAI(api_key=st.session_state["api_key"])

# Sidebar med virksomhedsprofil
st.sidebar.header("📁 Din virksomhedsprofil")
if "brand_profile" in st.session_state:
    st.sidebar.markdown(st.session_state["brand_profile"])
else:
    st.sidebar.info("Ingen virksomhedsprofil fundet endnu.")

with st.sidebar.expander("⚙️ Generér eller upload profil"):
    profilmetode = st.radio("Vælg metode", ["Chat med AI", "Upload fil"])

    if profilmetode == "Chat med AI":
        if "chat_history" not in st.session_state:
            st.session_state["chat_history"] = [
                {"role": "system", "content": "Du er en brandingekspert. Stil relevante spørgsmål og hjælp brugeren med at formulere en virksomhedsprofil."},
                {"role": "assistant", "content": "Hej! Fortæl mig lidt om din virksomhed. Hvad sælger I, og hvem er jeres kunder?"}
            ]

        for msg in st.session_state["chat_history"]:
            if msg["role"] == "user":
                st.chat_message("user").markdown(msg["content"])
            elif msg["role"] == "assistant":
                st.chat_message("assistant").markdown(msg["content"])

        user_input = st.chat_input("Skriv dit svar eller spørgsmål...")
        if user_input:
            st.session_state["chat_history"].append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)

            response = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=st.session_state["chat_history"],
                max_tokens=500
            )
            reply = response.choices[0].message.content.strip()
            st.session_state["chat_history"].append({"role": "assistant", "content": reply})
            with st.chat_message("assistant"):
                st.markdown(reply)

            if "brand_profile" not in st.session_state and len(st.session_state["chat_history"]) > 5:
                st.session_state["brand_profile"] = reply
                st.sidebar.success("Virksomhedsprofil genereret fra chat!")

    elif profilmetode == "Upload fil":
        uploaded_file = st.file_uploader("Upload CSV, Excel eller PDF", type=["csv", "xlsx", "pdf"])
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
            st.text_area("Ekstraheret tekst (redigér hvis nødvendigt)", extracted_text, height=200, key="raw_info")

            if st.button("Generér virksomhedsprofil ud fra uploadet tekst"):
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
                st.sidebar.success("Profil genereret!")

# Hovedindhold – SEO tekstgenerator
if "brand_profile" in st.session_state:
    st.subheader("Generér SEO-tekst")
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
else:
    st.info("Start med at oprette en virksomhedsprofil i sidepanelet for at kunne generere SEO-tekster.")
