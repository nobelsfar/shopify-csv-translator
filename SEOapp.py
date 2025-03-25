import streamlit as st
import pandas as pd
import openai
import base64
from PIL import Image
import io

st.title("Avanceret SEO Tekstgenerator")

api_key = st.text_input("OpenAI API-nøgle", type="password")

if api_key:
    client = openai.OpenAI(api_key=api_key)

    # Upload produktdata
    uploaded_csv = st.file_uploader("Upload produktdata (CSV)", type=["csv"])
    if uploaded_csv:
        product_df = pd.read_csv(uploaded_csv)
        st.success("Produktdata indlæst!")

    # Upload billeder
    uploaded_images = st.file_uploader("Upload produktbilleder", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

    # Virksomhedens DNA
    brand_dna = st.text_area("Beskriv virksomhedens DNA, værdier, stil og målgruppe:")

    seo_keyword = st.text_input("Primært SEO-søgeord")
    emne = st.text_input("Emne for teksten")
    tone = st.selectbox("Tone-of-voice", ["Professionel", "Informativ", "Inspirerende", "Humoristisk", "Salg"])

    if st.button("Generér SEO-tekst"):
        prompt = f"Skriv en SEO-optimeret tekst om '{emne}' med søgeordet '{seo_keyword}'. Tone: {tone}. Virksomhedens DNA: {brand_dna}."

        if uploaded_csv:
            product_info = product_df.head(3).to_dict(orient='records')
            prompt += f" Produktinformation: {product_info}."

        if uploaded_images:
            image_descriptions = []
            for img in uploaded_images:
                img_bytes = img.getvalue()
                img_base64 = base64.b64encode(img_bytes).decode()

                # OpenAI Vision API kan analysere billeder
                vision_response = client.chat.completions.create(
                    model="gpt-4-vision-preview",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Beskriv billedet i korte og præcise termer til brug i produktbeskrivelse."},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
                            ]
                        }
                    ],
                    max_tokens=100
                )
                image_descriptions.append(vision_response.choices[0].message.content.strip())
            
            prompt += f" Billedbeskrivelser: {image_descriptions}."

        try:
            # Generér tekst fra samlet data
            response = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000
            )
            seo_text = response.choices[0].message.content.strip()

            st.subheader("Genereret SEO-tekst")
            edited_text = st.text_area("Tilpas teksten yderligere her:", seo_text, height=400)

            if st.download_button("Download SEO-tekst", edited_text, "seo_text.txt"):
                st.success("SEO-tekst downloadet!")
        except Exception as e:
            st.error(f"Fejl under generering: {e}")

else:
    st.info("Indtast API-nøglen for at bruge appen.")
