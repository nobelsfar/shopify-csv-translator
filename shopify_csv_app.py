#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Mar 22 15:58:05 2025

@author: babelon
"""

import streamlit as st
import pandas as pd
import openai
import time
import io

# ✅ Denne linje skal stå FØRST
st.set_page_config(page_title="Shopify CSV Oversætter", layout="wide")

# 🔐 Adgangskodebeskyttelse
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if not st.session_state["password_correct"]:
        st.title("🔐 Log ind for at bruge appen")
        password = st.text_input("Adgangskode:", type="password")
        login_button = st.button("Log ind")

        if login_button:
            if password == "hemmeligtkodeord":  # ← skift til din ønskede kode
                st.session_state["password_correct"] = True
                st.success("✅ Logget ind!")
            else:
                st.error("Forkert adgangskode")
                st.stop()

        else:
            st.stop()


check_password()

# 🔽 Resten af appen (vises kun efter korrekt login)
st.title("🌐 Shopify CSV Oversætter")
st.markdown("Upload en CSV-fil fra Shopify, og oversæt indholdet automatisk baseret på Locale-kolonnen.")

# 🔹 Sprog der understøttes
supported_languages = {
    "en": "Engelsk", "de": "Tysk", "fr": "Fransk", "nl": "Hollandsk",
    "es": "Spansk", "it": "Italiensk", "sv": "Svensk", "no": "Norsk",
    "fi": "Finsk", "pl": "Polsk", "ja": "Japansk"
}

# 📂 Upload CSV
uploaded_file = st.file_uploader("Upload din Shopify CSV-fil", type=["csv"])
api_key = st.text_input("Indsæt din OpenAI API-nøgle", type="password")

# 🌍 Start, hvis alt er klar
if uploaded_file and api_key:
    df = pd.read_csv(uploaded_file)
    st.success("CSV-fil indlæst!")

    # Vælg hvilke sprog der skal oversættes
    available_locales = df["Locale"].dropna().unique().tolist()
    selected_locales = st.multiselect("Vælg hvilke Locale-sprog du vil oversætte", options=available_locales, default=available_locales)

    if st.button("✉️ Start oversættelse"):
        client = openai.OpenAI(api_key=api_key)
        progress = st.progress(0)
        total = len(df)
        count = 0

        for index, row in df.iterrows():
            locale = row["Locale"]
            if locale in supported_languages and locale in selected_locales:
                if pd.isna(row["Translated content"]) or row["Translated content"].strip() == "":
                    try:
                        response = client.chat.completions.create(
                            model="gpt-4-turbo",
                            messages=[
                                {"role": "system", "content": f"Du er en professionel oversætter. Oversæt nøjagtigt og ordret fra dansk til {supported_languages[locale]}. Bevar alle HTML-tags og strukturen præcis som den er. Du må ikke forklare noget. Returnér KUN den oversatte tekst – uden overskrifter, bemærkninger eller forklaringer."},
                                {"role": "user", "content": f"Oversæt følgende tekst fra dansk til {supported_languages[locale]}: {row['Default content']}"}
                            ]
                        )
                        translated_text = response.choices[0].message.content.strip()
                        df.at[index, "Translated content"] = translated_text
                    except Exception as e:
                        df.at[index, "Translated content"] = f"FEJL: {e}"
            count += 1
            progress.progress(count / total)
            time.sleep(1)

        st.success("Oversættelse færdig!")

        # 🔍 Vis de første par rækker
        st.dataframe(df.head(10))

        # 🔧 Tillad download
        csv = df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="📂 Download oversat CSV",
            data=csv,
            file_name="shopify_translated.csv",
            mime="text/csv"
        )

else:
    st.info("Upload en CSV og indsæt din API-nøgle for at komme i gang.")
