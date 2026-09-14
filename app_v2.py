# ==========================================
# VERZE 6.8.1 - Správa flotily - RHJ Gastro
# ==========================================

import asyncio
import socket
import sys
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

# Importujeme funkce z našich DB a pomocných souborů
from db import *
from utils import *

# --- LOKÁLNÍ UPDATE FUNKCE ---
def oznacit_zavadu_opraveno(zavada_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE zavady SET stav = 'Opraveno' WHERE id = ?", (zavada_id,))
    conn.commit()
    cursor.close()
    conn.close()

# Oprava pro asyncio na Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

SUPERVISOR_PASSWORD = 'supervisor789'

# Spuštění inicializace a nahrání fiktivních dat
init_db()

st.set_page_config(
    page_title='Správa flotily - RHJ Gastro [v6.8.1]', page_icon='🚀', layout='wide'
)

if 'active_tab' not in st.session_state:
    st.session_state['active_tab'] = '🏢 Vozidla'
if 'car_action' not in st.session_state:
    st.session_state['car_action'] = 'view'
if 'editing_spz' not in st.session_state:
    st.session_state['editing_spz'] = None
if 'tank_action' not in st.session_state:
    st.session_state['tank_action'] = 'view'
if 'servis_action' not in st.session_state:
    st.session_state['servis_action'] = 'view'
if 'zavada_action' not in st.session_state:
    st.session_state['zavada_action'] = 'view'
if 'admin_autentizovan' not in st.session_state:
    st.session_state['admin_autentizovan'] = False
if 'supervizor_autentizovan' not in st.session_state:
    st.session_state['supervizor_autentizovan'] = False
if 'simulovat_ridice' not in st.session_state:
    st.session_state['simulovat_ridice'] = False
if 'dark_mode' not in st.session_state:
    st.session_state['dark_mode'] = False
if 'car_view_mode' not in st.session_state:
    st.session_state['car_view_mode'] = 'Karty (Tile View)'

# Dynamické CSS pro podporu světlého a tmavého režimu + mobilní optimalizace
if st.session_state['dark_mode']:
    THEME_CSS = """
    <style>
        .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
            background-color: #121214 !important; 
            color: #e1e1e6 !important;
            font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
        }
        p, label, .stMarkdown, .stText { color: #e1e1e6 !important; font-size: 15px !important; }
        h1 { font-size: 34px !important; color: #ffffff !important; font-weight: 800 !important; }
        h2 { font-size: 24px !important; color: #ffffff !important; font-weight: 700 !important; }
        h3 { font-size: 20px !important; color: #ffffff !important; font-weight: 600 !important; }

        input, textarea, select, div[data-baseweb="select"] > div {
            background-color: #202024 !important;
            color: #e1e1e6 !important;
            border: 1px solid #323238 !important;
            border-radius: 8px !important;
            font-weight: 500 !important;
        }

        [data-testid="stCode"], pre, code {
            background-color: #202024 !important; color: #e1e1e6 !important; border: 1px solid #323238 !important; border-radius: 8px !important;
        }
        .styled-table { background-color: #202024 !important; border: 1px solid #323238 !important; }
        .styled-table th { background-color: #29292e !important; color: #ffffff !important; border-bottom: 1px solid #323238 !important; }
        .styled-table td { color: #e1e1e6 !important; border-bottom: 1px solid #29292e !important; }
        .alert-box { background-color: #202024 !important; border: 1px solid #323238 !important; }
        .car-card-blue, .car-card-orange, .car-card-green {
            background: #202024 !important; border-left: 1px solid #323238 !important; border-right: 1px solid #323238 !important; border-bottom: 1px solid #323238 !important;
        }
        
        [data-testid="stAlert"] p, [data-testid="stAlert"] span { color: #e1e1e6 !important; }
    </style>
    """
else:
    THEME_CSS = """
    <style>
        .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
            background-color: #f4f4f7 !important; 
            color: #1e1b29 !important;
            font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
        }
        p, label, .stMarkdown, .stText { color: #332d42 !important; font-size: 15px !important; }
        h1 { font-size: 34px !important; color: #1e1b29 !important; font-weight: 800 !important; }
        h2 { font-size: 24px !important; color: #1e1b29 !important; font-weight: 700 !important; }
        h3 { font-size: 20px !important; color: #1e1b29 !important; font-weight: 600 !important; }

        input, textarea, select, div[data-baseweb="select"] > div {
            background-color: #ffffff !important; color: #1e1b29 !important; border: 1px solid #d1cce3 !important; border-radius: 8px !important; font-weight: 500 !important;
        }

        [data-testid="stCode"], pre, code { background-color: #ffffff !important; color: #1e1b29 !important; border: 1px solid #d1cce3 !important; border-radius: 8px !important; }
        .styled-table { background-color: #ffffff; border: 1px solid #e2e8f0; }
        .styled-table th { background-color: #f1ecfa !important; color: #1e1b29 !important; border-bottom: 1px solid #d1cce3; }
        .styled-table td { color: #332d42 !important; border-bottom: 1px solid #f1f5f9; }
        .alert-box { background-color: white; border: 1px solid #e2e8f0; }
        .car-card-blue { background: linear-gradient(145deg, #ffffff, #f0f6ff) !important; border-left: 1px solid #dbeafe !important; border-right: 1px solid #dbeafe !important; border-bottom: 1px solid #dbeafe !important; }
        .car-card-orange { background: linear-gradient(145deg, #ffffff, #fffbeb) !important; border-left: 1px solid #ffedd5 !important; border-right: 1px solid #ffedd5 !important; border-bottom: 1px solid #ffedd5 !important; }
        .car-card-green { background: linear-gradient(145deg, #ffffff, #f0fdf4) !important; border-left: 1px solid #dcfce7 !important; border-right: 1px solid #dcfce7 !important; border-bottom: 1px solid #dcfce7 !important; }
        
        [data-testid="stAlert"] p, [data-testid="stAlert"] span { color: #1e1b29 !important; }
    </style>
    """

CLEAN_CSS = THEME_CSS + """
<style>
    div.nav-tile-btn button {
        background: linear-gradient(135deg, #5b4b8a 0%, #48396b) !important;
        color: #ffffff !important;
        border: 1px solid #6b599c !important;
        border-radius: 14px !important;
        font-weight: 700 !important;
        font-size: 15px !important;
        padding: 16px 8px !important;
        box-shadow: 0 4px 12px rgba(91, 75, 138, 0.25) !important;
        width: 100% !important;
        height: 75px !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    div.nav-tile-btn button * { color: #ffffff !important; font-weight: 700 !important; }
    div.nav-tile-btn button:hover { background: linear-gradient(135deg, #6b599c 0%, #5b4b8a) !important; box-shadow: 0 6px 16px rgba(91, 75, 138, 0.4) !important; transform: translateY(-2px); }

    div.nav-tile-btn-active button {
        background: linear-gradient(135deg, #3d3156 0%, #2a213c) !important;
        color: #ffffff !important;
        border: 2px solid #8572bd !important;
        border-radius: 14px !important;
        font-weight: 800 !important;
        font-size: 15px !important;
        padding: 16px 8px !important;
        box-shadow: inset 0 3px 6px rgba(0, 0, 0, 0.35), 0 6px 15px rgba(61, 49, 86, 0.5) !important;
        width: 100% !important;
        height: 75px !important;
    }
    div.nav-tile-btn-active button * { color: #ffffff !important; font-weight: 800 !important; }

    div.delete-tile-btn button, div.stButton > button, [data-testid="stFormSubmitButton"] > button, [data-testid="stDownloadButton"] > button {
        background: linear-gradient(135deg, #5b4b8a 0%, #48396b) !important; color: #ffffff !important; border: 1px solid #6b599c !important; border-radius: 10px !important; font-weight: 700 !important; font-size: 15px !important; padding: 10px 16px !important; box-shadow: 0 4px 12px rgba(91, 75, 138, 0.25) !important; width: 100% !important; transition: all 0.2s ease !important;
    }
    div.delete-tile-btn button *, div.stButton > button *, [data-testid="stFormSubmitButton"] > button *, [data-testid="stDownloadButton"] > button * { color: #ffffff !important; fill: #ffffff !important; }
    div.delete-tile-btn button:hover, div.stButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover, [data-testid="stDownloadButton"] > button:hover { background: linear-gradient(135deg, #6b599c 0%, #5b4b8a) !important; box-shadow: 0 6px 16px rgba(91, 75, 138, 0.4) !important; transform: translateY(-2px); }

    div.stButton > button[kind="primary"] { background-color: #0f9d58 !important; background: #0f9d58 !important; color: white !important; border: none !important; }
    div.stButton > button[kind="primary"] * { color: white !important; }

    .car-card-blue { border-top: 6px solid #2563eb !important; border-radius: 16px !important; padding: 24px !important; box-shadow: 0 10px 25px -5px rgba(37, 99, 235, 0.15) !important; margin-bottom: 15px !important; }
    .car-card-orange { border-top: 6px solid #ea580c !important; border-radius: 16px !important; padding: 24px !important; box-shadow: 0 10px 25px -5px rgba(234, 88, 12, 0.15) !important; margin-bottom: 15px !important; }
    .car-card-green { border-top: 6px solid #16a34a !important; border-radius: 16px !important; padding: 24px !important; box-shadow: 0 10px 25px -5px rgba(22, 163, 74, 0.15) !important; margin-bottom: 15px !important; }

    .badge-red { background-color: #fee2e2; color: #dc2626; padding: 3px 8px; border-radius: 6px; font-weight: 700; display: inline-block; }
    .badge-orange { background-color: #fef3c7; color: #d97706; padding: 3px 8px; border-radius: 6px; font-weight: 700; display: inline-block; }
    .badge-green { background-color: #dcfce7; color: #16a34a; padding: 3px 8px; border-radius: 6px; font-weight: 700; display: inline-block; }

    .styled-table { border-collapse: collapse; margin: 15px 0; font-size: 14px; width: 100%; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.04); }
    .styled-table th { text-align: left; padding: 12px 16px; font-weight: 700; position: sticky; top: 0; z-index: 1; }
    .styled-table td { padding: 12px 16px; }
    .table-container { max-height: 500px; overflow-y: auto; border-radius: 10px; border: 1px solid #e2e8f0; }

    .alert-box { border-radius: 10px; padding: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); height: 100%; }
    .oil-scroll-container { max-height: 250px !important; overflow-y: auto !important; overflow-x: hidden !important; padding-right: 6px; margin-top: 8px; }
    [data-testid="stMetricValue"] { font-weight: 800 !important; color: #5b4b8a !important; }
    
    /* Mobilní optimalizace pro dílnu */
    @media (max-width: 768px) {
        .main .block-container { padding-left: 0.75rem; padding-right: 0.75rem; }
        table { font-size: 12px !important; }
        div.nav-tile-btn button, div.nav-tile-btn-active button { height: 55px !important; font-size: 13px !important; padding: 8px 4px !important; }
    }
</style>
"""
st.markdown(CLEAN_CSS, unsafe_allow_html=True)

query_params = st.query_params
qr_spz_param = query_params.get("spz", None)
qr_ridic_param = query_params.get("ridic", "Neznámý řidič")

if st.session_state['simulovat_ridice']:
    df_auta_sim = get_vsechna_auta()
    if not df_auta_sim.empty:
        prvni_auto = df_auta_sim.iloc[0]
        qr_ridic_param = prvni_auto['staly_ridic'] if prvni_auto['staly_ridic'] != 'Neuveden' else 'Testovací řidič'
        qr_spz_param = prvni_auto['spz']
    else:
        qr_ridic_param = 'Testovací řidič'
        qr_spz_param = '5Z49372'

if qr_spz_param or st.session_state.get('simulovat_ridice', False):
    st.markdown(
        """
        <div style="background-color: #eae5f5; padding: 24px 32px; border-radius: 18px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); margin-bottom: 25px; display: flex; align-items: center; justify-content: space-between; border: 1px solid #d1cce3;">
            <div style="display: flex; align-items: center; gap: 20px;">
                <div style="background: white; padding: 10px 14px; border-radius: 12px; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <span style="font-size: 30px; font-weight: 900; color: #5b4b8a; letter-spacing: -1px;">RHJ</span>
                </div>
                <div>
                    <h1 style="color: #5b4b8a !important; margin: 0; font-size: 32px !important; font-weight: 900;">RHJ Gastro – Rozhraní pro řidiče</h1>
                    <p style="color: #3d3156 !important; margin: 4px 0 0 0; font-size: 15px !important; font-weight: 600;">Rychlý záznam tankování / nabíjení pro vozidlo (v6.8.1)</p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state['admin_autentizovan'] or st.session_state['simulovat_ridice']:
        if st.button("⬅️ Zpět do administrace flotily"):
            st.session_state['simulovat_ridice'] = False
            st.query_params.clear()
            st.rerun()

    df_auta = get_vsechna_auta()
    df_ridici_mobil = get_ridici()

    seznam_ridicu = []
    if not df_ridici_mobil.empty and 'jmeno' in df_ridici_mobil.columns:
        seznam_ridicu.extend(df_ridici_mobil['jmeno'].dropna().tolist())
    if not df_auta.empty and 'staly_ridic' in df_auta.columns:
        seznam_ridicu.extend(df_auta['staly_ridic'].dropna().tolist())
    
    seznam_ridicu = sorted(list(set([str(r).strip() for r in seznam_ridicu if str(r).strip() and str(r).strip() != 'Neuveden'])))
    if not seznam_ridicu:
        seznam_ridicu = ["Neznámý řidič"]

    st.markdown("### Výběr řidiče a vozidla")
    
    default_ridic_idx = 0
    if qr_ridic_param in seznam_ridicu:
        default_ridic_idx = seznam_ridicu.index(qr_ridic_param)
    
    selected_driver_name = st.selectbox("1. Jméno řidiče", seznam_ridicu, index=default_ridic_idx)

    if not df_auta.empty:
        df_auta['car_label'] = df_auta.apply(lambda r: f"{r['nazev']} (SPZ: {r['spz']})", axis=1)
        
        default_car_idx = 0
        if qr_spz_param:
            match_rows = df_auta[df_auta['spz'] == qr_spz_param]
            if not match_rows.empty:
                default_car_idx = df_auta.index.get_loc(match_rows.index[0])

        selected_car_label = st.selectbox("2. Typ a SPZ", df_auta['car_label'].tolist(), index=default_car_idx)
        selected_car_row = df_auta[df_auta['car_label'] == selected_car_label].iloc[0]
        
        active_spz = selected_car_row['spz']
        auto = selected_car_row
    else:
        auto = None
        active_spz = None

    if auto is not None:
        pohonna_hmota = str(auto['typ_pohonu']).strip().lower()
        is_elektro = 'elektřina' in pohonna_hmota or 'elektre' in pohonna_hmota or 'ev' in pohonna_hmota

        st.markdown(f"### Zvolené vozidlo: **{auto['nazev']}** (SPZ: **{auto['spz']}**)")
        st.markdown(f"**Pohonná hmota:** {auto['typ_pohonu']} | **Aktivní řidič:** {selected_driver_name}")
        st.markdown('---')

        driver_tab1, driver_tab2 = st.tabs(["⚡ Zapsat tankování / Nabíjení EV", "⚠️ Nahlásit závadu"])

        with driver_tab1:
            if not is_elektro:
                with st.form('driver_fuel_form'):
                    d_km = st.number_input('Aktuální stav tachometru (km)', min_value=0, step=100)
                    d_litry = st.number_input('Množství paliva (litry)', min_value=0.0, step=1.0)
                    d_cena = st.number_input('Celková cena (Kč)', min_value=0.0, step=10.0)

                    submitted_fuel = st.form_submit_button('Uložit')
                    if submitted_fuel:
                        if selected_driver_name.strip():
                            pridat_zaznam_paliva(auto['spz'], selected_driver_name, d_km, 'Čerpací stanice / Veřejný zdroj', d_litry, d_cena)
                            st.success('Záznam o tankování byl úspěšně uložen!')
                        else:
                            st.error('Zadejte prosím své jméno.')
            else:
                conn = get_connection()
                cursor = conn.cursor()
                res_kwh = cursor.execute("SELECT hodnota FROM nastaveni WHERE klic = 'cena_kwh'").fetchone()
                cena_za_kwh = float(res_kwh[0]) if res_kwh else 6.50
                conn.close()

                kapacita_baterie_kwh = 37.3

                with st.form('driver_electro_form'):
                    d_km_el = st.number_input('Aktuální stav tachometru (km)', min_value=0, step=100)
                    d_zdroj_el = st.selectbox("Zdroj nabíjení", ["Wallbox", "Zasuvka 220", "Veřejná nabíječka"])
                    
                    st.markdown('#### Stav baterie')
                    stav_procenta = st.slider('Aktuální stav baterie před nabíjením (%)', min_value=0, max_value=100, value=20, step=1)

                    chybi_procenta = max(0, 100 - stav_procenta)
                    dopocitane_kwh = (chybi_procenta / 100.0) * kapacita_baterie_kwh
                    dopocitana_cena = dopocitane_kwh * cena_za_kwh

                    st.info(f"📊 **Dopočet do plného nabití (100%):** Chybí **{chybi_procenta} %** kapacity (~**{dopocitane_kwh:.2f} kWh**). Odhadovaná cena nabití: **{dopocitana_cena:.2f} Kč** (při {cena_za_kwh} Kč/kWh).")

                    submitted_electro = st.form_submit_button('Uložit')
                    if submitted_electro:
                        if selected_driver_name.strip():
                            pridat_zaznam_paliva(auto['spz'], selected_driver_name, d_km_el, d_zdroj_el, dopocitane_kwh, dopocitana_cena, stav_procenta, 100, 0.0)
                            st.success('Záznam o nabíjení byl úspěšně uložen!')
                        else:
                            st.error('Zadejte prosím své jméno.')

        with driver_tab2:
            st.subheader("Nahlásit novou závadu na vozidle")
            with st.form("driver_zavada_form"):
                d_popis_zavady = st.text_area("Popis závady / problémů:")
                d_submit_zavada = st.form_submit_button("Odeslat hlášení závady")
                
                if d_submit_zavada:
                    if d_popis_zavady:
                        pridat_zavadu(auto['spz'], selected_driver_name, d_popis_zavady)
                        st.success("Závada byla úspěšně odeslána do centrální správy!")
                    else:
                        st.error("Vyplňte prosím popis závady.")
    else:
        st.error('V databázi nejsou žádná vozidla.')

    st.stop()

if not st.session_state['admin_autentizovan']:
    st.markdown(
        """
        <div style="max-width: 450px; margin: 80px auto; background: white; padding: 30px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.08); border: 1px solid #d1cce3;">
            <h2 style="color: #5b4b8a !important; text-align: center; margin-top: 0;">🔒 Administrace Flotily</h2>
            <p style="text-align: center; color: #666; font-size: 14px;">Pro přístup zadejte administrátorské nebo supervizorské heslo.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        zadane_heslo = st.text_input("Heslo", type="password", key="admin_pass_input")
        if st.button("Přihlásit se do administrace"):
            aktualni_admin_heslo = ziskej_admin_heslo()
            if zadane_heslo == aktualni_admin_heslo:
                st.session_state['admin_autentizovan'] = True
                st.session_state['supervizor_autentizovan'] = False
                st.success("Přístup povolen (Admin)!")
                st.rerun()
            elif zadane_heslo == SUPERVISOR_PASSWORD:
                st.session_state['admin_autentizovan'] = True
                st.session_state['supervizor_autentizovan'] = True
                st.success("Přístup povolen (Master Supervizor)!")
                st.rerun()
            else:
                st.error("Nesprávné heslo!")
    st.stop()

st.markdown(
    """
    <div style="background-color: #eae5f5; padding: 24px 32px; border-radius: 18px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); margin-bottom: 25px; display: flex; align-items: center; justify-content: space-between; border: 1px solid #d1cce3;">
        <div style="display: flex; align-items: center; gap: 20px;">
            <div style="background: white; padding: 10px 14px; border-radius: 12px; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <span style="font-size: 30px; font-weight: 900; color: #5b4b8a; letter-spacing: -1px;">RHJ</span>
            </div>
            <div>
                <h1 style="color: #5b4b8a !important; margin: 0; font-size: 32px !important; font-weight: 900;">RHJ Gastro – Správa vozového parku</h1>
                <p style="color: #3d3156 !important; margin: 4px 0 0 0; font-size: 15px !important; font-weight: 600;">Rozvoz hotových jídel — Fleet Management & Operations System (v6.8.1)</p>
            </div>
        </div>
        <div style="text-align: right; display: flex; gap: 10px; align-items: center;">
    """,
    unsafe_allow_html=True,
)

if st.session_state['supervizor_autentizovan']:
    st.markdown('<span style="background: #7c3aed; color: white; padding: 6px 12px; border-radius: 8px; font-size: 12px; font-weight: 700;">★ MASTER SUPERVIZOR</span>', unsafe_allow_html=True)

dark_mode_toggle = st.toggle("🌙 Tmavý režim (Dark Mode)", value=st.session_state['dark_mode'])
if dark_mode_toggle != st.session_state['dark_mode']:
    st.session_state['dark_mode'] = dark_mode_toggle
    st.rerun()

if st.button("📱 Přepnout na rozhraní řidiče", type="primary"):
    st.session_state['simulovat_ridice'] = True
    st.rerun()

if st.button("🚪 Odhlásit admin"):
    st.session_state['admin_autentizovan'] = False
    st.session_state['supervizor_autentizovan'] = False
    st.rerun()

st.markdown("</div></div>", unsafe_allow_html=True)

# ==================== KPI DASHBOARD ====================
df_auta_kpi = get_vsechna_auta()
df_servis_kpi = get_zaznamy_servis()
df_palivo_kpi = get_zaznamy_paliva()

propadle_stk_pocet = 0
blizici_stk_pocet = 0
dnes_kpi = datetime.now().date()
for _, a_row in df_auta_kpi.iterrows():
    try:
        s_date = datetime.strptime(str(a_row['stk_do']), '%Y-%m-%d').date()
        dny_stk = (s_date - dnes_kpi).days
        if dny_stk < 0:
            propadle_stk_pocet += 1
        elif 0 <= dny_stk <= 30:
            blizici_stk_pocet += 1
    except Exception:
        pass

aktualni_mesic = dnes_kpi.strftime('%Y-%m')

naklady_nafta_natural = 0.0
naklady_dobijeni = 0.0
naklady_dily_servis = 0.0

if not df_palivo_kpi.empty and not df_auta_kpi.empty:
    df_palivo_kpi['datum_dt'] = pd.to_datetime(df_palivo_kpi['datum'], errors='coerce')
    df_palivo_merged = pd.merge(df_palivo_kpi, df_auta_kpi[['spz', 'typ_pohonu']], on='spz', how='left')
    
    df_mesic = df_palivo_merged[df_palivo_merged['datum_dt'].dt.strftime('%Y-%m') == aktualni_mesic]
    
    mask_nafta_nat = df_mesic['typ_pohonu'].astype(str).str.upper().str.contains('NAFTA|NATURAL')
    naklady_nafta_natural = df_mesic[mask_nafta_nat]['cena'].sum()
    
    mask_elektro = df_mesic['typ_pohonu'].astype(str).str.upper().str.contains('ELEKTŘINA|ELEKTRE|EV|BAT') | df_mesic['zdroj'].astype(str).str.upper().str.contains('WALLBOX|NABÍJEČKA|ZASUVKA|ELEKTŘINA')
    naklady_dobijeni = df_mesic[mask_elektro]['cena'].sum()

if not df_servis_kpi.empty:
    df_servis_kpi['datum_dt'] = pd.to_datetime(df_servis_kpi['datum'], errors='coerce')
    df_servis_mesic = df_servis_kpi[df_servis_kpi['datum_dt'].dt.strftime('%Y-%m') == aktualni_mesic]
    naklady_dily_servis = df_servis_mesic['cena'].sum()

kpi_c1, kpi_c2, kpi_c3, kpi_c4 = st.columns(4)
with kpi_c1:
    st.markdown(f"""
        <div style="background: linear-gradient(135deg, #ef4444 0%, #b91c1c); padding: 18px; border-radius: 12px; color: white; box-shadow: 0 4px 12px rgba(239,68,68,0.2);">
            <div style="font-size: 14px; font-weight: 600; opacity: 0.9;">Díly a servis</div>
            <div style="font-size: 24px; font-weight: 800; margin-top: 5px;">{naklady_dily_servis:,.0f} Kč</div>
        </div>
    """, unsafe_allow_html=True)
with kpi_c2:
    st.markdown(f"""
        <div style="background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8); padding: 18px; border-radius: 12px; color: white; box-shadow: 0 4px 12px rgba(59,130,246,0.2);">
            <div style="font-size: 14px; font-weight: 600; opacity: 0.9;">Náklady Nafta / Natural</div>
            <div style="font-size: 24px; font-weight: 800; margin-top: 5px;">{naklady_nafta_natural:,.0f} Kč</div>
        </div>
    """, unsafe_allow_html=True)
with kpi_c3:
    st.markdown(f"""
        <div style="background: linear-gradient(135deg, #10b981 0%, #047857); padding: 18px; border-radius: 12px; color: white; box-shadow: 0 4px 12px rgba(16,185,129,0.2);">
            <div style="font-size: 14px; font-weight: 600; opacity: 0.9;">Náklady na dobíjení</div>
            <div style="font-size: 24px; font-weight: 800; margin-top: 5px;">{naklady_dobijeni:,.0f} Kč</div>
        </div>
    """, unsafe_allow_html=True)
with kpi_c4:
    st.markdown(f"""
        <div style="background: linear-gradient(135deg, #f59e0b 0%, #d97706); padding: 18px; border-radius: 12px; color: white; box-shadow: 0 4px 12px rgba(245,158,11,0.2);">
            <div style="font-size: 14px; font-weight: 600; opacity: 0.9;">Blížící se STK</div>
            <div style="font-size: 28px; font-weight: 800; margin-top: 5px;">{blizici_stk_pocet}</div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ==================== NAVIGACE ====================
st.markdown('### 🎛️ Hlavní menu')

tabs_list = [
    '🏢 Vozidla',
    '⚙️ Nastavení',
    '⛽ Tankování',
    '💳 Karty',
    '🛠️ Servis',
    '👥 Řidiči',
    '📊 Statistiky',
    '📱 QR Kód',
    '⚠️ Závady',
]

# Chytrá mobilní navigace - na mobilech hodíme rozevírací selectbox, na PC klasické dlaždice
is_mobile_view = st.checkbox("📱 Režim mobilního zobrazení (Menu jako rozevírací seznam)", value=False, help="Zaškrtni, pokud prohlížíš aplikaci na mobilu a chceš pohodlnější výběr v menu.")

if is_mobile_view:
    current_idx = tabs_list.index(st.session_state['active_tab']) if st.session_state['active_tab'] in tabs_list else 0
    selected_tab_mobile = st.selectbox("📌 Vyber sekci menu:", tabs_list, index=current_idx)
    if selected_tab_mobile != st.session_state['active_tab']:
        st.session_state['active_tab'] = selected_tab_mobile
        st.session_state['car_action'] = 'view'
        st.session_state['tank_action'] = 'view'
        st.session_state['servis_action'] = 'view'
        st.session_state['zavada_action'] = 'view'
        st.rerun()
else:
    nav_col1, nav_col2, nav_col3, nav_col4, nav_col5, nav_col6, nav_col7, nav_col8, nav_col9 = st.columns(9)
    cols_mapping = [nav_col1, nav_col2, nav_col3, nav_col4, nav_col5, nav_col6, nav_col7, nav_col8, nav_col9]
    
    for idx, title in enumerate(tabs_list):
        col = cols_mapping[idx]
        is_active = st.session_state['active_tab'] == title
        css_class = 'nav-tile-btn-active' if is_active else 'nav-tile-btn'

        with col:
            st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
            if st.button(title, key=f'nav_{title}'):
                st.session_state['active_tab'] = title
                st.session_state['car_action'] = 'view'
                st.session_state['tank_action'] = 'view'
                st.session_state['servis_action'] = 'view'
                st.session_state['zavada_action'] = 'view'
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

st.markdown('---')

akt_sekce = st.session_state['active_tab']

# ==================== 1. VOZIDLA ====================
if akt_sekce == '🏢 Vozidla':
    if st.session_state['car_action'] == 'add':
        st.header('➕ Přidat nové vozidlo')
        if st.button('🔙 Zpět na přehled vozidel'):
            st.session_state['car_action'] = 'view'
            st.rerun()

        with st.form('add_car_form'):
            c1, c2 = st.columns(2)
            with c1:
                new_spz = st.text_input('SPZ')
                new_nazev = st.text_input('Model')
                new_vin = st.text_input('VIN')
                new_pohonu = st.selectbox('Pohonná hmota', ['Nafta', 'Natural', 'Elektřina', 'LPG'])
                new_stk = st.text_input('STK do (YYYY-MM-DD)', value='2027-01-01')
            with c2:
                new_dz = st.text_input('DZ do (YYYY-MM-DD)', value='2027-01-01')
                new_pojisteni = st.text_input('Pojištění do (YYYY-MM-DD)', value='2027-01-01')
                new_ridic = st.text_input('Stálý řidič')
                new_pneu = st.text_input('Pneu (rozměr/typ)', value='Neuveden')
                new_pneu_druh = st.selectbox('Aktuálně obuto (Letní/Zimní)', ['Celoroční', 'Letní', 'Zimní'])

            if st.form_submit_button('Uložit vozidlo'):
                if new_spz:
                    pridat_auto(
                        new_spz, new_nazev, new_pohonu, new_stk, new_dz, new_pojisteni, new_pneu, new_pneu_druh, new_ridic, new_vin
                    )
                    st.success('Vozidlo přidáno do databáze!')
                    st.session_state['car_action'] = 'view'
                    st.rerun()
                else:
                    st.error('Zadejte prosím SPZ vozidla.')

    elif st.session_state['car_action'] == 'edit' and st.session_state['editing_spz']:
        spz_to_edit = st.session_state['editing_spz']
        st.header(f'✏️ Upravit vozidlo: {spz_to_edit}')
        if st.button('🔙 Zpět na přehled vozidel'):
            st.session_state['car_action'] = 'view'
            st.session_state['editing_spz'] = None
            st.rerun()

        df_auta = get_vsechna_auta()
        car_row = df_auta[df_auta['spz'] == spz_to_edit]

        if not car_row.empty:
            row = car_row.iloc[0]
            
            conn_sum = get_connection()
            df_s_servis = pd.read_sql_query("SELECT cena FROM servis WHERE spz=?", conn_sum, params=(spz_to_edit,))
            df_s_tank = pd.read_sql_query("SELECT cena FROM zaznamy WHERE spz=?", conn_sum, params=(spz_to_edit,))
            conn_sum.close()
            
            celkem_servis = df_s_servis['cena'].sum() if not df_s_servis.empty else 0.0
            celkem_palivo = df_s_tank['cena'].sum() if not df_s_tank.empty else 0.0
            celkem_naklady = celkem_servis + celkem_palivo
            
            st.markdown(
                f"""
                <div style="background: #eef2ff; border: 1px solid #c7d2fe; padding: 16px; border-radius: 12px; margin-bottom: 20px; display: flex; justify-content: space-around; text-align: center;">
                    <div><span style="font-size: 13px; color: #4338ca; display: block;">Celkem servis:</span><strong style="font-size: 18px; color: #312e81;">{celkem_servis:,.2f} Kč</strong></div>
                    <div style="border-left: 1px solid #c7d2fe; padding-left: 15px;"><span style="font-size: 13px; color: #4338ca; display: block;">Celkem palivo:</span><strong style="font-size: 18px; color: #312e81;">{celkem_palivo:,.2f} Kč</strong></div>
                    <div style="border-left: 1px solid #c7d2fe; padding-left: 15px;"><span style="font-size: 13px; color: #4338ca; display: block;">Celkové výdaje:</span><strong style="font-size: 18px; color: #1e1b4b;">{celkem_naklady:,.2f} Kč</strong></div>
                </div>
                """,
                unsafe_allow_html=True
            )

            with st.form(f'edit_car_form_{spz_to_edit}'):
                e_nazev = st.text_input('Model', value=row['nazev'])
                e_vin = st.text_input('VIN', value=row['vin'])
                
                palivo_opts = ['Nafta', 'Natural', 'Elektřina', 'LPG']
                akt_paliva = str(row['typ_pohonu']).strip()
                palivo_idx = palivo_opts.index(akt_paliva) if akt_paliva in palivo_opts else 0
                e_pohon = st.selectbox('Pohonná hmota', palivo_opts, index=palivo_idx)
                
                e_stk_do = st.text_input('STK do', value=row['stk_do'])
                e_dz = st.text_input('DZ do', value=row['dz_do'])
                e_pojisteni = st.text_input('Pojištění do', value=row['pojisteni_do'])
                e_pneu = st.text_input('Pneu rozměr', value=row['pneu_rozmer'])
                
                druhy_pneu = ['Celoroční', 'Letní', 'Zimní']
                akt_druh_pneu = str(row.get('pneu_druh', 'Celoroční')).strip()
                pneu_idx = druhy_pneu.index(akt_druh_pneu) if akt_druh_pneu in druhy_pneu else 0
                e_pneu_druh = st.selectbox('Aktuálně obuto', druhy_pneu, index=pneu_idx)
                
                e_ridic = st.text_input('Stálý řidič', value=row['staly_ridic'])

                if st.form_submit_button('Uložit změny'):
                    upravit_auto(
                        spz_to_edit, e_nazev, e_pohon, e_stk_do, e_dz, e_pojisteni, e_pneu, e_pneu_druh, e_ridic, e_vin
                    )
                    st.success('Vozidlo aktualizováno!')
                    st.session_state['car_action'] = 'view'
                    st.session_state['editing_spz'] = None
                    st.rerun()
        else:
            st.error('Vozidlo nebylo nalezeno v databázi.')
            if st.button('Zpět'):
                st.session_state['car_action'] = 'view'
                st.rerun()

    else:
        st.header('🏢 Dashboard vozidel')
        c_add, c_reset, c_viewtoggle = st.columns([1, 1, 1.5])
        with c_add:
            if st.button('➕ Přidat nové vozidlo'):
                st.session_state['car_action'] = 'add'
                st.rerun()
        with c_reset:
            if st.button('🔄 Obnovit/Opravit výchozí data'):
                obnovit_vychozi_auta()
                st.success('Data aut byla obnovena!')
                st.rerun()
        with c_viewtoggle:
            view_mode_selected = st.radio("Zobrazení:", ["Karty (Tile View)", "Tabulka"], horizontal=True, key="car_view_mode_radio")
            st.session_state['car_view_mode'] = view_mode_selected

        df_auta = get_vsechna_auta()
        
        # --- Zjištění aktivních závad pro zobrazení varování ---
        df_vsechny_zavady = get_zavady()
        aktivni_spz_kount = {}
        if not df_vsechny_zavady.empty:
            aktivni_df = df_vsechny_zavady[df_vsechny_zavady['stav'].astype(str).str.strip().str.lower() != 'opraveno']
            if not aktivni_df.empty:
                kount_series = aktivni_df.groupby(aktivni_df['spz'].astype(str).str.strip()).size()
                aktivni_spz_kount = kount_series.to_dict()
        
        search_auta = st.text_input("🔍 Hledat vozidlo (SPZ, model, řidič)...", "")
        if search_auta:
            mask = df_auta['spz'].str.contains(search_auta, case=False, na=False) | \
                   df_auta['nazev'].str.contains(search_auta, case=False, na=False) | \
                   df_auta['staly_ridic'].str.contains(search_auta, case=False, na=False)
            df_auta = df_auta[mask]

        if not df_auta.empty:
            dnes_Aktual = datetime.now().date()
            
            def get_semafor_html(dat_str):
                try:
                    d_dt = datetime.strptime(str(dat_str).strip(), '%Y-%m-%d').date()
                    dny_zbyva = (d_dt - dnes_Aktual).days
                    if dny_zbyva < 0:
                        return f'<span class="badge-red">Prošlo ({dat_str})</span>'
                    elif dny_zbyva <= 30:
                        return f'<span class="badge-orange">Končí za {dny_zbyva} d ({dat_str})</span>'
                    else:
                        return f'<span class="badge-green">{dat_str} (OK)</span>'
                except Exception:
                    return f'<span>{dat_str}</span>'

            if st.session_state['car_view_mode'] == 'Karty (Tile View)':
                num_cars = len(df_auta)
                for i in range(0, num_cars, 2):
                    cols = st.columns(2)
                    
                    row1 = df_auta.iloc[i]
                    pohon_raw1 = str(row1['typ_pohonu']).upper().strip()
                    if 'ELEKTŘINA' in pohon_raw1 or 'ELEKTRE' in pohon_raw1 or 'EV' in pohon_raw1:
                        card_class1 = 'car-card-green'
                    elif 'LPG' in pohon_raw1:
                        card_class1 = 'car-card-orange'
                    else:
                        card_class1 = 'car-card-blue'

                    stk_semafor_1 = get_semafor_html(row1['stk_do'])
                    dz_semafor_1 = get_semafor_html(row1['dz_do'])
                    poj_semafor_1 = get_semafor_html(row1['pojisteni_do'])
                    druh_pneu_text = row1.get('pneu_druh', 'Celoroční')
                    
                    spz_clean_1 = str(row1['spz']).strip()
                    if spz_clean_1 in aktivni_spz_kount:
                        pocet_1 = aktivni_spz_kount[spz_clean_1]
                        varovani_1 = f'<span style="color: #dc2626; font-size: 1.2em; margin-left: 8px;" title="Aktivní porucha!">⚠️ ({pocet_1})</span>'
                    else:
                        varovani_1 = ''

                    with cols[0]:
                        st.markdown(
                            f"""
                                <div class="{card_class1}">
                                    <h3 style="margin: 0;">🚗 {row1['nazev']}{varovani_1}</h3>
                                    <p style="margin: 4px 0;"><b>SPZ:</b> <span style="font-family: monospace; font-weight: 700;">{row1['spz']}</span></p>
                                    <p style="margin: 4px 0;"><b>Pohonná hmota:</b> {row1['typ_pohonu']}</p>
                                    <p style="margin: 4px 0;"><b>Stálý řidič:</b> {row1['staly_ridic']}</p>
                                    <p style="margin: 4px 0;"><b>STK do:</b> {stk_semafor_1} | <b>DZ do:</b> {dz_semafor_1}</p>
                                    <p style="margin: 4px 0;"><b>Pojištění do:</b> {poj_semafor_1}</p>
                                    <p style="margin: 4px 0;"><b>Pneu:</b> {row1['pneu_rozmer']} ({druh_pneu_text})</p>
                                    <p style="margin: 4px 0;"><b>VIN:</b> <span style="font-family: monospace;">{row1['vin']}</span></p>
                                </div>
                                """,
                            unsafe_allow_html=True,
                        )

                        col_btn1, col_btn2 = st.columns(2)
                        with col_btn1:
                            if st.button(f"✏️ Upravit {row1['spz']}", key=f"edit_btn_{row1['spz']}_{i}"):
                                st.session_state['car_action'] = 'edit'
                                st.session_state['editing_spz'] = row1['spz']
                                st.rerun()
                        with col_btn2:
                            st.markdown('<div class="delete-tile-btn">', unsafe_allow_html=True)
                            if st.button(f"🗑️ Smazat {row1['spz']}", key=f"del_btn_{row1['spz']}_{i}"):
                                smazat_auto(row1['spz'])
                                st.rerun()
                            st.markdown('</div>', unsafe_allow_html=True)

                    if i + 1 < num_cars:
                        row2 = df_auta.iloc[i + 1]
                        pohon_raw2 = str(row2['typ_pohonu']).upper().strip()
                        if 'ELEKTŘINA' in pohon_raw2 or 'ELEKTRE' in pohon_raw2 or 'EV' in pohon_raw2:
                            card_class2 = 'car-card-green'
                        elif 'LPG' in pohon_raw2:
                            card_class2 = 'car-card-orange'
                        else:
                            card_class2 = 'car-card-blue'

                        stk_semafor_2 = get_semafor_html(row2['stk_do'])
                        dz_semafor_2 = get_semafor_html(row2['dz_do'])
                        poj_semafor_2 = get_semafor_html(row2['pojisteni_do'])
                        druh_pneu_text2 = row2.get('pneu_druh', 'Celoroční')
                        
                        spz_clean_2 = str(row2['spz']).strip()
                        if spz_clean_2 in aktivni_spz_kount:
                            pocet_2 = aktivni_spz_kount[spz_clean_2]
                            varovani_2 = f'<span style="color: #dc2626; font-size: 1.2em; margin-left: 8px;" title="Aktivní porucha!">⚠️ ({pocet_2})</span>'
                        else:
                            varovani_2 = ''

                        with cols[1]:
                            st.markdown(
                                f"""
                                    <div class="{card_class2}">
                                        <h3 style="margin: 0;">🚗 {row2['nazev']}{varovani_2}</h3>
                                        <p style="margin: 4px 0;"><b>SPZ:</b> <span style="font-family: monospace; font-weight: 700;">{row2['spz']}</span></p>
                                        <p style="margin: 4px 0;"><b>Pohonná hmota:</b> {row2['typ_pohonu']}</p>
                                        <p style="margin: 4px 0;"><b>Stálý řidič:</b> {row2['staly_ridic']}</p>
                                        <p style="margin: 4px 0;"><b>STK do:</b> {stk_semafor_2} | <b>DZ do:</b> {dz_semafor_2}</p>
                                        <p style="margin: 4px 0;"><b>Pojištění do:</b> {poj_semafor_2}</p>
                                        <p style="margin: 4px 0;"><b>Pneu:</b> {row2['pneu_rozmer']} ({druh_pneu_text2})</p>
                                        <p style="margin: 4px 0;"><b>VIN:</b> <span style="font-family: monospace;">{row2['vin']}</span></p>
                                    </div>
                                    """,
                                unsafe_allow_html=True,
                            )

                            col_btn3, col_btn4 = st.columns(2)
                            with col_btn3:
                                if st.button(f"✏️ Upravit {row2['spz']}", key=f"edit_btn_{row2['spz']}_{i+1}"):
                                    st.session_state['car_action'] = 'edit'
                                    st.session_state['editing_spz'] = row2['spz']
                                    st.rerun()
                            with col_btn4:
                                st.markdown('<div class="delete-tile-btn">', unsafe_allow_html=True)
                                if st.button(f"🗑️ Smazat {row2['spz']}", key=f"del_btn_{row2['spz']}_{i+1}"):
                                    smazat_auto(row2['spz'])
                                    st.rerun()
                                st.markdown('</div>', unsafe_allow_html=True)
            else:
                df_table = df_auta.copy()
                df_table['stk_do'] = df_table['stk_do'].apply(get_semafor_html)
                df_table['dz_do'] = df_table['dz_do'].apply(get_semafor_html)
                df_table['pojisteni_do'] = df_table['pojisteni_do'].apply(get_semafor_html)
                
                def get_nazev_with_warning(r):
                    spz_c = str(r['spz']).strip()
                    if spz_c in aktivni_spz_kount:
                        return f"🚗 {r['nazev']} ⚠️ ({aktivni_spz_kount[spz_c]})"
                    return f"🚗 {r['nazev']}"

                df_table['nazev'] = df_table.apply(get_nazev_with_warning, axis=1)
                
                st.markdown('<div class="table-container">', unsafe_allow_html=True)
                render_styled_table(df_table[['spz', 'nazev', 'typ_pohonu', 'stk_do', 'dz_do', 'pojisteni_do', 'pneu_druh', 'staly_ridic']])
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info('Nic nebylo nalezeno.')

# ==================== 2. NASTAVENÍ ====================
elif akt_sekce == '⚙️ Nastavení':
    st.header('⚙️ Nastavení aplikace & Notifikace')
    conn = get_connection()
    cursor = conn.cursor()
    cena_kwh = cursor.execute("SELECT hodnota FROM nastaveni WHERE klic = 'cena_kwh'").fetchone()[0]
    admin_h = cursor.execute("SELECT hodnota FROM nastaveni WHERE klic = 'admin_heslo'").fetchone()[0]
    
    res_mail = cursor.execute("SELECT hodnota FROM nastaveni WHERE klic = 'sefka_mail'").fetchone()
    sefka_mail_val = res_mail[0] if res_mail else 'rhjvedeni@gmail.com'
    
    res_mob = cursor.execute("SELECT hodnota FROM nastaveni WHERE klic = 'sefka_mobil'").fetchone()
    sefka_mobil_val = res_mob[0] if res_mob else ''
    conn.close()

    with st.form('nastaveni_form'):
        st.subheader("Pravidla a zabezpečení")
        nova_cena = st.number_input('Cena elektřiny za kWh (Kč)', value=float(cena_kwh), format='%.2f')
        nove_heslo = st.text_input('Změnit administrátorské heslo', value=str(admin_h), type='password')
        
        st.markdown('---')
        st.subheader("📬 Notifikace pro vedení (Šéfka)")
        st.markdown("Zde lze nastavit kam (e-mail / mobilní číslo) budou směřovat upozornění na blížící se STK, dálniční známky, pojištění, propadlé řidičáky a jiné výstrahy.")
        
        novy_mail = st.text_input('E-mail pro notifikace', value=str(sefka_mail_val))
        novy_mobil = st.text_input('Mobilní číslo pro notifikace', value=str(sefka_mobil_val), placeholder="+420 777 000 000")
        
        if st.form_submit_button('Uložit nastavení'):
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE nastaveni SET hodnota = ? WHERE klic = "cena_kwh"', (str(nova_cena),))
            cursor.execute('UPDATE nastaveni SET hodnota = ? WHERE klic = "admin_heslo"', (str(nove_heslo),))
            cursor.execute('INSERT OR REPLACE INTO nastaveni (klic, hodnota) VALUES ("sefka_mail", ?)', (str(novy_mail),))
            cursor.execute('INSERT OR REPLACE INTO nastaveni (klic, hodnota) VALUES ("sefka_mobil", ?)', (str(novy_mobil),))
            conn.commit()
            conn.close()
            st.success('Nastavení a notifikační kontakty úspěšně uloženy!')

# ==================== 3. TANKOVÁNÍ ====================
elif akt_sekce == '⛽ Tankování':
    st.header('⛽ Evidence tankování a nabíjení')

    if st.session_state['tank_action'] == 'add':
        if st.button('🔙 Zpět na přehled tankování'):
            st.session_state['tank_action'] = 'view'
            st.rerun()

        with st.form('add_tank_form'):
            df_auta = get_vsechna_auta()
            spz_list = df_auta['spz'].tolist() if not df_auta.empty else []
            t_spz = st.selectbox('Vozidlo (SPZ)', spz_list)
            
            auto_info = df_auta[df_auta['spz'] == t_spz].iloc[0] if not df_auta.empty and t_spz in df_auta['spz'].values else None
            typ_pohonu_aut = auto_info['typ_pohonu'] if auto_info is not None else 'Nafta'
            
            t_ridic = st.text_input('Řidič')
            t_km = st.number_input('Stav tachometru (km)', min_value=0, step=100)
            t_zdroj = st.selectbox(
                'Zdroj / Typ paliva / Čerpací stanice', ['Čerpací stanice', 'Wallbox', 'Zasuvka 220', 'Veřejná nabíječka', 'Nafta', 'Natural', 'LPG', 'Elektřina']
            )
            t_mnozstvi = st.number_input('Množství (litry / kWh)', min_value=0.0, step=1.0)
            t_cena = st.number_input('Celková cena (Kč)', min_value=0.0, step=10.0)
            if st.form_submit_button('Uložit záznam'):
                pridat_zaznam_paliva(t_spz, t_ridic, t_km, t_zdroj, t_mnozstvi, t_cena)
                st.success('Záznam o tankování/nabíjení byl přidán!')
                st.session_state['tank_action'] = 'view'
                st.rerun()
    else:
        c_t1, c_t2 = st.columns(2)
        with c_t1:
            if st.button('➕ Přidat nový záznam tankování'):
                st.session_state['tank_action'] = 'add'
                st.rerun()
        
        df_zaz = get_zaznamy_paliva()
        search_tank = st.text_input("🔍 Hledat záznam (SPZ nebo řidič)...", "")
        if search_tank:
            mask = df_zaz['spz'].str.contains(search_tank, case=False, na=False) | df_zaz['ridic'].str.contains(search_tank, case=False, na=False)
            df_zaz = df_zaz[mask]

        if not df_zaz.empty:
            df_zaz = df_zaz.sort_values(by=['spz', 'km'], ascending=[True, True])
            df_zaz['spotreba_na_100km'] = None
            spotreby_list = []
            
            for spz_group, group in df_zaz.groupby('spz'):
                group = group.sort_values(by='km')
                prev_km = None
                for idx, row in group.iterrows():
                    akt_km, akt_mnoz = row['km'], row['mnozstvi']
                    if prev_km is not None and akt_km > prev_km:
                        ujeto = akt_km - prev_km
                        if ujeto > 0:
                            spotreby_list.append((idx, (akt_mnoz / ujeto) * 100))
                    prev_km = akt_km
            
            if spotreby_list:
                df_spotreby = pd.DataFrame(spotreby_list, columns=['idx', 'spotreba'])
                df_zaz.loc[df_spotreby['idx'], 'spotreba_na_100km'] = df_spotreby['spotreba'].round(2)

            render_styled_table(df_zaz.sort_values(by='datum', ascending=False))
        else:
            st.info('Nic nebylo nalezeno.')

# ==================== 4. KARTY ====================
elif akt_sekce == '💳 Karty':
    st.header('💳 Evidence firemních tankovacích karet')
    
    with st.form('add_karta_form'):
        st.subheader('Přidat / Upravit kartu')
        c1, c2, c3 = st.columns(3)
        with c1:
            k_cislo = st.text_input('Číslo karty (nebo název)')
        with c2:
            df_rid = get_ridici()
            ridici_list = df_rid['jmeno'].tolist() if not df_rid.empty else []
            df_auta_k = get_vsechna_auta()
            if not df_auta_k.empty:
                ridici_list.extend(df_auta_k['staly_ridic'].tolist())
            ridici_list = sorted(list(set([r for r in ridici_list if r != 'Neuveden'])))
            k_ridic = st.selectbox('Přiřazený řidič', ['Neznámý'] + ridici_list)
        with c3:
            k_limit = st.number_input('Měsíční limit (Kč)', min_value=0.0, step=1000.0, value=10000.0)
            
        if st.form_submit_button('Uložit kartu'):
            if k_cislo.strip():
                pridat_kartu(k_cislo.strip(), k_ridic, k_limit)
                st.success(f"Karta {k_cislo} úspěšně uložena!")
                st.rerun()
            else:
                st.error("Zadejte číslo karty.")
                
    st.markdown('---')
    df_karty = get_karty()
    if not df_karty.empty:
        st.subheader('Přehled karet a čerpání v aktuálním měsíci')
        
        df_palivo = get_zaznamy_paliva()
        akt_mesic = datetime.now().strftime('%Y-%m')
        
        karty_data = []
        anomalie_karty = []
        
        for _, row in df_karty.iterrows():
            ridic_k = row['ridic']
            limit_k = row['mesicni_limit']
            utraceno = 0.0
            
            if not df_palivo.empty:
                df_p_mesic = df_palivo[pd.to_datetime(df_palivo['datum'], errors='coerce').dt.strftime('%Y-%m') == akt_mesic]
                utraceno = df_p_mesic[df_p_mesic['ridic'] == ridic_k]['cena'].sum()
                
            stav = "✅ OK"
            if limit_k > 0 and utraceno > limit_k:
                stav = "🚨 PŘEKROČENO"
                anomalie_karty.append(f"⚠️ Řidič **{ridic_k}** překročil limit na kartě {row['cislo_karty']}! (Limit: {limit_k:,.0f} Kč, Utraceno: {utraceno:,.0f} Kč)")
                
            karty_data.append({
                'Číslo karty': row['cislo_karty'],
                'Řidič': ridic_k,
                'Měsíční limit (Kč)': limit_k,
                'Utraceno tento měsíc (Kč)': utraceno,
                'Stav': stav
            })
            
        df_karty_view = pd.DataFrame(karty_data)
        
        if anomalie_karty:
            st.markdown("#### 🚨 Detekované anomálie na kartách")
            for anom in anomalie_karty:
                st.warning(anom)
                
        render_styled_table(df_karty_view)
        
        st.markdown('#### Smazat kartu')
        karta_del = st.selectbox("Vyberte kartu k odstranění", df_karty['cislo_karty'].tolist())
        if st.button("Odstranit vybranou kartu"):
            smazat_kartu(karta_del)
            st.rerun()
    else:
        st.info("Zatím nejsou evidovány žádné karty.")

# ==================== 5. SERVIS ====================
elif akt_sekce == '🛠️ Servis':
    st.header('🛠️ Servisní záznamy')
    
    st.markdown("""
        <div style="padding: 18px; border-radius: 12px; border: 1px solid #d1cce3; margin-bottom: 20px; box-shadow: 0 2px 6px rgba(0,0,0,0.02);">
            <h4 style="margin-top: 0;">🔗 Doporučení partneři a e-shopy pro náhradní díly</h4>
            <div style="display: flex; gap: 15px; flex-wrap: wrap; margin-top: 12px;">
                <a href="https://www.autorozvody.cz/cs" target="_blank" style="padding: 10px 16px; border: 1px solid #e2e8f0; border-radius: 8px; font-weight: 600; text-decoration: none; display: inline-flex; align-items: center; gap: 6px;">🌐 Autorozvody</a>
                <a href="https://www.autodoc.cz/" target="_blank" style="padding: 10px 16px; border: 1px solid #e2e8f0; border-radius: 8px; font-weight: 600; text-decoration: none; display: inline-flex; align-items: center; gap: 6px;">🌐 AutoDoc</a>
                <a href="https://cz.intercars.com/" target="_blank" style="padding: 10px 16px; border: 1px solid #e2e8f0; border-radius: 8px; font-weight: 600; text-decoration: none; display: inline-flex; align-items: center; gap: 6px;">🌐 Inter Cars</a>
                <a href="https://www.autodily-cardo.cz/" target="_blank" style="padding: 10px 16px; border: 1px solid #e2e8f0; border-radius: 8px; font-weight: 600; text-decoration: none; display: inline-flex; align-items: center; gap: 6px;">🌐 Autodíly Cardo</a>
                <a href="https://www.autodily-pema.cz/?cfpm_ref=https%3A%2F%2Fwww.google.com%2F" target="_blank" style="padding: 10px 16px; border: 1px solid #e2e8f0; border-radius: 8px; font-weight: 600; text-decoration: none; display: inline-flex; align-items: center; gap: 6px;">🌐 Autodíly Pema</a>
            </div>
        </div>
    """, unsafe_allow_html=True)

    if st.session_state['servis_action'] == 'add':
        if st.button('🔙 Zpět na přehled servisu'):
            st.session_state['servis_action'] = 'view'
            st.rerun()

        with st.form('add_servis_form'):
            df_auta = get_vsechna_auta()
            spz_list = df_auta['spz'].tolist() if not df_auta.empty else []
            s_spz = st.selectbox('Vozidlo (SPZ)', spz_list)
            s_ridic = st.text_input('Zadal / Řidič')
            s_km = st.number_input('Stav tachometru (km)', min_value=0, step=100)
            s_kat = st.selectbox('Kategorie servisu', ['Výměna oleje', 'Pneu', 'STK', 'Brzdy', 'Oprava motoru', 'Ostatní'])
            s_popis = st.text_area('Popis servisu / opravy')
            s_cena = st.number_input('Cena (Kč)', min_value=0.0, step=100.0)

            if st.form_submit_button('Uložit servisní záznam'):
                pridat_servisni_zaznam(s_spz, s_km, s_kat, s_popis, s_cena, s_ridic)
                st.success('Uloženo!')
                st.session_state['servis_action'] = 'view'
                st.rerun()
    else:
        if st.button('➕ Přidat nový servisní záznam'):
            st.session_state['servis_action'] = 'add'
            st.rerun()

        df_servis = get_zaznamy_servis()
        search_servis = st.text_input("🔍 Hledat servisní záznam (SPZ nebo řidič)...", "")
        if search_servis:
            mask = df_servis['spz'].str.contains(search_servis, case=False, na=False) | df_servis['ridic'].str.contains(search_servis, case=False, na=False)
            df_servis = df_servis[mask]

        if not df_servis.empty:
            render_styled_table(df_servis)
        else:
            st.info('Žádné servisní záznamy nenalezeny.')

# ==================== 6. ŘIDIČI ====================
elif akt_sekce == '👥 Řidiči':
    st.header('👥 Správa řidičů')
    with st.form('add_driver_form'):
        d_jmeno = st.text_input('Jméno a příjmení')
        d_telefon = st.text_input('Telefonní číslo')
        d_ridicak = st.text_input('Platnost řidičáku (YYYY-MM-DD)', value='2028-01-01')
        if st.form_submit_button('Uložit řidiče'):
            if d_jmeno.strip():
                pridat_ridice(d_jmeno.strip(), d_telefon, d_ridicak)
                st.success(f"Řidič {d_jmeno} uložen!")
                st.rerun()
                
    st.markdown('---')
    df_rid = get_ridici()
    if not df_rid.empty:
        render_styled_table(df_rid)
        ridic_del = st.selectbox("Vyberte řidiče k odstranění", df_rid['jmeno'].tolist())
        if st.button("Odstranit vybraného řidiče"):
            r_row_match = df_rid[df_rid['jmeno'] == ridic_del]
            if not r_row_match.empty:
                smazat_ridice(int(r_row_match.iloc[0]['id']))
                st.rerun()
    else:
        st.info("Nejsou evidováni žádní řidiči.")

# ==================== 7. STATISTIKY ====================
elif akt_sekce == '📊 Statistiky':
    st.header('📊 Statistiky a export dat')
    
    df_s_stat = get_zaznamy_servis()
    df_p_stat = get_zaznamy_paliva()
    df_a_stat = get_vsechna_auta()
    
    if not df_s_stat.empty or not df_p_stat.empty:
        
        # Sestavení dat pro export
        naklady_vozidla = []
        for _, av in df_a_stat.iterrows():
            s_sum = df_s_stat[df_s_stat['spz'] == av['spz']]['cena'].sum() if not df_s_stat.empty else 0.0
            p_sum = df_p_stat[df_p_stat['spz'] == av['spz']]['cena'].sum() if not df_p_stat.empty else 0.0
            naklady_vozidla.append({'SPZ': av['spz'], 'Vozidlo': av['nazev'], 'Servis': s_sum, 'Palivo': p_sum, 'Celkem': s_sum + p_sum})
        df_nakl_vozidla = pd.DataFrame(naklady_vozidla)
        
        # Export tlačítko
        csv_data = df_nakl_vozidla.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 Stáhnout měsíční report pro účetní (CSV/Excel)",
            data=csv_data,
            file_name=f"report_nakladu_{aktualni_mesic}.csv",
            mime="text/csv",
            type="primary"
        )
        st.markdown('---')
        
        c_graf1, c_graf2 = st.columns(2)
        with c_graf1:
            st.subheader("Rozložení nákladů (Aktuální měsíc)")
            pie_df = pd.DataFrame({
                'Kategorie': ['Nafta/Natural', 'Elektřina', 'Díly a servis'],
                'Kč': [naklady_nafta_natural, naklady_dobijeni, naklady_dily_servis]
            })
            pie_df = pie_df[pie_df['Kč'] > 0]
            if not pie_df.empty:
                fig_pie = px.pie(pie_df, names='Kategorie', values='Kč', hole=0.4, color_discrete_sequence=['#3b82f6', '#10b981', '#ef4444'])
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("Žádné náklady tento měsíc.")

        with c_graf2:
            st.subheader("Vývoj nákladů v čase")
            df_all_p = df_p_stat.copy()
            df_all_s = df_s_stat.copy()
            
            if not df_all_p.empty:
                df_all_p['mesic'] = pd.to_datetime(df_all_p['datum'], errors='coerce').dt.to_period('M').astype(str)
                trend_p = df_all_p.groupby('mesic')['cena'].sum().reset_index()
                trend_p['Typ'] = 'Palivo/Energie'
            else:
                trend_p = pd.DataFrame(columns=['mesic', 'cena', 'Typ'])
                
            if not df_all_s.empty:
                df_all_s['mesic'] = pd.to_datetime(df_all_s['datum'], errors='coerce').dt.to_period('M').astype(str)
                trend_s = df_all_s.groupby('mesic')['cena'].sum().reset_index()
                trend_s['Typ'] = 'Servis'
            else:
                trend_s = pd.DataFrame(columns=['mesic', 'cena', 'Typ'])
                
            trend_df = pd.concat([trend_p, trend_s]).sort_values('mesic')
            if not trend_df.empty:
                fig_line = px.bar(trend_df, x='mesic', y='cena', color='Typ', barmode='group', color_discrete_sequence=['#3b82f6', '#ef4444'])
                st.plotly_chart(fig_line, use_container_width=True)
                
        st.subheader("Tabulka nákladů dle vozidel (celkem)")
        render_styled_table(df_nakl_vozidla)
    else:
        st.info("Nejsou k dispozici data pro statistiky.")
        
    st.markdown('---')
    st.subheader('🛢️ Evidence dobíjení a tankování (dle řidičů a vozidel)')
    df_palivo_stat = get_zaznamy_paliva()
    if not df_palivo_stat.empty:
        c_stat1, c_stat2 = st.columns(2)
        with c_stat1:
            st.markdown('#### 👤 Podle řidičů')
            df_ridici_aggr = df_palivo_stat.groupby('ridic').agg(
                Pocet_Tankovani=('id', 'count'),
                Celkem_Mnozstvi=('mnozstvi', 'sum'),
                Celkem_Cena=('cena', 'sum')
            ).reset_index().rename(columns={'ridic': 'Řidič', 'Pocet_Tankovani': 'Počet', 'Celkem_Mnozstvi': 'Objem', 'Celkem_Cena': 'Kč'})
            render_styled_table(df_ridici_aggr.sort_values(by='Kč', ascending=False))
        with c_stat2:
            st.markdown('#### 🚗 Podle vozidel')
            df_auta_aggr = df_palivo_stat.groupby('spz').agg(
                Pocet_Tankovani=('id', 'count'),
                Celkem_Mnozstvi=('mnozstvi', 'sum'),
                Celkem_Cena=('cena', 'sum')
            ).reset_index().rename(columns={'spz': 'SPZ', 'Pocet_Tankovani': 'Počet', 'Celkem_Mnozstvi': 'Objem', 'Celkem_Cena': 'Kč'})
            render_styled_table(df_auta_aggr.sort_values(by='Kč', ascending=False))
        
        st.markdown('#### 🚨 Upozornění na anomálie v tankování')
        df_palivo_stat = df_palivo_stat.sort_values(by=['spz', 'km'], ascending=[True, True])
        anomalie_seznam = []
        
        for spz_group, group in df_palivo_stat.groupby('spz'):
            group = group.sort_values(by='km')
            prev_km = None
            for idx, row in group.iterrows():
                akt_km = row['km']
                akt_mnoz = row['mnozstvi']
                ridic = row['ridic']
                
                if akt_mnoz > 120:
                    anomalie_seznam.append(f"⚠️ **Extrémní objem:** Vozidlo **{spz_group}** ({ridic}) nabralo **{akt_mnoz}** l/kWh naráz.")

                if prev_km is not None and akt_km > prev_km:
                    ujeto = akt_km - prev_km
                    if ujeto > 0:
                        spotreba = (akt_mnoz / ujeto) * 100
                        if spotreba > 25.0:
                            anomalie_seznam.append(f"⚠️ **Vysoká spotřeba:** Vozidlo **{spz_group}** ({ridic}) hlásí **{spotreba:.1f}** na 100 km.")
                prev_km = akt_km
        
        if anomalie_seznam:
            for an in list(dict.fromkeys(anomalie_seznam)): # Odstranění duplicit
                st.warning(an)
        else:
            st.success("✅ Všechna tankování a spotřeby jsou v normě.")
    else:
        st.info("Zatím chybí data o tankování.")

    # ==================== UPOZORNĚNÍ PANEL (pouze ve statistikách) ====================
    upoz_stk, upoz_dz, upoz_poj, upoz_olej, upoz_ridicaky, upoz_pneu = ziskej_upozorneni()
    if any([upoz_stk, upoz_dz, upoz_poj, upoz_olej, upoz_ridicaky, upoz_pneu]):
        st.markdown('---')
        st.subheader('🚨 Centrální upozornění flotily')
        
        uc1, uc2, uc3 = st.columns(3)
        with uc1:
            st.markdown('<div class="alert-box">#### 🛡️ STK & Dálniční známky', unsafe_allow_html=True)
            for i in upoz_stk + upoz_dz: st.markdown(i)
            st.markdown('</div>', unsafe_allow_html=True)
            
        with uc2:
            st.markdown('<div class="alert-box">#### 📄 Pojištění & Řidičáky', unsafe_allow_html=True)
            for i in upoz_poj + upoz_ridicaky: st.markdown(i)
            st.markdown('</div>', unsafe_allow_html=True)
            
        with uc3:
            st.markdown('<div class="alert-box">#### 🛢️ Servis a Pneumatiky', unsafe_allow_html=True)
            st.markdown('<div class="oil-scroll-container">', unsafe_allow_html=True)
            for i in upoz_olej + upoz_pneu: st.markdown(i)
            st.markdown('</div></div>', unsafe_allow_html=True)

# ==================== 8. QR KÓD ====================
elif akt_sekce == '📱 QR Kód':
    st.header('📱 Generátor QR kódů')
    df_auta_qr = get_vsechna_auta()
    if not df_auta_qr.empty:
        qr_rezim = st.radio("Zvolte režim QR kódů", ["Jednotlivý QR kód", "Hromadná mřížka pro tisk (všechna auta)"], horizontal=True)
        
        if qr_rezim == "Jednotlivý QR kód":
            qr_sel = st.selectbox("Vyberte vozidlo", df_auta_qr['spz'].tolist())
            sel_row = df_auta_qr[df_auta_qr['spz'] == qr_sel].iloc[0]
            qr_drv = st.text_input("Předvyplnit řidiče", value=sel_row['staly_ridic'])
            app_url = f"http://{socket.gethostbyname(socket.gethostname())}:8501/?spz={qr_sel}&ridic={qr_drv}"
            st.markdown(f"**URL:** `{app_url}`")
            img_bytes = generuj_qr_kod(app_url)
            st.image(img_bytes, width=300)
            st.download_button("Stáhnout QR", data=img_bytes, file_name=f"qr_{qr_sel}.png", mime="image/png")
        else:
            st.markdown("### 🖨️ Hromadný tisk QR kódů (karty do peněženky / na stínítko)")
            
            # Volba mřížky
            mrizka_styl = st.radio("Vyberte rozvržení mřížky na stránku:", ["3x3 (9 kódů na stránku)", "4x4 (16 kódů na stránku - menší)"], horizontal=True)
            
            col_tisk1, col_tisk2 = st.columns([1, 4])
            with col_tisk1:
                # Tlačítko pro vyvolání systémového tiskového dialogu
                components.html(
                    """
                    <button onclick="window.print();" style="background-color: #5b4b8a; color: white; padding: 12px 20px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; font-size: 15px; width: 100%; box-shadow: 0 4px 12px rgba(91,75,138,0.3);">
                        🖨️ Vytisknout stránku
                    </button>
                    """,
                    height=50
                )
            
            cols_count = 3 if "3x3" in mrizka_styl else 4
            qr_size = 110 if "4x4" in mrizka_styl else 140
            
            # Generování mřížky
            auta_seznam = df_auta_qr.to_dict('records')
            pocet_aut = len(auta_seznam)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            for i in range(0, pocet_aut, cols_count):
                cols = st.columns(cols_count)
                for j in range(cols_count):
                    if i + j < pocet_aut:
                        car = auta_seznam[i + j]
                        spz_val = car['spz']
                        nazev_val = car['nazev']
                        ridic_val = car['staly_ridic'] if car['staly_ridic'] != 'Neuveden' else 'Řidič'
                        
                        target_url = f"http://{socket.gethostbyname(socket.gethostname())}:8501/?spz={spz_val}&ridic={ridic_val}"
                        qr_bytes = generuj_qr_kod(target_url)
                        
                        with cols[j]:
                            st.markdown(
                                f"""
                                <div style="border: 2px dashed #b1a7d1; border-radius: 8px; padding: 8px; text-align: center; margin-bottom: 10px; background: white; page-break-inside: avoid;">
                                    <div style="font-size: 13px; font-weight: 700; color: #1e1b29; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{nazev_val}</div>
                                    <div style="font-family: monospace; font-size: 15px; font-weight: 900; color: #5b4b8a; margin: 2px 0;">{spz_val}</div>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                            # Zobrazení QR kódów
                            st.image(qr_bytes, width=qr_size)
                            st.markdown(f"<p style='text-align: center; font-size: 11px; color: #555; margin-top: -5px;'>{ridic_val}</p>", unsafe_allow_html=True)

# ==================== 9. ZÁVADY ====================
elif akt_sekce == '⚠️ Závady':
    st.header('⚠️ Hlášené závady')
    df_zavady = get_zavady()
    
    if not df_zavady.empty:
        df_zavady_aktivni = df_zavady[df_zavady['stav'] != 'Opraveno']
        df_zavady_opravene = df_zavady[df_zavady['stav'] == 'Opraveno']
        
        st.subheader("🚨 Aktivní poruchy (Čeká na opravu)")
        if not df_zavady_aktivni.empty:
            render_styled_table(df_zavady_aktivni)
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Vyřešit závadu**")
                z_sel_id_oprava = st.selectbox("Vyberte ID k vyřízení:", df_zavady_aktivni['id'].tolist(), key="oprava_sel")
                if st.button("✅ Zadat jako OPRAVENO"):
                    oznacit_zavadu_opraveno(int(z_sel_id_oprava))
                    st.rerun()
            with c2:
                st.markdown("**Smazat chybný záznam**")
                z_sel_id_smazat = st.selectbox("Vyberte ID ke smazání:", df_zavady_aktivni['id'].tolist(), key="smazat_sel_1")
                if st.button("🗑️ Smazat vybranou závadu"):
                    smazat_zavadu(int(z_sel_id_smazat))
                    st.rerun()
        else:
            st.success("Aktuálně neevidujeme žádné aktivní závady!")
            
        if not df_zavady_opravene.empty:
            st.markdown('---')
            st.subheader("✅ Historie opravených závad")
            render_styled_table(df_zavady_opravene)
            
            z_sel_id_historie = st.selectbox("Vyberte ID z historie ke smazání:", df_zavady_opravene['id'].tolist(), key="smazat_sel_2")
            if st.button("🗑️ Smazat záznam z historie"):
                smazat_zavadu(int(z_sel_id_historie))
                st.rerun()
    else:
        st.info("Žádné nahlášené závady.")
