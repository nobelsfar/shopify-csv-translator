import streamlit as st
import pandas as pd
import openai
import time
import io

st.set_page_config(page_title="Shopify CSV Oversætter", layout="wide")

# Adgangskodebeskyttelse
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if not st.session_state["password_correct"]:
        st.title("🔐 Log ind for at bruge appen")
        password = st.text_input("Adgangskode:", type="password")
        login_button = st.button("Log ind")

        if login_button:
            if password == "hemmeligtkodeord":
                st.session_state["password_correct"] = True
                st.success("✅ Logget ind!")
            else:
                st.error("Forkert adgangskode")
                st.stop()

        else:
            st.stop()

check_password()

st.title("🌐 Shopify CSV Oversætter")
st.markdown("Upload en CSV-fil fra Shopify, og oversæt indholdet automatisk baseret på Locale-kolonnen.")

supported_languages = {
    "en": "Engelsk", "de": "Tysk", "fr": "Fransk", "nl": "Hollandsk",
    "es": "Spansk", "it": "Italiensk", "sv": "Svensk", "no": "Norsk",
    "fi": "Finsk", "pl": "Polsk", "ja": "Japansk"
}

uploaded_file = st.file_uploader("Upload din Shopify CSV-fil", type=["csv"])
api_key = st.text_input("Indsæt din OpenAI API-nøgle", type="password")

if uploaded_file and api_key:
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.str.strip()
    st.success("CSV-fil indlæst!")

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
                                {"role": "system", "content": f"Du er en professionel oversætter. Oversæt nøjagtigt og ordret fra dansk til {supported_languages[locale]}. Bevar alle HTML-tags og strukturen præcis som den er. Du må ikke forklare noget. Returnér KUN den oversatte tekst."},
                                {"role": "user", "content": f"{row['Default content']}"}
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

    st.markdown("---")
    st.subheader("📝 Rediger og forhåndsvis oversættelser")

    def label_row(i):
        default = df.at[i, "Default content"]
        short = default[:60].replace("\n", " ").strip() + ("..." if len(default) > 60 else "")
        return f"{i}: {df.at[i, 'Type']} – {df.at[i, 'Field']} ({df.at[i, 'Locale']}) → {short}"

    selected_row = st.selectbox("Vælg række til redigering og preview", options=df.index, format_func=label_row)

    st.markdown("**🔍 Forhåndsvisning af indhold:**")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Original (dansk):**")
        default_content = df.at[selected_row, 'Default content']

        if st.checkbox("Vis HTML (dansk)", key=f"show_html_da_{selected_row}"):
            edited_default = st.text_area("HTML (dansk)", value=default_content, height=200, key=f"html_da_{selected_row}")
            default_content = edited_default

        st.markdown(f"<div style='border:1px solid #ccc; padding:1em; border-radius:10px;'>{default_content}</div>", unsafe_allow_html=True)
    with col2:
        st.markdown("**Oversættelse:**")
        translated_content = df.at[selected_row, 'Translated content'] if pd.notna(df.at[selected_row, 'Translated content']) else ""

        if st.checkbox("Vis HTML (oversat)", key=f"show_html_trans_{selected_row}"):
            edited_translated = st.text_area("HTML (oversat)", value=translated_content, height=200, key=f"html_trans_{selected_row}")
            translated_content = edited_translated

        edited_translated_content = st.text_area("", value=translated_content, height=300, key=f"preview_trans_{selected_row}")
        translated_content = edited_translated_content

    st.markdown("**✏️ Redigér HTML-indholdet:**")
    text_key = f"text_{selected_row}"
    if text_key not in st.session_state:
        raw_val = df.at[selected_row, "Translated content"]
        st.session_state[text_key] = "" if pd.isna(raw_val) else str(raw_val)

    #edited_text feltet er fjernet da redigering nu sker direkte i preview-feltet

    #"Ret oversættelsen her:", height=300, key=edit_key)

    if st.button("💾 Gem ændringer"):
        edited_text = st.session_state[translated_html_key]
        original = "" if pd.isna(df.at[selected_row, "Translated content"]) else str(df.at[selected_row, "Translated content"])
        if edited_text.strip() == "":
            st.warning("Oversættelsen må ikke være tom – ændring blev ikke gemt.")
        elif edited_text != original:
            df.at[selected_row, "Translated content"] = edited_text
            st.success("Ændring gemt!")
        else:
            st.info("Ingen ændringer at gemme.")

    csv = df.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        label="📂 Download oversat CSV",
        data=csv,
        file_name="shopify_translated.csv",
        mime="text/csv"
    )
else:
    st.info("Upload en CSV og indsæt din OpenAI API-nøgle for at komme i gang.")
