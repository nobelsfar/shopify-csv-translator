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

if st.sidebar.button("✏️ Redigér virksomhedsprofil"):
    st.session_state["vis_redigeringsside"] = True

if st.session_state.get("vis_redigeringsside"):
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
    st.stop()

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
            rep
