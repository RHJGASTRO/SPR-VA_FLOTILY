# VERZE 4.1.3 - Správa flotily - RHJ Gastro (Final Master Release - QR & Hosting Fixed)
# ==============================================================================
import hashlib
import io
import os
import re
import socket
import sqlite3
from datetime import datetime, timedelta
from urllib.parse import quote
import pandas as pd
import plotly.express as px
import qrcode
import streamlit as st

DB_NAME = 'flotila.db'
# Zabezpečený hash supervizorského hesla (původně 'supervisor789')
SUPERVISOR_PASSWORD_HASH = hashlib.sha256('supervisor789'.encode()).hexdigest()


def get_connection():
    return sqlite3.connect(DB_NAME, timeout=10)


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auta (
                spz TEXT PRIMARY KEY,
                nazev TEXT NOT NULL,
                typ_pohonu TEXT NOT NULL,
                stk_do TEXT,
                dz_do TEXT,
                pojisteni_do TEXT,
                pneu_rozmer TEXT,
                staly_ridic TEXT,
                vin TEXT,
                olej_interval INTEGER DEFAULT 10000
            )
        """)
        
        try:
            cursor.execute("SELECT pojisteni_do FROM auta LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE auta ADD COLUMN pojisteni_do TEXT")

        cursor.execute("SELECT COUNT(*) FROM auta")
        if cursor.fetchone()[0] == 0:
            vychozi_auta = [
                ("2M88435", "Fiat Doblo", "Natural", "2027-01-01", "2027-01-01", "2027-01-01", "175/70 R14 (88T XL)", "Kolářová Zuzana", "ZFA22300005463005", 10000),
                ("4B33954", "Fiat Doblo", "Natural", "2027-01-01", "2027-01-01", "2027-01-01", "175/70 R14 (88T XL)", "Švadlenková Denisa", "ZFA22300005443286", 10000),
                ("5E81583", "Volkswagen Caddy", "Nafta", "2027-01-01", "2027-01-01", "2027-01-01", "195/65 R15 (95T XL)", "Lokaj Martin", "WV1ZZZ2KZ9X101365", 10000),
                ("5E94630", "Volkswagen Caddy", "Nafta", "2027-01-01", "2027-01-01", "2027-01-01", "195/65 R15 (95T XL)", "NÁHRADNÍ", "WV1ZZZ2KZAX049128", 10000),
                ("5Z49372", "Citroen Jumpy", "Nafta", "2027-01-01", "2027-01-01", "2027-01-01", "215/60 R16C 103/101T (103/101)", "Mukařovský Martin", "VF7XUAH8FZ013373", 10000),
                ("6E14928", "Fiat Doblo", "Natural", "2027-01-01", "2027-01-01", "2027-01-01", "175/70 R14 (88T XL)", "Doležal Martin", "ZFA22300005374486", 10000),
                ("6E24392", "Fiat Doblo LPG - náhradní", "Natural", "2027-01-01", "2027-01-01", "2027-01-01", "175/70 R14 (88T XL)", "NÁHRADNÍ", "ZFA22300005559273", 10000),
                ("6E74807", "Ford Transit", "Nafta", "2027-01-01", "2027-01-01", "2027-01-01", "195/70 R15C (104/102R)", "Balog Marcel", "WF0SXXTTFS8R16015", 10000),
                ("6E85382", "Peugeot Partner", "Nafta", "2027-01-01", "2027-01-01", "2027-01-01", "195/65 R15 (91H)", "Sejpková Anna Marie", "VF3XT9HMOCZ005574", 10000),
                ("6E94181", "IVECO", "Nafta", "2027-01-01", "2027-01-01", "2027-01-01", "215/75 R17.5 (126/124M)", "ODPADY", "ZCFA80F0002004883", 10000),
            ]
            for auto in vychozi_auta:
                cursor.execute("""
                    INSERT OR IGNORE INTO auta (spz, nazev, typ_pohonu, stk_do, dz_do, pojisteni_do, pneu_rozmer, staly_ridic, vin, olej_interval)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, auto)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS zaznamy (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spz TEXT NOT NULL,
                ridic TEXT,
                datum TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                km INTEGER NOT NULL,
                zdroj TEXT NOT NULL,
                mnozstvi REAL NOT NULL,
                cena REAL NOT NULL,
                procenta_od REAL DEFAULT 0,
                procenta_do REAL DEFAULT 0,
                teplota REAL DEFAULT 0
            )
        """)
        
        for col, definition in [('procenta_od', 'REAL DEFAULT 0'), ('procenta_do', 'REAL DEFAULT 0'), ('teplota', 'REAL DEFAULT 0')]:
            try:
                cursor.execute(f"SELECT {col} FROM zaznamy LIMIT 1")
            except sqlite3.OperationalError:
                cursor.execute(f"ALTER TABLE zaznamy ADD COLUMN {col} {definition}")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS servis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spz TEXT NOT NULL,
                ridic TEXT,
                datum DATE DEFAULT CURRENT_DATE,
                km INTEGER NOT NULL,
                kategorie TEXT NOT NULL,
                popis TEXT NOT NULL,
                cena REAL NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS zavady (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spz TEXT NOT NULL,
                ridic TEXT,
                datum TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                popis TEXT NOT NULL,
                stav TEXT DEFAULT 'Nahlášeno'
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ridici (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                jmeno TEXT NOT NULL UNIQUE,
                telefon TEXT,
                ridicak_do TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nastaveni (
                klic TEXT PRIMARY KEY,
                hodnota TEXT NOT NULL
            )
        """)

        cursor.execute(
            "INSERT OR IGNORE INTO nastaveni (klic, hodnota) VALUES ('cena_kwh', '6.50')"
        )
        # Výchozí heslo admin123 uložené jako hash
        default_admin_hash = hashlib.sha256('admin123'.encode()).hexdigest()
        cursor.execute(
            "INSERT OR IGNORE INTO nastaveni (klic, hodnota) VALUES ('admin_heslo_hash', ?)", (default_admin_hash,)
        )
        # Migrace starého textového hesla na hash, pokud existuje
        cursor.execute("SELECT hodnota FROM nastaveni WHERE klic = 'admin_heslo'")
        old_pass_row = cursor.fetchone()
        if old_pass_row:
            old_pass = old_pass_row[0]
            if len(old_pass) != 64:  # Není to sha256 hash
                new_hash = hashlib.sha256(old_pass.encode()).hexdigest()
                cursor.execute("UPDATE nastaveni SET hodnota = ? WHERE klic = 'admin_heslo_hash'", (new_hash,))
            cursor.execute("DELETE FROM nastaveni WHERE klic = 'admin_heslo'")
        conn.commit()


def ziskej_admin_heslo_hash():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT hodnota FROM nastaveni WHERE klic = 'admin_heslo_hash'")
        row = cursor.fetchone()
        return row[0] if row else hashlib.sha256('admin123'.encode()).hexdigest()


def get_vsechna_auta():
    with get_connection() as conn:
        df = pd.read_sql_query(
            'SELECT spz, nazev, typ_pohonu, staly_ridic, stk_do, dz_do, pojisteni_do, pneu_rozmer, vin, olej_interval FROM auta',
            conn,
        )
    df = df.fillna('Neuveden')
    df.replace(['None', 'nan', ''], 'Neuveden', inplace=True)
    return df


def get_zaznamy_paliva():
    with get_connection() as conn:
        df = pd.read_sql_query(
            'SELECT id, spz, ridic, datum, km, zdroj, mnozstvi, cena, procenta_od, procenta_do, teplota FROM zaznamy ORDER BY datum DESC',
            conn,
        )
    return df


def get_zaznamy_servis():
    with get_connection() as conn:
        df = pd.read_sql_query(
            'SELECT id, spz, ridic, datum, km, kategorie, popis, cena FROM servis ORDER BY datum DESC',
            conn,
        )
    return df


def get_zavady():
    with get_connection() as conn:
        df = pd.read_sql_query(
            'SELECT id, spz, ridic, datum, popis, stav FROM zavady ORDER BY datum DESC',
            conn,
        )
    return df


def get_ridici():
    with get_connection() as conn:
        df = pd.read_sql_query('SELECT id, jmeno, telefon, ridicak_do FROM ridici ORDER BY jmeno ASC', conn)
    df = df.fillna('Neuveden')
    return df


