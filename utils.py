# ==========================================
# VERZE 6.6.4 - Správa flotily - RHJ Gastro
# ==========================================

import io
import qrcode
import streamlit as st

def generuj_qr_kod(url_adresa):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url_adresa)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

def render_styled_table(df):
    html = df.to_html(classes='styled-table', index=False, escape=False)
    st.markdown(html, unsafe_allow_html=True)
