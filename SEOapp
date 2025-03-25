import streamlit as st
import openai

st.set_page_config(page_title="SEO Tekstgenerator", layout="wide")
st.title("SEO Tekstgenerator med AI")

# API-nøgle input (kan senere gemmes i session_state)
api_key = st.text_input("Indtast din OpenAI API-nøgle:", type="password")

if api_key:
    client = openai.OpenAI(api_key=api_key)

    with st.form("seo_form"):
        seo_keyword = st.text_input("Primært søgeord")
        emne = st.text_input("Emne")
        tone = st.selectbox("Tone-of-voice", ["Professionel", "Informativ", "Salg", "Venlig", "Humoristisk"])
        undgaa = st.text_area("Ord/sætninger, der skal undgås (adskil med komma)")
        laengde = st.number_input("Ønsket længde (antal ord)", min_value=50, max_value=2000, value=300)
        
        submitted = st.form_submit_button("Generér tekst")

    if submitted:
        undgaa_prompt = f"Undgå følgende ord eller sætninger: {undgaa}." if undgaa.strip() else ""
        prompt = (
            f"Skriv en SEO-optimeret tekst på dansk med det primære søgeord '{seo_keyword}'. "
            f"Emnet er '{emne}'. Teksten skal have en '{tone}' tone-of-voice og være omkring {laengde} ord. "
            f"{undgaa_prompt} Sørg for, at teksten er naturlig og engagerende."
        )

        try:
            response = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[{"role": "user", "content": prompt}]
            )
            seo_tekst = response.choices[0].message.content.strip()
            
            st.subheader("Genereret SEO-tekst")
            edited_text = st.text_area("Tilpas teksten her:", seo_tekst, height=400)
            
            if st.button("Download tekst"):
                st.download_button(
                    label="Download SEO-tekst",
                    data=edited_text,
                    file_name="seo_tekst.txt",
                    mime="text/plain"
                )

        except Exception as e:
            st.error(f"Der opstod en fejl: {e}")

else:
    st.info("Indtast din OpenAI API-nøgle for at starte.")