def pridat_ridice(jmeno, telefon, ridicak_do):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO ridici (jmeno, telefon, ridicak_do) VALUES (?, ?, ?)",
            (jmeno, telefon, str(ridicak_do)),
        )
        conn.commit()


def smazat_ridice(ridic_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM ridici WHERE id = ?', (ridic_id,))
        conn.commit()


def pridat_zavadu(spz, ridic, popis):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO zavady (spz, ridic, popis, stav) VALUES (?, ?, ?, 'Nahlášeno')",
            (spz, ridic, popis),
        )
        conn.commit()


def smazat_zavadu(zavada_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM zavady WHERE id = ?', (zavada_id,))
        conn.commit()


def pridat_zaznam_paliva(spz, ridic, km, zdroj, mnozstvi, cena, p_od=0, p_do=100, teplota=0):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
                INSERT INTO zaznamy (spz, ridic, datum, km, zdroj, mnozstvi, cena, procenta_od, procenta_do, teplota)
                VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?)
            """,
            (spz, ridic, km, zdroj, mnozstvi, cena, p_od, p_do, teplota),
        )
        conn.commit()


def smazat_zaznam_paliva(zaznam_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM zaznamy WHERE id = ?', (zaznam_id,))
        conn.commit()


def smazat_servisni_zaznam(servis_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM servis WHERE id = ?', (servis_id,))
        conn.commit()


def pridat_auto(
    spz, nazev, typ_pohonu, stk_do, dz_do, pojisteni_do, pneu_rozmer, staly_ridic, vin
):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
                INSERT INTO auta (spz, nazev, typ_pohonu, stk_do, dz_do, pojisteni_do, pneu_rozmer, staly_ridic, vin, olej_interval)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 10000)
            """,
            (
                spz,
                nazev,
                typ_pohonu,
                str(stk_do),
                str(dz_do),
                str(pojisteni_do),
                pneu_rozmer,
                staly_ridic,
                vin,
            ),
        )
        conn.commit()


