# ---- SEO-SIDE ----
elif st.session_state["page"] == "seo":
    st.header("Generér SEO-tekst (HTML + forhåndsvisning)")

    data = st.session_state["profiles"].get(
        st.session_state["current_profile"],
        {"brand_profile": "", "blacklist": "", "produkt_info": ""}
    )

    st.write("Virksomhedsprofil:")
    st.markdown(data.get("brand_profile", "(ingen)"))

    # Fjern eventuelle selectboxes for output-format
    malgruppe = st.selectbox("Målgruppe", ["B2C (forbrugere)", "B2B (professionelle)", "Design/fagligt interesserede", "Andet"])
    formaal = st.selectbox("Formål", ["Salg/landingsside", "Informativ blog", "Branding/storytelling"])
    rel_soegeord = st.text_input("Relaterede søgeord (kommasep)", "")
    cfaq, cmeta, cints, ccta = st.columns(4)
    with cfaq: 
        inc_faq = st.checkbox("Inkluder FAQ")
    with cmeta: 
        inc_meta = st.checkbox("Meta-titel+beskrivelse")
    with cints: 
        inc_links = st.checkbox("Interne links")
    with ccta: 
        inc_cta = st.checkbox("CTA")

    min_len = st.number_input("Min. ordlængde", min_value=50, max_value=2000, value=700, step=50)
    tone_opts = ["Neutral", "Formel", "Venlig", "Entusiastisk", "Humoristisk", "Autoritær", "Professionel"]
    tone = st.selectbox("Tone-of-voice", tone_opts, 0)

    seo_key = st.text_input("Hoved-søgeord / emne", "")
    antal = st.selectbox("Antal SEO-tekster", list(range(1, 11)), 0)

    if seo_key:
        if st.button("Generér SEO-tekst"):
            with st.spinner("Genererer SEO-tekst..."):
                for i in range(antal):
                    # Hardkod prompt til at returnere HTML
                    base_prompt = (
                        f"Skriv en SEO-optimeret tekst på dansk om '{seo_key}'.\n"
                        f"Formål: {formaal}, Målgruppe: {malgruppe}, Tone-of-voice: {tone}.\n"
                        f"Brug brandprofil: {data.get('brand_profile', '')} og produktinfo: {data.get('produkt_info', '')}.\n"
                        f"Min. {min_len} ord.\n"
                        "Undgå 'bæredygtighed'/'bæredygtig'.\n"
                        f"Relaterede søgeord: {rel_soegeord}.\n"
                        "Returnér i HTML med <h2>, <h3>, <h4> overskrifter.\n"
                    )
                    if inc_faq:
                        base_prompt += "Lav en FAQ-sektion med mindst 3 spørgsmål.\n"
                    if inc_meta:
                        base_prompt += "Tilføj meta-titel (60 tegn) og meta-beskrivelse (160 tegn).\n"
                    if inc_links:
                        base_prompt += "Tilføj mindst 2 interne links.\n"
                    if inc_cta:
                        base_prompt += "Afslut med en tydelig CTA.\n"

                    blacklist_words = data.get("blacklist", "")

                    # 1) generér iterativ => min. ord
                    draft = generate_iterative_seo_text(base_prompt, min_len=min_len, max_tries=3)

                    # 2) FJERN IKKE "### " - enten lad den være eller omdøb den til h3:
                    # draft = draft.replace("### ", "")  # <- SLET ELLER UDKOMMENTER

                    # 3) check blacklist => rewrite
                    final_txt = check_blacklist_and_rewrite(draft, blacklist_words, max_tries=2)

                    st.session_state["generated_texts"].append(final_txt)
            save_state()

            if st.session_state["generated_texts"]:
                st.subheader("Dine SEO-tekster - forhåndsvisning (HTML)")
                cpy = st.session_state["generated_texts"][:]
                for idx, doc in enumerate(cpy):
                    with st.expander(f"SEO-tekst {idx+1}"):
                        # Altid vis HTML
                        st.markdown(doc, unsafe_allow_html=True)

                        # Download-knap (HTML-fil)
                        st.download_button(
                            label=f"Download SEO {idx+1} (HTML)",
                            data=doc,
                            file_name=f"seo_{idx+1}.html",
                            mime="text/html"
                        )
                        if st.button(f"Slet tekst {idx+1}", key=f"del_{idx}"):
                            st.session_state["generated_texts"].pop(idx)
                            save_state()
                            st.experimental_rerun()
