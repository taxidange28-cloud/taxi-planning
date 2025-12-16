# ========================================
# CODE À AJOUTER AU DÉBUT DE APP.PY
# ========================================
# 
# INSTRUCTIONS :
# 1. Ouvre app.py sur GitHub
# 2. Clique sur le crayon (Edit)
# 3. Trouve la ligne : import streamlit as st
# 4. JUSTE APRÈS cette ligne, colle ce code ci-dessous
# 5. Sauvegarde (Commit changes)
#
# ========================================

# Configuration PWA
st.set_page_config(
    page_title="Planning DanGE",
    page_icon="🚖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Injection du manifest PWA
st.markdown("""
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#4CAF50">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="apple-mobile-web-app-title" content="Planning DanGE">
""", unsafe_allow_html=True)

# ========================================
# FIN DU CODE À AJOUTER
# ========================================
#
# Après avoir ajouté ce code, le début de app.py
# doit ressembler à ceci :
#
# import streamlit as st
# # Configuration PWA
# st.set_page_config(
#     page_title="Planning DanGE",
#     ...
# )
# # Injection du manifest PWA
# st.markdown("""
#     ...
# """, unsafe_allow_html=True)
#
# import streamlit.components.v1 as components
# import psycopg2
# ...
#
# ========================================