def upravit_auto(
    spz, nazev, typ_pohonu, stk_do, dz_do, pojisteni_do, pneu_rozmer, staly_ridic, vin
):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
                UPDATE auta 
                SET nazev = ?, typ_pohonu = ?, stk_do = ?, dz_do = ?, pojisteni_do = ?, pneu_rozmer = ?, staly_ridic = ?, vin = ?, olej_interval = 10000
                WHERE spz = ?
            """,
            (
                nazev,
                typ_pohonu,
                str(stk_do),
                str(dz_do),
                str(pojisteni_do),
                pneu_rozmer,
                staly_ridic,
                vin,
                spz,
            ),
        )
        conn.commit()


def smazat_auto(spz):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM auta WHERE spz = ?', (spz,))
        conn.commit()


def pridat_servisni_zaznam(spz, km, kategorie, popis, cena, ridic):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
                INSERT INTO servis (spz, km, kategorie, popis, cena, ridic)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
            (spz, km, kategorie, popis, cena, ridic),
        )
        conn.commit()


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


def ziskej_upozorneni():
    with get_connection() as conn:
        auta_df = pd.read_sql_query("SELECT spz, nazev, stk_do, dz_do, pojisteni_do, typ_pohonu FROM auta", conn)
        try:
            ridici_df = pd.read_sql_query("SELECT jmeno, ridicak_do FROM ridici", conn)
        except Exception:
            ridici_df = pd.DataFrame(columns=['jmeno', 'ridicak_do'])
    
    upozorneni_stk = []
    upozorneni_dz = []
    upozorneni_poj = []
    upozorneni_olej = []
    upozorneni_ridicaky = []
    
    dnes = datetime.now().date()
    
    for _, auto in auta_df.iterrows():
        spz = auto['spz']
        
        try:
            stk_date = datetime.strptime(auto['stk_do'], '%Y-%m-%d').date()
            dny_stk = (stk_date - dnes).days
            if dny_stk < 0:
                upozorneni_stk.append(f"🚨 **{spz}**: STK propadla ({stk_date.strftime('%d.%m.%Y')})!")
            elif dny_stk <= 30:
                upozorneni_stk.append(f"⚠️ **{spz}**: STK končí za {dny_stk} dní ({stk_date.strftime('%d.%m.%Y')}).")
        except Exception:
            pass
            
        try:
            dz_date = datetime.strptime(auto['dz_do'], '%Y-%m-%d').date()
            dny_dz = (dz_date - dnes).days
            if dny_dz < 0:
                upozorneni_dz.append(f"🚨 **{spz}**: Dálniční známka propadla ({dz_date.strftime('%d.%m.%Y')})!")
            elif dny_dz <= 30:
                upozorneni_dz.append(f"⚠️ **{spz}**: DZ končí za {dny_dz} dní ({dz_date.strftime('%d.%m.%Y')}).")
        except Exception:
            pass

        try:
            poj_date = datetime.strptime(auto['pojisteni_do'], '%Y-%m-%d').date()
            dny_poj = (poj_date - dnes).days
            if dny_poj < 0:
                upozorneni_poj.append(f"🚨 **{spz}**: Pojištění propadlo ({poj_date.strftime('%d.%m.%Y')})!")
            elif dny_poj <= 30:
                upozorneni_poj.append(f"⚠️ **{spz}**: Pojištění končí za {dny_poj} dní ({poj_date.strftime('%d.%m.%Y')}).")
        except Exception:
            pass
            
        pohon_raw = str(auto['typ_pohonu']).upper()
        if not any(x in pohon_raw for x in ['ELEKTŘINA', 'ELEKTRE', 'EV', 'BAT']):
            with get_connection() as conn_temp:
                max_km_query = """
                    SELECT MAX(km) as max_km FROM (
                        SELECT km FROM zaznamy WHERE spz=?
                        UNION ALL
                        SELECT km FROM servis WHERE spz=?
                    ) t
                """
                max_km_val = pd.read_sql_query(max_km_query, conn_temp, params=(spz, spz)).iloc[0]['max_km']
                aktualni_km = int(max_km_val) if pd.notna(max_km_val) and max_km_val is not None else 0
                
                posledni_olej_query = "SELECT MAX(km) as max_km FROM servis WHERE spz=? AND kategorie='Výměna oleje'"
                olej_km_val = pd.read_sql_query(posledni_olej_query, conn_temp, params=(spz,)).iloc[0]['max_km']
                posledni_olej_km = int(olej_km_val) if pd.notna(olej_km_val) and olej_km_val is not None else None
            
            if posledni_olej_km is not None:
                zbyva_km = (posledni_olej_km + 10000) - aktualni_km
                if zbyva_km < 0:
                    upozorneni_olej.append(f"🚨 **{spz}**: Přejeta výměna o {abs(zbyva_km)} km!")
                elif zbyva_km <= 1000:
                    upozorneni_olej.append(f"🛢️ **{spz}**: Zbývá {zbyva_km} km do výměny.")
            else:
                upozorneni_olej.append(f"ℹ️ **{spz}**: Chybí záznam výměny v Servisu (nebo stav tachometru).")

    for _, r_row in ridici_df.iterrows():
        r_jmeno = r_row['jmeno']
        r_do_str = str(r_row['ridicak_do'])
        try:
            r_date = datetime.strptime(r_do_str, '%Y-%m-%d').date()
            dny_r = (r_date - dnes).days
            if dny_r < 0:
                upozorneni_ridicaky.append(f"🚨 **{r_jmeno}**: Řidičský průkaz propadl ({r_date.strftime('%d.%m.%Y')})!")
            elif dny_r <= 30:
                upozorneni_ridicaky.append(f"⚠️ **{r_jmeno}**: Řidičský průkaz končí za {dny_r} dní ({r_date.strftime('%d.%m.%Y')}).")
        except Exception:
            pass

    return upozorneni_stk, upozorneni_dz, upozorneni_poj, upozorneni_olej, upozorneni_ridicaky


init_db()

st.set_page_config(
    page_title='Správa flotily - RHJ Gastro [v4.1.3]', page_icon='🚀', layout='wide'
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

CLEAN_CSS = """
<style>
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: #f4f4f7 !important; 
        color: #1e1b29 !important;
        font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
    }
    p, label, .stMarkdown, .stText {
        color: #332d42 !important;
        font-size: 15px !important;
    }
    h1 { font-size: 34px !important; color: #1e1b29 !important; font-weight: 800 !important; }
    h2 { font-size: 24px !important; color: #1e1b29 !important; font-weight: 700 !important; }
    h3 { font-size: 20px !important; color: #1e1b29 !important; font-weight: 600 !important; }

    input, textarea, select, div[data-baseweb="select"] > div {
        background-color: #ffffff !important;
        color: #1e1b29 !important;
        border: 1px solid #d1cce3 !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
    }

    [data-testid="stCode"], pre, code {
        background-color: #ffffff !important;
        color: #1e1b29 !important;
        border: 1px solid #d1cce3 !important;
        border-radius: 8px !important;
    }
    [data-testid="stCode"] span, pre span, code span {
        color: #1e1b29 !important;
    }

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
    div.nav-tile-btn button * {
        color: #ffffff !important;
        font-weight: 700 !important;
    }
    div.nav-tile-btn button:hover {
        background: linear-gradient(135deg, #6b599c 0%, #5b4b8a) !important;
        box-shadow: 0 6px 16px rgba(91, 75, 138, 0.4) !important;
        transform: translateY(-2px);
    }
    div.nav-tile-btn button:hover * {
        color: #ffffff !important;
    }

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
    div.nav-tile-btn-active button * {
        color: #ffffff !important;
        font-weight: 800 !important;
    }

    div.delete-tile-btn button, div.stButton > button, [data-testid="stFormSubmitButton"] > button, [data-testid="stDownloadButton"] > button {
        background: linear-gradient(135deg, #5b4b8a 0%, #48396b) !important;
        color: #ffffff !important;
        border: 1px solid #6b599c !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
        font-size: 15px !important;
        padding: 10px 16px !important;
        box-shadow: 0 4px 12px rgba(91, 75, 138, 0.25) !important;
        width: 100% !important;
        transition: all 0.2s ease !important;
    }
    div.delete-tile-btn button *, div.stButton > button *, [data-testid="stFormSubmitButton"] > button *, [data-testid="stDownloadButton"] > button * {
        color: #ffffff !important;
        fill: #ffffff !important;
    }
    div.delete-tile-btn button:hover, div.stButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover, [data-testid="stDownloadButton"] > button:hover {
        background: linear-gradient(135deg, #6b599c 0%, #5b4b8a) !important;
        box-shadow: 0 6px 16px rgba(91, 75, 138, 0.4) !important;
        transform: translateY(-2px);
    }
    div.delete-tile-btn button:hover *, div.stButton > button:hover *, [data-testid="stFormSubmitButton"] > button:hover *, [data-testid="stDownloadButton"] > button:hover * {
        color: #ffffff !important;
        fill: #ffffff !important;
    }

    div.stButton > button[kind="primary"] {
        background-color: #0f9d58 !important;
        background: #0f9d58 !important;
        color: white !important;
        border: none !important;
    }
    div.stButton > button[kind="primary"] * {
        color: white !important;
    }

    .car-card-blue {
        background: linear-gradient(145deg, #ffffff, #f0f6ff) !important;
        border-top: 6px solid #2563eb !important;
        border-radius: 16px !important;
        padding: 24px !important;
        box-shadow: 0 10px 25px -5px rgba(37, 99, 235, 0.15) !important;
        border-left: 1px solid #dbeafe !important;
        border-right: 1px solid #dbeafe !important;
        border-bottom: 1px solid #dbeafe !important;
        margin-bottom: 15px !important;
    }
    .car-card-orange {
        background: linear-gradient(145deg, #ffffff, #fffbeb) !important;
        border-top: 6px solid #ea580c !important;
        border-radius: 16px !important;
        padding: 24px !important;
        box-shadow: 0 10px 25px -5px rgba(234, 88, 12, 0.15) !important;
        border-left: 1px solid #ffedd5 !important;
        border-right: 1px solid #ffedd5 !important;
        border-bottom: 1px solid #ffedd5 !important;
        margin-bottom: 15px !important;
    }
    .car-card-green {
        background: linear-gradient(145deg, #ffffff, #f0fdf4) !important;
        border-top: 6px solid #16a34a !important;
        border-radius: 16px !important;
        padding: 24px !important;
        box-shadow: 0 10px 25px -5px rgba(22, 163, 74, 0.15) !important;
        border-left: 1px solid #dcfce7 !important;
        border-right: 1px solid #dcfce7 !important;
        border-bottom: 1px solid #dcfce7 !important;
        margin-bottom: 15px !important;
    }

    .alert-badge {
        background-color: #fee2e2;
        border: 1px solid #fecaca;
        color: #991b1b;
        padding: 8px 12px;
        border-radius: 8px;
        font-weight: 700;
        margin-top: 10px;
        font-size: 13px;
        display: flex;
        align-items: center;
        gap: 6px;
    }

    .warning-badge {
        background-color: #fef3c7;
        border: 1px solid #fde68a;
        color: #92400e;
        padding: 8px 12px;
        border-radius: 8px;
        font-weight: 700;
        margin-top: 8px;
        font-size: 13px;
    }

    .styled-table {
        border-collapse: collapse;
        margin: 15px 0;
        font-size: 14px;
        width: 100%;
        background-color: #ffffff;
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 4px 12px rgba(0,0,0,0.04);
        border: 1px solid #e2e8f0;
    }
    .styled-table th {
        background-color: #f1ecfa !important;
        color: #1e1b29 !important;
        text-align: left;
        padding: 12px 16px;
        font-weight: 700;
        border-bottom: 1px solid #d1cce3;
    }
    .styled-table td {
        padding: 12px 16px;
        color: #332d42 !important;
        border-bottom: 1px solid #f1f5f9;
    }
    .alert-box {
        background-color: white;
        border-radius: 10px;
        padding: 15px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        height: 100%;
    }
    
    .oil-scroll-container {
        max-height: 250px !important;
        overflow-y: auto !important;
        overflow-x: hidden !important;
        padding-right: 6px;
        margin-top: 8px;
    }
    
    [data-testid="stMetricValue"] {
        font-weight: 800 !important;
        color: #5b4b8a !important;
    }
</style>
"""
st.markdown(CLEAN_CSS, unsafe_allow_html=True)

params = st.query_params
qr_ridic = params.get("ridic", "Neznámý řidič")
qr_spz = params.get("spz", "Neznámá SPZ")

if st.session_state['simulovat_ridice']:
    df_auta_sim = get_vsechna_auta()
    if not df_auta_sim.empty:
        prvni_auto = df_auta_sim.iloc[0]
        qr_ridic = prvni_auto['staly_ridic'] if prvni_auto['staly_ridic'] != 'Neuveden' else 'Testovací řidič'
        qr_spz = prvni_auto['spz']
    else:
        qr_ridic = 'Testovací řidič'
        qr_spz = '5Z49372'

def zisti_zda_je_ev(spz):
    if not spz:
        return False
    with get_connection() as conn:
        res = pd.read_sql_query("SELECT typ_pohonu FROM auta WHERE spz = ?", conn, params=(spz,))
    if res.empty:
        return False
    pohon = str(res.iloc[0]['typ_pohonu']).upper()
    return any(x in pohon for x in ['EV', 'ELEKTŘINA', 'ELEKTRE', 'BAT'])

if qr_ridic != "Neznámý řidič" or qr_spz != "Neznámá SPZ" or st.session_state.get('simulovat_ridice', False):
    st.markdown(
        """
        <div style="background-color: #eae5f5; padding: 20px; border-radius: 14px; margin-bottom: 20px; text-align: center; border: 1px solid #d1cce3;">
            <h2 style="color: #5b4b8a !important; margin: 0;">RHJ Gastro – Mobilní portál řidiče</h2>
            <p style="margin: 4px 0 0 0; font-weight: 600;">Rychlé hlášení závad a zápis tankování / nabíjení z terénu</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    if st.session_state['admin_autentizovan'] or st.session_state['simulovat_ridice']:
        if st.button("⬅️ Zpět do administrace flotily"):
            st.session_state['simulovat_ridice'] = False
            st.query_params.clear()
            st.rerun()

    aktivni_ridic = qr_ridic
    skutecna_spz = qr_spz
    is_ev_car = zisti_zda_je_ev(skutecna_spz)

    st.markdown(
        f"""
        <div style="background: white; padding: 15px 20px; border-radius: 12px; border: 1px solid #d1cce3; margin-bottom: 20px; display: flex; justify-content: space-around; text-align: center;">
            <div>
                <span style="font-size: 13px; color: #666; display: block;">Přihlášený řidič:</span>
                <strong style="font-size: 17px; color: #5b4b8a;">{aktivni_ridic}</strong>
            </div>
            <div style="border-left: 1px solid #e2e8f0; padding-left: 20px;">
                <span style="font-size: 13px; color: #666; display: block;">Přiřazené vozidlo (SPZ):</span>
                <strong style="font-size: 17px; color: #2563eb; font-family: monospace;">{skutecna_spz}</strong> {'(Elektromobil)' if is_ev_car else ''}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    driver_tab1, driver_tab2 = st.tabs(["⚡ Zapsat tankování / Nabíjení EV", "⚠️ Nahlásit závadu"])
    
    with driver_tab1:
        if is_ev_car:
            st.subheader("⚡ Zapsat nabíjení elektromobilu")
        else:
            st.subheader("⛽ Zapsat tankování paliva (Čerpací stanice)")

        with st.form("driver_tank_form"):
            d_km = st.number_input("Aktuální stav tachometru (km)", min_value=0, step=100)
            
            if is_ev_car:
                d_zdroj = st.selectbox("Zdroj nabíjení", ["Wallbox", "Zasuvka 220"])
                st.markdown("#### 🔋 Počáteční stav baterie a kWh")
                d_p_od = st.slider("Počáteční stav baterie (%)", min_value=0, max_value=100, value=20, step=1)
                d_p_do = 100
                
                total_battery_capacity = 50.0
                missing_percentage = 100 - d_p_od
                d_mnozstvi = round((missing_percentage / 100.0) * total_battery_capacity, 2)
                d_teplota = 0.0
                
                with get_connection() as conn_c:
                    cur_c = conn_c.cursor()
                    cur_c.execute("SELECT hodnota FROM nastaveni WHERE klic = 'cena_kwh'")
                    row_c = cur_c.fetchone()
                cena_kwh_val = float(row_c[0]) if row_c else 6.50
                
                d_cena = round(d_mnozstvi * cena_kwh_val, 2)
            else:
                d_zdroj = "Čerpací stanice"
                d_mnozstvi = st.number_input("Množství (litry)", min_value=0.0, step=1.0)
                d_cena = st.number_input("Celková cena (Kč)", min_value=0.0, step=10.0)
                d_p_od, d_p_do, d_teplota = 0.0, 100.0, 0.0
            
            d_submit_tank = st.form_submit_button("Uložit záznam")
            
            if d_submit_tank:
                if skutecna_spz:
                    pridat_zaznam_paliva(skutecna_spz, aktivni_ridic, d_km, d_zdroj, d_mnozstvi, d_cena, d_p_od, d_p_do, d_teplota)
                    st.success("Záznam byl úspěšně uložen!")
                else:
                    st.error("Chybí identifikace vozidla.")

    with driver_tab2:
        st.subheader("Nahlásit novou závadu na vozidle")
        with st.form("driver_zavada_form"):
            d_popis_zavady = st.text_area("Popis závady / problémů:")
            d_submit_zavada = st.form_submit_button("Odeslat hlášení závady")
            
            if d_submit_zavada:
                if d_popis_zavady and skutecna_spz:
                    pridat_zavadu(skutecna_spz, aktivni_ridic, d_popis_zavady)
                    st.success("Závada byla úspěšně odeslána do centrální správy!")
                else:
                    st.error("Vyplňte prosím popis závady.")
                    
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
            zadany_hash = hash_password(zadane_heslo)
            aktualni_admin_hash = ziskej_admin_heslo_hash()
            
            if zadany_hash == aktualni_admin_hash:
                st.session_state['admin_autentizovan'] = True
                st.session_state['supervizor_autentizovan'] = False
                st.success("Přístup povolen (Admin)!")
                st.rerun()
            elif zadany_hash == SUPERVISOR_PASSWORD_HASH:
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
                <p style="color: #3d3156 !important; margin: 4px 0 0 0; font-size: 15px !important; font-weight: 600;">Rozvoz hotových jídel — Fleet Management & Operations System (v4.1.3)</p>
                <p style="color: #666 !important; margin: 4px 0 0 0; font-size: 12px !important;">&copy; 2026 RHJ Gastro. All rights reserved. Všechna práva vyhrazena.</p>
            </div>
        </div>
        <div style="text-align: right; display: flex; gap: 10px; align-items: center;">
    """,
    unsafe_allow_html=True,
)

if st.session_state['supervizor_autentizovan']:
    st.markdown('<span style="background: #7c3aed; color: white; padding: 6px 12px; border-radius: 8px; font-size: 12px; font-weight: 700;">★ MASTER SUPERVIZOR</span>', unsafe_allow_html=True)

if st.button("📱 Přepnout na rozhraní řidiče", type="primary"):
    st.session_state['simulovat_ridice'] = True
    st.rerun()

if st.button("🚪 Odhlásit admin"):
    st.session_state['admin_autentizovan'] = False
    st.session_state['supervizor_autentizovan'] = False
    st.rerun()

st.markdown("</div></div>", unsafe_allow_html=True)

st.markdown('### 🎛️ Hlavní menu')
nav_col1, nav_col2, nav_col3, nav_col4, nav_col5, nav_col6, nav_col7, nav_col8 = st.columns(8)

tabs_list = [
    ('🏢 Vozidla', nav_col1),
    ('⚙️ Nastavení', nav_col2),
    ('⛽ Tankování', nav_col3),
    ('🛠️ Servis', nav_col4),
    ('👥 Řidiči', nav_col5),
    ('📊 Statistiky', nav_col6),
    ('📱 QR Kód', nav_col7),
    ('⚠️ Závady', nav_col8),
]

for title, col in tabs_list:
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
upoz_stk, upoz_dz, upoz_poj, upoz_olej, upoz_ridicaky = ziskej_upozorneni()

if akt_sekce == '🏢 Vozidla':
    if st.session_state['car_action'] == 'add':
        st.header('➕ Přidat nové vozidlo')
        if st.button('🔙 Zpět na přehled vozidel'):
            st.session_state['car_action'] = 'view'
            st.rerun()

        with st.form('add_car_form'):
            c1, c2 = st.columns(2)
            with c1:
                new_spz = st.text_input('SPZ (např. 1A2 3456 nebo 5Z49372)')
                new_nazev = st.text_input('Model (např. Maxus eDeliver 3, VW Caddy EV...)')
                new_vin = st.text_input('VIN')
                new_stk = st.text_input('STK do (YYYY-MM-DD)', value='2027-01-01')
                new_dz = st.text_input('DZ do (YYYY-MM-DD)', value='2027-01-01')
            with c2:
                new_pohonu = st.selectbox('Pohon', ['EV', 'Diesel', 'firemní', 'LPG', 'Natural'])
                new_pojisteni = st.text_input('Pojištění do (YYYY-MM-DD)', value='2027-01-01')
                new_pneu = st.text_input('Pneu rozměr', value='215/70 R15C')
                new_ridic = st.text_input('Stálý řidič')

            if st.form_submit_button('Uložit vozidlo'):
                cleaned_spz = new_spz.replace(" ", "").upper()
                if cleaned_spz:
                    df_check = get_vsechna_auta()
                    if not df_check[df_check['spz'] == cleaned_spz].empty:
                        st.error(f"Vozidlo se SPZ {cleaned_spz} již v databázi existuje!")
                    else:
                        pridat_auto(
                            cleaned_spz,
                            new_nazev,
                            new_pohonu,
                            new_stk,
                            new_dz,
                            new_pojisteni,
                            new_pneu,
                            new_ridic,
                            new_vin,
                        )
                        st.success('Vozidlo úspěšně přidáno do databáze!')
                        st.session_state['car_action'] = 'view'
                        st.rerun()
                else:
                    st.error('Zadejte prosím SPZ vozidla.')

    elif st.session_state['car_action'] == 'edit' and st.session_state['editing_spz']:
        spz_to_edit = st.session_state['editing_spz']
        st.header(f'✏️ Upravit / spravovat vozidlo: {spz_to_edit}')
        if st.button('🔙 Zpět na přehled vozidel'):
            st.session_state['car_action'] = 'view'
            st.session_state['editing_spz'] = None
            st.rerun()

        df_auta = get_vsechna_auta()
        car_row = df_auta[df_auta['spz'] == spz_to_edit]

        if not car_row.empty:
            row = car_row.iloc[0]
            
            with get_connection() as conn_sum:
                df_s_servis = pd.read_sql_query("SELECT cena FROM servis WHERE spz=?", conn_sum, params=(spz_to_edit,))
                df_s_tank = pd.read_sql_query("SELECT cena FROM zaznamy WHERE spz=?", conn_sum, params=(spz_to_edit,))
            
            celkem_servis = df_s_servis['cena'].sum() if not df_s_servis.empty else 0.0
            celkem_palivo = df_s_tank['cena'].sum() if not df_s_tank.empty else 0.0
            celkem_naklady = celkem_servis + celkem_palivo
            
            st.markdown(
                f"""
                <div style="background: #eef2ff; border: 1px solid #c7d2fe; padding: 16px; border-radius: 12px; margin-bottom: 20px; display: flex; justify-content: space-around; text-align: center;">
                    <div>
                        <span style="font-size: 13px; color: #4338ca; display: block;">Celkem náklady na servis:</span>
                        <strong style="font-size: 18px; color: #312e81;">{celkem_servis:,.2f} Kč</strong>
                    </div>
                    <div style="border-left: 1px solid #c7d2fe; padding-left: 15px;">
                        <span style="font-size: 13px; color: #4338ca; display: block;">Celkem náklady na palivo/energie:</span>
                        <strong style="font-size: 18px; color: #312e81;">{celkem_palivo:,.2f} Kč</strong>
                    </div>
                    <div style="border-left: 1px solid #c7d2fe; padding-left: 15px;">
                        <span style="font-size: 13px; color: #4338ca; display: block;">Celkové výdaje celkem:</span>
                        <strong style="font-size: 18px; color: #1e1b4b;">{celkem_naklady:,.2f} Kč</strong>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            with st.form(f'edit_car_form_{spz_to_edit}'):
                e_nazev = st.text_input('Model', value=row['nazev'])
                e_vin = st.text_input('VIN', value=row['vin'])
                pohony_opts = ['EV', 'Diesel', 'firemní', 'LPG', 'Natural']
                pohon_idx = (
                    pohony_opts.index(row['typ_pohonu'])
                    if row['typ_pohonu'] in pohony_opts
                    else 0
                )
                e_pohon = st.selectbox('Pohon', pohony_opts, index=pohon_idx)
                e_stk = st.text_input('STK do', value=row['stk_do'])
                e_dz = st.text_input('DZ do', value=row['dz_do'])
                e_pojisteni = st.text_input('Pojištění do', value=row.get('pojisteni_do', '2027-01-01'))
                e_pneu = st.text_input('Pneu rozměr', value=row['pneu_rozmer'])
                e_ridic = st.text_input('Stálý řidič', value=row['staly_ridic'])

                st.markdown('---')
                povolit_smazani = st.checkbox('⚠️ Povolit smazání vozidla')

                sub_col1, sub_col2 = st.columns(2)
                with sub_col1:
                    ulozeno = st.form_submit_button('Uložit změny')
                with sub_col2:
                    smazano = st.form_submit_button('🗑️ Smazat toto vozidlo')

                if ulozeno:
                    upravit_auto(
                        spz_to_edit,
                        e_nazev,
                        e_pohon,
                        e_stk,
                        e_dz,
                        e_pojisteni,
                        e_pneu,
                        e_ridic,
                        e_vin,
                    )
                    st.success('Vozidlo aktualizováno v databázi!')
                    st.session_state['car_action'] = 'view'
                    st.session_state['editing_spz'] = None
                    st.rerun()

                if smazano:
                    if povolit_smazani:
                        smazat_auto(spz_to_edit)
                        st.success(f'Vozidlo {spz_to_edit} bylo úspěšně smazáno.')
                        st.session_state['car_action'] = 'view'
                        st.session_state['editing_spz'] = None
                        st.rerun()
                    else:
                        st.error('Pro smazání vozidla musíte zaškrtnout políčko "Povolit smazání vozidla".')
            
            st.markdown("---")
            st.markdown(f"### 📋 Kompletní historie pro: {spz_to_edit}")
            
            with get_connection() as conn_hist:
                df_h_servis = pd.read_sql_query("SELECT id, datum, km, kategorie, popis, cena, ridic FROM servis WHERE spz=? ORDER BY datum DESC", conn_hist, params=(spz_to_edit,))
                df_h_tank = pd.read_sql_query("SELECT id, datum, km, zdroj, mnozstvi, cena, procenta_od, procenta_do, teplota, ridic FROM zaznamy WHERE spz=? ORDER BY datum DESC", conn_hist, params=(spz_to_edit,))
                df_h_zavady = pd.read_sql_query("SELECT id, datum, popis, stav FROM zavady WHERE spz=? ORDER BY datum DESC", conn_hist, params=(spz_to_edit,))

            t_s1, t_s2, t_s3 = st.tabs(["🛠️ Servisní úkony", "⛽ Tankování / Nabíjení", "⚠️ Hlášené závady"])
            
            with t_s1:
                if not df_h_servis.empty:
                    render_styled_table(df_h_servis)
                    if st.session_state.get('supervizor_autentizovan', False):
                        st.markdown("##### ★ Supervizor zásah: Smazat chybný servisní záznam")
                        sup_serv_id = st.selectbox("ID servisu k opravě/smazání", df_h_servis['id'].tolist(), key=f"sup_serv_{spz_to_edit}")
                        if st.button("🗑️ [Supervizor] Odstranit servisní záznam", key=f"btn_sup_serv_{spz_to_edit}"):
                            smazat_servisni_zaznam(sup_serv_id)
                            st.success("Záznam byl supervizorem odstraněn.")
                            st.rerun()
                else:
                    st.info("Žádné servisní záznamy.")
                    
            with t_s2:
                if not df_h_tank.empty:
                    render_styled_table(df_h_tank)
                    if st.session_state.get('supervizor_autentizovan', False):
                        st.markdown("##### ★ Supervizor zásah: Smazat chybný záznam paliva")
                        sup_tank_id = st.selectbox("ID záznamu paliva k smazání", df_h_tank['id'].tolist(), key=f"sup_tank_{spz_to_edit}")
                        if st.button("🗑️ [Supervizor] Odstranit záznam paliva", key=f"btn_sup_tank_{spz_to_edit}"):
                            smazat_zaznam_paliva(sup_tank_id)
                            st.success("Záznam o palivu byl supervizorem odstraněn.")
                            st.rerun()
                else:
                    st.info("Žádné záznamy o tankování.")
                    
            with t_s3:
                if not df_h_zavady.empty:
                    render_styled_table(df_h_zavady)
                    if st.session_state.get('supervizor_autentizovan', False):
                        st.markdown("##### ★ Supervizor zásah: Uzavřít/smazat závadu")
                        sup_zav_id = st.selectbox("ID závady k odstranění", df_h_zavady['id'].tolist(), key=f"sup_zav_{spz_to_edit}")
                        if st.button("🗑️ [Supervizor] Odstranit závadu", key=f"btn_sup_zav_{spz_to_edit}"):
                            smazat_zavadu(sup_zav_id)
                            st.success("Závada byla supervizorem odstraněna.")
                            st.rerun()
                else:
                    st.info("Žádné hlášené závady.")
        else:
            st.error('Vozidlo nebylo nalezeno.')

    else:
        st.header('🏢 Dashboard vozidel')
        if st.button('➕ Přidat nové vozidlo'):
            st.session_state['car_action'] = 'add'
            st.rerun()

        st.markdown('')
        df_auta = get_vsechna_auta()

        if not df_auta.empty:
            with get_connection() as conn_z:
                df_vsechny_zavady = pd.read_sql_query("SELECT spz, popis FROM zavady", conn_z)

            dnes = datetime.now().date()
            cols = st.columns(2)
            
            for idx, row in df_auta.iterrows():
                pohon_val = str(row['typ_pohonu']).upper()
                spz_karta = row['spz']
                
                if 'LPG' in pohon_val:
                    card_class = 'car-card-orange'
                elif any(x in pohon_val for x in ['EV', 'ELEKTŘINA', 'ELEKTRE', 'BAT']):
                    card_class = 'car-card-green'
                else:
                    card_class = 'car-card-blue'

                olej_radek = f"<p style='margin: 4px 0;'><b>Interval výměny oleje:</b> 10 000 km</p>"

                varovani_html = ""
                try:
                    stk_d = datetime.strptime(str(row['stk_do']), '%Y-%m-%d').date()
                    dny_s = (stk_d - dnes).days
                    if dny_s <= 30:
                        varovani_html += f"<div class='warning-badge'>⚠️ STK končí za {dny_s} dní ({row['stk_do']})</div>" if dny_s >= 0 else f"<div class='alert-badge'>🚨 STK propadla!</div>"
                except Exception:
                    pass

                try:
                    dz_d = datetime.strptime(str(row['dz_do']), '%Y-%m-%d').date()
                    dny_d = (dz_d - dnes).days
                    if dny_d <= 30:
                        varovani_html += f"<div class='warning-badge'>⚠️ Dálniční známka končí za {dny_d} dní ({row['dz_do']})</div>" if dny_d >= 0 else f"<div class='alert-badge'>🚨 Dálniční známka propadla!</div>"
                except Exception:
                    pass

                try:
                    poj_d_str = row.get('pojisteni_do', 'Neuveden')
                    if poj_d_str != 'Neuveden':
                        poj_d = datetime.strptime(str(poj_d_str), '%Y-%m-%d').date()
                        dny_p = (poj_d - dnes).days
                        if dny_p <= 30:
                            varovani_html += f"<div class='warning-badge'>⚠️ Pojištění končí za {dny_p} dní ({poj_d_str})</div>" if dny_p >= 0 else f"<div class='alert-badge'>🚨 Pojištění propadlo!</div>"
                except Exception:
                    pass

                aktivni_zavady_auta = df_vsechny_zavady[df_vsechny_zavady['spz'] == spz_karta]
                zavada_banner = ""
                if not aktivni_zavady_auta.empty:
                    zavada_banner = f'<div class="alert-badge">⚠️ Pozor: Aktivní hlášená závada ({len(aktivni_zavady_auta)}x)</div>'

                with cols[idx % 2]:
                    st.markdown(
                        f"""
                            <div class="{card_class}">
                                <h3 style="margin: 0; color: #1e1b29;">🚗 {row['nazev']}</h3>
                                <p style="margin: 4px 0;"><b>SPZ:</b> <span style="font-family: monospace; font-weight: 700;">{spz_karta}</span></p>
                                <p style="margin: 4px 0;"><b>VIN:</b> <span style="font-family: monospace;">{row['vin']}</span></p>
                                <p style="margin: 4px 0;"><b>Typ pohonu:</b> {row['typ_pohonu']}</p>
                                <p style="margin: 4px 0;"><b>Stálý řidič:</b> {row['staly_ridic']}</p>
                                <p style="margin: 4px 0;"><b>STK do:</b> {row['stk_do']} | <b>DZ do:</b> {row['dz_do']}</p>
                                <p style="margin: 4px 0;"><b>Pojištění do:</b> {row.get('pojisteni_do', 'Neuvedeno')}</p>
                                <p style="margin: 4px 0;"><b>Pneu:</b> {row['pneu_rozmer']}</p>
                                {olej_radek}
                                {varovani_html}
                                {zavada_banner}
                            </div>
                            """,
                        unsafe_allow_html=True,
                    )

                    if st.button("✏️ Upravit / Správa & Historie", key=f"edit_btn_{spz_karta}_{idx}"):
                        st.session_state['car_action'] = 'edit'
                        st.session_state['editing_spz'] = spz_karta
                        st.rerun()

                    st.markdown("<br>", unsafe_allow_html=True)
        else:
            st.info('V databázi nejsou žádná vozidla.')

elif akt_sekce == '⚙️ Nastavení':
    st.header('⚙️ Nastavení aplikace & Notifikace')
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT hodnota FROM nastaveni WHERE klic = 'cena_kwh'")
        cena_kwh = cursor.fetchone()[0]

    with st.form('nastaveni_form'):
        nova_cena = st.number_input('Cena elektřiny za kWh (Kč)', value=float(cena_kwh), format='%.2f')
        
        st.markdown("---")
        st.markdown("### 🔑 Změna administrátorského hesla (pro šéfovou)")
        staré_heslo = st.text_input("Původní administrátorské heslo", type="password")
        nove_admin_heslo = st.text_input("Nové administrátorské heslo", type="password")
        potvrzeni_hesla = st.text_input("Potvrzení nového administrátorského hesla", type="password")
        
        st.markdown("---")
        st.markdown("### 🔔 Notifikační kanály (WhatsApp & Gmail)")
        notif_whatsapp = st.text_input("WhatsApp telefonní číslo (pro okamžitá upozornění na STK/olej)", value="+420")
        notif_gmail = st.text_input("Gmail / E-mail pro zasílání měsíčních reportů a varování", value="sefova@rhjgastro.cz")
        
        if st.form_submit_button('Uložit nastavení'):
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE nastaveni SET hodnota = ? WHERE klic = ?', (str(nova_cena), 'cena_kwh'))
                
                if nove_admin_heslo:
                    if nove_admin_heslo != potvrzeni_hesla:
                        st.error("Nové heslo a potvrzení se neshodují!")
                    else:
                        starý_hash = hash_password(staré_heslo)
                        aktualni_hash = ziskej_admin_heslo_hash()
                        if starý_hash == aktualni_hash or st.session_state.get('supervizor_autentizovan', False):
                            novy_hash = hash_password(nove_admin_heslo)
                            cursor.execute('INSERT OR REPLACE INTO nastaveni (klic, hodnota) VALUES (?, ?)', ('admin_heslo_hash', novy_hash))
                            conn.commit()
                            st.success('Nastavení a administrátorské heslo úspěšně aktualizovány!')
                        else:
                            st.error("Původní administrátorské heslo je nesprávné!")
                else:
                    conn.commit()
                    st.success('Nastavení a notifikační kanály úspěšně uloženy!')

elif akt_sekce == '⛽ Tankování':
    st.header('⛽ Evidence tankování a nabíjení EV')

    if st.session_state['tank_action'] == 'add':
        if st.button('🔙 Zpět na přehled'):
            st.session_state['tank_action'] = 'view'
            st.rerun()

        with st.form('add_tank_form'):
            df_auta = get_vsechna_auta()
            spz_list = df_auta['spz'].tolist() if not df_auta.empty else []
            t_spz = st.selectbox('Vozidlo (SPZ)', spz_list)
            t_ridic = st.text_input('Řidič')
            t_km = st.number_input('Stav tachometru (km)', min_value=0, step=100)
            
            is_ev_selected = zisti_zda_je_ev(t_spz)
            if is_ev_selected:
                t_zdroj = st.selectbox('Zdroj nabíjení', ['Wallbox', 'Zasuvka 220'])
                st.markdown("#### 🔋 Počáteční stav baterie a kWh")
                t_p_od = st.slider('Počáteční stav baterie (%)', min_value=0, max_value=100, value=20, step=1)
                t_p_do = 100
                
                total_battery_capacity = 50.0
                missing_percentage = 100 - t_p_od
                t_mnozstvi = round((missing_percentage / 100.0) * total_battery_capacity, 2)
                t_teplota = 0.0
                
                with get_connection() as conn_c:
                    cur_c = conn_c.cursor()
                    cur_c.execute("SELECT hodnota FROM nastaveni WHERE klic = 'cena_kwh'")
                    row_c = cur_c.fetchone()
                cena_kwh_val = float(row_c[0]) if row_c else 6.50
                
                t_cena = round(t_mnozstvi * cena_kwh_val, 2)
            else:
                t_zdroj = 'Čerpací stanice'
                t_mnozstvi = st.number_input('Množství (litry)', min_value=0.0, step=1.0)
                t_cena = st.number_input('Celková cena (Kč)', min_value=0.0, step=10.0)
                t_p_od, t_p_do, t_teplota = 0.0, 100.0, 0.0
            
            if st.form_submit_button('Přidat záznam'):
                with get_connection() as conn_v:
                    last_km_res = pd.read_sql_query("SELECT MAX(km) as max_km FROM zaznamy WHERE spz=?", conn_v, params=(t_spz,))
                last_km = last_km_res.iloc[0]['max_km'] if not last_km_res.empty and pd.notna(last_km_res.iloc[0]['max_km']) else 0
                
                if last_km > 0 and t_km < last_km:
                    st.error(f"Pozor: Zadávaný stav tachometru ({t_km} km) je nižší než poslední zaznamenaný stav ({last_km} km)!")
                else:
                    pridat_zaznam_paliva(t_spz, t_ridic, t_km, t_zdroj, t_mnozstvi, t_cena, t_p_od, t_p_do, t_teplota)
                    st.success('Záznam přídán!')
                    st.session_state['tank_action'] = 'view'
                    st.rerun()
    else:
        if st.button('➕ Přidat záznam tankování / nabití'):
            st.session_state['tank_action'] = 'add'
            st.rerun()

        st.markdown('')
        df_tank = get_zaznamy_paliva()
        if not df_tank.empty:
            render_styled_table(df_tank)
            sel_id = st.selectbox('ID záznamu k smazání', df_tank['id'].tolist(), key='del_tank_sel')
            st.markdown('<div class="delete-tile-btn">', unsafe_allow_html=True)
            if st.button('Smazat záznam'):
                smazat_zaznam_paliva(sel_id)
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info('Zatím žádné záznamy.')

elif akt_sekce == '🛠️ Servis':
    st.header('🛠️ Servisní záznamy')

    if st.session_state['servis_action'] == 'add':
        if st.button('🔙 Zpět na přehled servisů'):
            st.session_state['servis_action'] = 'view'
            st.rerun()

        with st.form('add_servis_form'):
            df_auta = get_vsechna_auta()
            spz_list = df_auta['spz'].tolist() if not df_auta.empty else []
            s_spz = st.selectbox('Vozidlo (SPZ)', spz_list, key='s_spz')
            s_ridic = st.text_input('Řidič', key='s_ridic')
            s_km = st.number_input('Tachometr (km)', min_value=0, step=100, key='s_km')
            s_kat = st.selectbox('Kategorie', ['Pravidelná prohlídka', 'Výměna oleje', 'Pneumatiky', 'Oprava', 'STK / Emise', 'Jiné'])
            s_popis = st.text_area('Popis práce / dílů')
            s_cena = st.number_input('Cena celkem (Kč)', min_value=0.0, step=100.0, key='s_cena')
            if st.form_submit_button('Uložit servis'):
                pridat_servisni_zaznam(s_spz, s_km, s_kat, s_popis, s_cena, s_ridic)
                st.success('Servisní záznam uložen!')
                st.session_state['servis_action'] = 'view'
                st.rerun()
    else:
        if st.button('➕ Přidat servisní úkon'):
            st.session_state['servis_action'] = 'add'
            st.rerun()

        st.markdown('')
        df_servis = get_zaznamy_servis()
        if not df_servis.empty:
            render_styled_table(df_servis)
            sel_s_id = st.selectbox('ID servisu k smazání', df_servis['id'].tolist(), key='del_servis_sel')
            st.markdown('<div class="delete-tile-btn">', unsafe_allow_html=True)
            if st.button('Smazat servisní záznam'):
                smazat_servisni_zaznam(sel_s_id)
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info('Žádné servisní záznamy.')

elif akt_sekce == '👥 Řidiči':
    st.header('👥 Evidence řidičů a platnosti řidičských průkazů')
    
    col_r1, col_r2 = st.columns([1, 1])
    with col_r1:
        st.subheader('Přidat / upravit řidiče')
        with st.form('add_ridic_form'):
            r_jmeno = st.text_input('Jméno a příjmení řidiče')
            r_tel = st.text_input('Telefonní číslo', value='+420')
            r_do = st.text_input('Platnost řidičského průkazu do (YYYY-MM-DD)', value='2028-01-01')
            
            if st.form_submit_button('Uložit řidiče'):
                if r_jmeno:
                    pridat_ridice(r_jmeno, r_tel, r_do)
                    st.success(f'Řidič {r_jmeno} byl úspěšně uložen.')
                    st.rerun()
                else:
                    st.error('Zadejte prosím jméno řidiče.')

    with col_r2:
        st.subheader('Seznam evidovaných řidičů')
        df_ridici = get_ridici()
        if not df_ridici.empty:
            render_styled_table(df_ridici)
            sel_r_id = st.selectbox('ID řidiče k odstranění', df_ridici['id'].tolist(), key='del_ridic_sel')
            if st.button('🗑️ Smazat řidiče'):
                smazat_ridice(sel_r_id)
                st.success('Řidič byl smazán.')
                st.rerun()
        else:
            st.info('Zatím nejsou evidováni žádní řidiči.')

elif akt_sekce == '📊 Statistiky':
    st.header('📊 Barevný manažerský dashboard flotily & Reporty')
    st.markdown("Provozní přehled nákladů, výpočet spotřeby a exporty pro vedení.")
    
    df_tank = get_zaznamy_paliva()
    df_servis = get_zaznamy_servis()
    df_auta_exp = get_vsechna_auta()
    df_zavady_exp = get_zavady()

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    celkem_tank_naklady = df_tank['cena'].sum() if not df_tank.empty else 0.0
    celkem_servis_naklady = df_servis['cena'].sum() if not df_servis.empty else 0.0
    celkem_vse = celkem_tank_naklady + celkem_servis_naklady
    
    with kpi1:
        st.metric("💰 Celkové výdaje flotily", f"{celkem_vse:,.2f} Kč")
    with kpi2:
        st.metric("🚗 Aktivní vozidla", f"{len(df_auta_exp)}")
    with kpi3:
        st.metric("⚠️ Otevřené závady", f"{len(df_zavady_exp)}")
    with kpi4:
        st.metric("🛠️ Servisní úkony", f"{len(df_servis)}")

    st.markdown("<br>", unsafe_allow_html=True)
    
    col_stk, col_dz, col_poj, col_olej, col_rid = st.columns(5)
    with col_stk:
        st.markdown('<div class="alert-box"><h4>🔴 Platnost STK</h4>', unsafe_allow_html=True)
        if upoz_stk:
            for u in upoz_stk: st.warning(u)
        else: st.success("Všechna vozidla platná STK.")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_dz:
        st.markdown('<div class="alert-box"><h4>🛣️ Dálniční známky</h4>', unsafe_allow_html=True)
        if upoz_dz:
            for u in upoz_dz: st.warning(u)
        else: st.success("Všechny známky OK.")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_poj:
        st.markdown('<div class="alert-box"><h4>🛡️ Pojištění</h4>', unsafe_allow_html=True)
        if upoz_poj:
            for u in upoz_poj: st.warning(u)
        else: st.success("Pojištění platná.")
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col_olej:
        st.markdown('<div class="alert-box"><h4>🛢️ Výměny oleje</h4><div class="oil-scroll-container">', unsafe_allow_html=True)
        if upoz_olej:
            for u in upoz_olej: st.warning(u)
        else: st.success("Olej OK.")
        st.markdown('</div></div>', unsafe_allow_html=True)

    with col_rid:
        st.markdown('<div class="alert-box"><h4>🪪 Řidičské průkazy</h4><div class="oil-scroll-container">', unsafe_allow_html=True)
        if upoz_ridicaky:
            for u in upoz_ridicaky: st.warning(u)
        else: st.success("Všechny řidičáky OK.")
        st.markdown('</div></div>', unsafe_allow_html=True)
        
    st.markdown("<br><hr><br>", unsafe_allow_html=True)

    st.markdown("### 📥 Exporty dat pro vedení")
    ex_col1, ex_col2 = st.columns(2)

    with ex_col1:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_auta_exp.to_excel(writer, sheet_name='Vozidla', index=False)
            df_tank.to_excel(writer, sheet_name='Tankovani_Energie', index=False)
            df_servis.to_excel(writer, sheet_name='Servis', index=False)
        excel_data = output.getvalue()
        
        st.download_button(
            label="📊 Stáhnout kompletní Excel report flotily",
            data=excel_data,
            file_name=f"RHJ_Gastro_Flotila_Report_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    with ex_col2:
        sumar_txt = f"RHJ GASTRO - SOUHRNNY REPORT\nDatum vygenerovani: {datetime.now().strftime('%d.%m.%Y')}\n\nPocet vozidel: {len(df_auta_exp)}\nCelkem vydaje za palivo/energie: {df_tank['cena'].sum() if not df_tank.empty else 0} Kc\nCelkem vydaje za servis: {df_servis['cena'].sum() if not df_servis.empty else 0} Kc"
        st.download_button(
            label="📄 Stáhnout rychlý textový souhrn (TXT)",
            data=sumar_txt,
            file_name=f"RHJ_Souhrn_{datetime.now().strftime('%Y-%m-%d')}.txt",
            mime="text/plain"
        )

    st.markdown("<br><hr><br>", unsafe_allow_html=True)

    st.markdown("### ⛽ Hlášení spotřeby a efektivity (l/100 km nebo kWh/100 km)")
    if not df_tank.empty:
        spotreba_rows = []
        spz_unique = df_tank['spz'].unique()
        for s_spz in spz_unique:
            df_t_car = df_tank[df_tank['spz'] == s_spz].sort_values('km')
            if len(df_t_car) >= 2:
                prvni = df_t_car.iloc[0]
                posledni = df_t_car.iloc[-1]
                ujeto_km = posledni['km'] - prvni['km']
                celkem_mnozstvi = df_t_car['mnozstvi'].sum()
                if ujeto_km > 0:
                    spotreba_100 = round((celkem_mnozstvi / ujeto_km) * 100, 2)
                    spotreba_rows.append({'SPZ': s_spz, 'Ujeto km': ujeto_km, 'Spotřebováno (l/kWh)': celkem_mnozstvi, 'Průměr na 100 km': spotreba_100})
        
        if spotreba_rows:
            df_spotreba = pd.DataFrame(spotreba_rows)
            render_styled_table(df_spotreba)
        else:
            st.info("Pro výpočet spotřeby je potřeba alespoň 2 záznamy tankování s různým stavem tachometru u stejného auta.")
    else:
        st.info("Žádná data o tankování pro výpočet spotřeby.")

    st.markdown("<br><hr><br>", unsafe_allow_html=True)

    g_col1, g_col2 = st.columns(2)

    with g_col1:
        st.markdown("### ⚡ Náklady na palivo a energii (podle aut)")
        if not df_tank.empty:
            fig_palivo = px.bar(
                df_tank, 
                x='spz', 
                y='cena', 
                color='zdroj', 
                barmode='group',
                title="Výdaje za energie / palivo dle SPZ",
                color_discrete_sequence=px.colors.qualitative.Vivid
            )
            fig_palivo.update_layout(
                plot_bgcolor='rgba(0,0,0,0)', 
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#1e1b29', size=13),
                hoverlabel=dict(bgcolor="white", font_size=13, font_family="Inter")
            )
            st.plotly_chart(fig_palivo, use_container_width=True)
        else:
            st.info("Zatím nejsou k dispozici data o tankování.")

    with g_col2:
        st.markdown("### 🛠️ Porovnání nákladů na servis")
        if not df_servis.empty:
            fig_servis = px.pie(
                df_servis, 
                names='kategorie', 
                values='cena', 
                title="Podíl servisních nákladů podle kategorií",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Prism
            )
            fig_servis.update_layout(
                plot_bgcolor='rgba(0,0,0,0)', 
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#1e1b29', size=13),
                hoverlabel=dict(bgcolor="white", font_size=13, font_family="Inter")
            )
            st.plotly_chart(fig_servis, use_container_width=True)
        else:
            st.info("Zatím nejsou k dispozici servisní záznamy.")

    st.markdown("<br>", unsafe_allow_html=True)
    
    if not df_tank.empty or not df_servis.empty:
        st.markdown("### 👥 Náklady podle jednotlivých řidičů")
        df_tank_r = df_tank[['ridic', 'cena']].copy() if not df_tank.empty else pd.DataFrame(columns=['ridic', 'cena'])
        df_servis_r = df_servis[['ridic', 'cena']].copy() if not df_servis.empty else pd.DataFrame(columns=['ridic', 'cena'])
        df_spojene = pd.concat([df_tank_r, df_servis_r])
        df_spojene['ridic'] = df_spojene['ridic'].replace(['', None], 'Neznámý řidič').fillna('Neznámý řidič')
        df_soucet = df_spojene.groupby('ridic', as_index=False)['cena'].sum()

        fig_ridici = px.funnel(
            df_soucet, 
            x='cena', 
            y='ridic', 
            title="Celkové provozní náklady na řidiče (Palivo + Servis)",
            color_discrete_sequence=['#8b5cf6']
        )
        fig_ridici.update_layout(
            plot_bgcolor='rgba(0,0,0,0)', 
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#1e1b29', size=13),
            hoverlabel=dict(bgcolor="white", font_size=13, font_family="Inter")
        )
        st.plotly_chart(fig_ridici, use_container_width=True)

elif akt_sekce == '📱 QR Kód':
    st.header('📱 Generování QR kódů pro stínítka vozidel')
    st.markdown("Vyberte konkrétní vozidlo a vygenerujte specifický QR kód pro sluneční clonu.")
    
    zakladni_url = "https://spr-vaflotily-ys5pzghvkp3zoyxgebryvv.streamlit.app"
    
    df_auta_qr = get_vsechna_auta()
    if not df_auta_qr.empty:
        options_map = {}
        for _, row_item in df_auta_qr.iterrows():
            s_spz = row_item['spz']
            nazev_auta = row_item['nazev']
            r_jmeno = row_item['staly_ridic'] if row_item['staly_ridic'] and row_item['staly_ridic'] != 'Neuveden' else ''
            
            display_label = f"{s_spz} – {nazev_auta} (Řidič: {r_jmeno if r_jmeno else 'Neuveden'})"
            options_map[display_label] = (s_spz, r_jmeno)
            
        selected_label = st.selectbox("Vyberte vozidlo pro generování QR kódu:", list(options_map.keys()))
        qr_spz_vyber, staly_ridic_auta = options_map[selected_label]
        
        enc_spz = quote(str(qr_spz_vyber))
        enc_ridic = quote(str(staly_ridic_auta))
        cilova_url = f"{zakladni_url}/?spz={enc_spz}&ridic={enc_ridic}"
        
        st.markdown(f"**Cílová adresa pro vůz {qr_spz_vyber}:**")
        st.code(cilova_url)
        
        col_qr1, col_qr2 = st.columns([1, 2])
        with col_qr1:
            st.image(generuj_qr_kod(cilova_url), caption=f"SPZ: {qr_spz_vyber} | Řidič: {staly_ridic_auta or 'Neuveden'}", width=250)
        with col_qr2:
            zobrazeny_ridic = staly_ridic_auta if staly_ridic_auta else 'Neuveden'
            st.markdown(f"""
                ### 📌 Instrukce pro tisk:
                1. Vybrané vozidlo: **<span style="font-size: 1.2em; font-weight: bold;">{qr_spz_vyber}</span>** (Stálý řidič: {zobrazeny_ridic})
                2. QR kód si uložte nebo vytiskněte.
                3. Zalaminujte ho a nalepte na sluneční clonu vozidla.
                4. Kurýr po naskenování rovnou hlásí závady nebo tankování pro tento konkrétní vůz bez zdržování!
            """, unsafe_allow_html=True)
    else:
        st.info("V databázi nejsou žádná vozidla pro generování QR kódů.")

elif akt_sekce == '⚠️ Závady':
    st.header('⚠️ Hlášené závady vozidel')
    df_zavady = get_zavady()
    if not df_zavady.empty:
        render_styled_table(df_zavady)
        sel_z_id = st.selectbox('ID závady k vyřešení/smazání', df_zavady['id'].tolist(), key='del_zavada_sel')
        st.markdown('<div class="delete-tile-btn">', unsafe_allow_html=True)
        if st.button('Smazat / Vyřešit závadu'):
            smazat_zavadu(sel_z_id)
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info('Žádné nahlášené závady.')
