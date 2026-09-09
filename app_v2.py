# ==========================================
# VERZE 6.2.4 - Správa flotily - RHJ Gastro
# ==========================================

import asyncio
import base64
import io
import os
import socket
import sqlite3
import sys
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
import qrcode
import streamlit as st

# Oprava pro asyncio na Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

DB_NAME = 'flotila.db'
SUPERVISOR_PASSWORD = 'supervisor789'


def get_connection():
    return sqlite3.connect(DB_NAME, timeout=10)


def init_db():
    conn = get_connection()
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
        cursor.execute('SELECT vin FROM auta LIMIT 1')
    except sqlite3.OperationalError:
        cursor.execute('ALTER TABLE auta ADD COLUMN vin TEXT')
        
    try:
        cursor.execute("SELECT pojisteni_do FROM auta LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE auta ADD COLUMN pojisteni_do TEXT")

    try:
        cursor.execute("SELECT olej_interval FROM auta LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE auta ADD COLUMN olej_interval INTEGER DEFAULT 10000")

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
    cursor.execute(
        "INSERT OR IGNORE INTO nastaveni (klic, hodnota) VALUES ('admin_heslo', 'admin123')"
    )

    pocatecni_auta = [
        ('2M88435', 'Fiat Doblo', 'Natural', '2027-01-01', '2027-01-01', '2027-01-01', '175/70 R14 | 88T XL | 2.3 / 2.5 bar (Nákladní / Cargo)', 'Kolářová Zuzana', 'ZFA22300005463005', 10000),
        ('4B33954', 'Fiat Doblo', 'Natural', '2027-01-01', '2027-01-01', '2027-01-01', '175/70 R14 | 88T XL | 2.3 / 2.5 bar (Nákladní / Cargo)', 'Švadlenková Denisa', 'ZFA22300005443286', 10000),
        ('5E81583', 'Volkswagen Caddy', 'Nafta', '2027-01-01', '2027-01-01', '2027-01-01', '195/65 R15 | 91T / 95T XL | 2.4 / 2.8 bar (Zátěžová dodávka)', 'Lokaj Martin', 'WV1ZZZ2KZ9X101365', 10000),
        ('5E94630', 'Volkswagen Caddy', 'Nafta', '2027-01-01', '2027-01-01', '2027-01-01', '195/65 R15 | 91T / 95T XL | 2.4 / 2.8 bar (Zátěžová dodávka)', 'NÁHRADNÍ', 'WV1ZZZ2KZAX049128', 10000),
        ('5Z49372', 'Citroen Jumpy', 'Nafta', '2027-01-01', '2027-01-01', '2027-01-01', '215/60 R16C | 106/104T | 2.5 / 3.0 bar (Zátěžové C pneumatiky)', 'Mukařovský Martin', 'VF7XUAHZ8FZ013373', 10000),
        ('6E14928', 'Fiat Doblo', 'Nafta', '2027-01-01', '2027-01-01', '2027-01-01', '185/65 R15 | 88T / 92T XL | 2.3 / 2.6 bar (Nákladní / Cargo)', 'Doležal Martin', 'ZFA22300005374486', 10000),
        ('6E24392', 'Fiat Doblo', 'LPG', '2027-01-01', '2027-01-01', '2027-01-01', '175/70 R14 | 88T XL | 2.3 / 2.5 bar (V tabulce stav: prodáno)', 'NÁHRADNÍ', 'ZFA22300005559273', 10000),
        ('6E74807', 'Ford Transit', 'Nafta', '2027-01-01', '2027-01-01', '2027-01-01', '215/65 R16C | 109/107R | 3.5 / 4.5 bar (Zátěžové C pneumatiky)', 'Balog Marcel', 'WF0SXXTTFS8R16015', 10000),
        ('6E28016', 'Ford Transit', 'Nafta', '2027-01-01', '2027-01-01', '2027-01-01', '215/65 R16C | 109/107R | 3.5 / 4.5 bar (V tabulce stav: prodáno)', 'NÁHRADNÍ', 'WF0VXXBDFV4A52316', 10000),
        ('6E85382', 'Peugeot Partner', 'Nafta', '2027-01-01', '2027-01-01', '2027-01-01', '195/65 R15 | 91T / 95T XL | 2.4 / 2.8 bar (Nákladní / Cargo)', 'NÁHRADNÍ', 'VF3XT9HM0CZ005574', 10000),
        ('6E94181', 'IVECO', 'Nafta', '2027-01-01', '2027-01-01', '2027-01-01', '195/75 R16C | 107/105R | 4.5 / 4.5 bar (Zátěžové C pneumatiky)', 'ODPADY', 'ZCFA80F0002004883', 10000),
        ('6E94186', 'Peugeot Expert', 'Nafta', '2027-01-01', '2027-01-01', '2027-01-01', '215/60 R16C | 106/104T | 2.5 / 3.0 bar (Zátěžové C pneumatiky)', 'Anna Marie Sejpková', 'VF3XURHGH9Z033445', 10000),
        ('6T00251', 'Renault Thalia', 'Natural', '2027-01-01', '2027-01-01', '2027-01-01', '175/65 R14 | 82T | 2.1 / 2.0 bar (Osobní)', 'NÁHRADNÍ', 'VF1LBVU0540699987', 10000),
        ('7E22709', 'Volkswagen Transporter', 'Nafta', '2027-01-01', '2027-01-01', '2027-01-01', '205/65 R16C | 107/105T | 3.0 / 3.4 bar (Zátěžové C (T5))', 'NÁHRADNÍ', 'WV1ZZZ7HZ5H039974', 10000),
        ('7E36745', 'Fiat Doblo', 'Natural', '2027-01-01', '2027-01-01', '2027-01-01', '175/70 R14 | 88T XL | 2.3 / 2.5 bar (Nákladní / Cargo)', 'Slanařová Veronika', 'ZFA22300005712863', 10000),
        ('7P12357', 'Fiat Ducato', 'Nafta', '2027-01-01', '2027-01-01', '2027-01-01', '215/70 R15C | 109/107S | 4.5 / 5.0 bar (Zátěžové C pneumatiky)', 'NÁHRADNÍ', 'ZFA25000002G05606', 10000),
        ('7S71963', 'Volkswagen Caddy', 'Nafta', '2027-01-01', '2027-01-01', '2027-01-01', '195/65 R15 | 91T / 95T XL | 2.4 / 2.8 bar (Zátěžová dodávka)', 'Flekač Pavel', 'WV1ZZZ2KZ9X025434', 10000),
        ('EL141CR', 'Maxus E-Deliver 3', 'Elektřina', '2027-01-01', '2027-01-01', '2027-01-01', '185/65 R15 | 92H XL | 2.8 / 3.0 bar (Elektro (vyšší váha baterií))', 'Vohnout Oldřich', 'LSH14C4C0PA089247', 10000),
        ('EL142CR', 'Maxus E-Deliver 3', 'Elektřina', '2027-01-01', '2027-01-01', '2027-01-01', '185/65 R15 | 92H XL | 2.8 / 3.0 bar (Elektro (vyšší váha baterií))', 'Flekač Petr', 'LSH14C4C3NA068373', 10000),
        ('EL328CP', 'Maxus E-Deliver 3', 'Elektřina', '2027-01-01', '2027-01-01', '2027-01-01', '185/65 R15 | 92H XL | 2.8 / 3.0 bar (Elektro (vyšší váha baterií))', 'Šinkora Vladimír', 'LSH14C4C1NA068369', 10000),
        ('EL330CF', 'Maxus E-Deliver 3', 'Elektřina', '2027-01-01', '2027-01-01', '2027-01-01', '185/65 R15 | 92H XL | 2.8 / 3.0 bar (Elektro (vyšší váha baterií))', 'Trpkošová Iveta', 'LSH14C4C0PA089281', 10000),
        ('EL871EY', 'Maxus E-Deliver 3', 'Elektřina', '2027-01-01', '2027-01-01', '2027-01-01', '185/65 R15 | 92H XL | 2.8 / 3.0 bar (Elektro (vyšší váha baterií))', 'Kučerová Marie', 'LSH14C4C7LA116101', 10000),
        ('EL882EY', 'Maxus E-Deliver 3', 'Elektřina', '2027-01-01', '2027-01-01', '2027-01-01', '185/65 R15 | 92H XL | 2.8 / 3.0 bar (Elektro (vyšší váha baterií))', 'Akrman Stanislav', 'LSH14C4C5LA080067', 10000),
        ('EL952DF', 'Maxus SV3C', 'Elektřina', '2027-01-01', '2027-01-01', '2027-01-01', '185/65 R15 | 92H XL | 2.8 / 3.0 bar (Pozn.: SPZ uvedena 2x v Excelu)', 'Secká Zdenka', 'LSH14C4C0PA089216', 10000),
        ('EL945HA', 'Volkswagen EDCN Caddy', 'Elektřina', '2027-01-01', '2027-01-01', '2027-01-01', '195/65 R15 | 95T XL | 2.6 / 2.9 bar (Elektro přestavba Caddy)', 'Fraňková Veronika', 'WV1ZZZ2KZLX057133', 10000),
        ('EL952DF_2', 'Volkswagen EDCN Caddy', 'Elektřina', '2027-01-01', '2027-01-01', '2027-01-01', '195/65 R15 | 95T XL | 2.6 / 2.9 bar (Elektro přestavba Caddy)', 'NÁHRADNÍ', 'WV1ZZZ2KZLX039731', 10000)
    ]

    cursor.executemany(
        """
            INSERT OR REPLACE INTO auta (spz, nazev, typ_pohonu, stk_do, dz_do, pojisteni_do, pneu_rozmer, staly_ridic, vin, olej_interval)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        pocatecni_auta,
    )

    conn.commit()
    cursor.close()
    conn.close()


def obnovit_vychozi_auta():
    conn = get_connection()
    cursor = conn.cursor()
    pocatecni_auta = [
        ('2M88435', 'Fiat Doblo', 'Natural', '2027-01-01', '2027-01-01', '2027-01-01', '175/70 R14 | 88T XL | 2.3 / 2.5 bar (Nákladní / Cargo)', 'Kolářová Zuzana', 'ZFA22300005463005', 10000),
        ('4B33954', 'Fiat Doblo', 'Natural', '2027-01-01', '2027-01-01', '2027-01-01', '175/70 R14 | 88T XL | 2.3 / 2.5 bar (Nákladní / Cargo)', 'Švadlenková Denisa', 'ZFA22300005443286', 10000),
        ('5E81583', 'Volkswagen Caddy', 'Nafta', '2027-01-01', '2027-01-01', '2027-01-01', '195/65 R15 | 91T / 95T XL | 2.4 / 2.8 bar (Zátěžová dodávka)', 'Lokaj Martin', 'WV1ZZZ2KZ9X101365', 10000),
        ('5E94630', 'Volkswagen Caddy', 'Nafta', '2027-01-01', '2027-01-01', '2027-01-01', '195/65 R15 | 91T / 95T XL | 2.4 / 2.8 bar (Zátěžová dodávka)', 'NÁHRADNÍ', 'WV1ZZZ2KZAX049128', 10000),
        ('5Z49372', 'Citroen Jumpy', 'Nafta', '2027-01-01', '2027-01-01', '2027-01-01', '215/60 R16C | 106/104T | 2.5 / 3.0 bar (Zátěžové C pneumatiky)', 'Mukařovský Martin', 'VF7XUAHZ8FZ013373', 10000),
        ('6E14928', 'Fiat Doblo', 'Nafta', '2027-01-01', '2027-01-01', '2027-01-01', '185/65 R15 | 88T / 92T XL | 2.3 / 2.6 bar (Nákladní / Cargo)', 'Doležal Martin', 'ZFA22300005374486', 10000),
        ('6E24392', 'Fiat Doblo', 'LPG', '2027-01-01', '2027-01-01', '2027-01-01', '175/70 R14 | 88T XL | 2.3 / 2.5 bar (V tabulce stav: prodáno)', 'NÁHRADNÍ', 'ZFA22300005559273', 10000),
        ('6E74807', 'Ford Transit', 'Nafta', '2027-01-01', '2027-01-01', '2027-01-01', '215/65 R16C | 109/107R | 3.5 / 4.5 bar (Zátěžové C pneumatiky)', 'Balog Marcel', 'WF0SXXTTFS8R16015', 10000),
        ('6E28016', 'Ford Transit', 'Nafta', '2027-01-01', '2027-01-01', '2027-01-01', '215/65 R16C | 109/107R | 3.5 / 4.5 bar (V tabulce stav: prodáno)', 'NÁHRADNÍ', 'WF0VXXBDFV4A52316', 10000),
        ('6E85382', 'Peugeot Partner', 'Nafta', '2027-01-01', '2027-01-01', '2027-01-01', '195/65 R15 | 91T / 95T XL | 2.4 / 2.8 bar (Nákladní / Cargo)', 'NÁHRADNÍ', 'VF3XT9HM0CZ005574', 10000),
        ('6E94181', 'IVECO', 'Nafta', '2027-01-01', '2027-01-01', '2027-01-01', '195/75 R16C | 107/105R | 4.5 / 4.5 bar (Zátěžové C pneumatiky)', 'ODPADY', 'ZCFA80F0002004883', 10000),
        ('6E94186', 'Peugeot Expert', 'Nafta', '2027-01-01', '2027-01-01', '2027-01-01', '215/60 R16C | 106/104T | 2.5 / 3.0 bar (Zátěžové C pneumatiky)', 'Anna Marie Sejpková', 'VF3XURHGH9Z033445', 10000),
        ('6T00251', 'Renault Thalia', 'Natural', '2027-01-01', '2027-01-01', '2027-01-01', '175/65 R14 | 82T | 2.1 / 2.0 bar (Osobní)', 'NÁHRADNÍ', 'VF1LBVU0540699987', 10000),
        ('7E22709', 'Volkswagen Transporter', 'Nafta', '2027-01-01', '2027-01-01', '2027-01-01', '205/65 R16C | 107/105T | 3.0 / 3.4 bar (Zátěžové C (T5))', 'NÁHRADNÍ', 'WV1ZZZ7HZ5H039974', 10000),
        ('7E36745', 'Fiat Doblo', 'Natural', '2027-01-01', '2027-01-01', '2027-01-01', '175/70 R14 | 88T XL | 2.3 / 2.5 bar (Nákladní / Cargo)', 'Slanařová Veronika', 'ZFA22300005712863', 10000),
        ('7P12357', 'Fiat Ducato', 'Nafta', '2027-01-01', '2027-01-01', '2027-01-01', '215/70 R15C | 109/107S | 4.5 / 5.0 bar (Zátěžové C pneumatiky)', 'NÁHRADNÍ', 'ZFA25000002G05606', 10000),
        ('7S71963', 'Volkswagen Caddy', 'Nafta', '2027-01-01', '2027-01-01', '2027-01-01', '195/65 R15 | 91T / 95T XL | 2.4 / 2.8 bar (Zátěžová dodávka)', 'Flekač Pavel', 'WV1ZZZ2KZ9X025434', 10000),
        ('EL141CR', 'Maxus E-Deliver 3', 'Elektřina', '2027-01-01', '2027-01-01', '2027-01-01', '185/65 R15 | 92H XL | 2.8 / 3.0 bar (Elektro (vyšší váha baterií))', 'Vohnout Oldřich', 'LSH14C4C0PA089247', 10000),
        ('EL142CR', 'Maxus E-Deliver 3', 'Elektřina', '2027-01-01', '2027-01-01', '2027-01-01', '185/65 R15 | 92H XL | 2.8 / 3.0 bar (Elektro (vyšší váha baterií))', 'Flekač Petr', 'LSH14C4C3NA068373', 10000),
        ('EL328CP', 'Maxus E-Deliver 3', 'Elektřina', '2027-01-01', '2027-01-01', '2027-01-01', '185/65 R15 | 92H XL | 2.8 / 3.0 bar (Elektro (vyšší váha baterií))', 'Šinkora Vladimír', 'LSH14C4C1NA068369', 10000),
        ('EL330CF', 'Maxus E-Deliver 3', 'Elektřina', '2027-01-01', '2027-01-01', '2027-01-01', '185/65 R15 | 92H XL | 2.8 / 3.0 bar (Elektro (vyšší váha baterií))', 'Trpkošová Iveta', 'LSH14C4C0PA089281', 10000),
        ('EL871EY', 'Maxus E-Deliver 3', 'Elektřina', '2027-01-01', '2027-01-01', '2027-01-01', '185/65 R15 | 92H XL | 2.8 / 3.0 bar (Elektro (vyšší váha baterií))', 'Kučerová Marie', 'LSH14C4C7LA116101', 10000),
        ('EL882EY', 'Maxus E-Deliver 3', 'Elektřina', '2027-01-01', '2027-01-01', '2027-01-01', '185/65 R15 | 92H XL | 2.8 / 3.0 bar (Elektro (vyšší váha baterií))', 'Akrman Stanislav', 'LSH14C4C5LA080067', 10000),
        ('EL952DF', 'Maxus SV3C', 'Elektřina', '2027-01-01', '2027-01-01', '2027-01-01', '185/65 R15 | 92H XL | 2.8 / 3.0 bar (Pozn.: SPZ uvedena 2x v Excelu)', 'Secká Zdenka', 'LSH14C4C0PA089216', 10000),
        ('EL945HA', 'Volkswagen EDCN Caddy', 'Elektřina', '2027-01-01', '2027-01-01', '2027-01-01', '195/65 R15 | 95T XL | 2.6 / 2.9 bar (Elektro přestavba Caddy)', 'Fraňková Veronika', 'WV1ZZZ2KZLX057133', 10000),
        ('EL952DF_2', 'Volkswagen EDCN Caddy', 'Elektřina', '2027-01-01', '2027-01-01', '2027-01-01', '195/65 R15 | 95T XL | 2.6 / 2.9 bar (Elektro přestavba Caddy)', 'NÁHRADNÍ', 'WV1ZZZ2KZLX039731', 10000)
    ]
    cursor.executemany(
        """
            INSERT OR REPLACE INTO auta (spz, nazev, typ_pohonu, stk_do, dz_do, pojisteni_do, pneu_rozmer, staly_ridic, vin, olej_interval)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        pocatecni_auta,
    )
    conn.commit()
    cursor.close()
    conn.close()


def ziskej_admin_heslo():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT hodnota FROM nastaveni WHERE klic = 'admin_heslo'")
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row[0] if row else 'admin123'


def get_vsechna_auta():
    conn = get_connection()
    df = pd.read_sql_query(
        'SELECT spz, nazev, typ_pohonu, stk_do, dz_do, pojisteni_do, pneu_rozmer, staly_ridic, vin, olej_interval FROM auta ORDER BY spz ASC',
        conn,
    )
    conn.close()
    df = df.fillna('Neuveden')
    df.replace(['None', 'nan', ''], 'Neuveden', inplace=True)
    return df


def get_zaznamy_paliva():
    conn = get_connection()
    df = pd.read_sql_query(
        'SELECT id, spz, ridic, datum, km, zdroj, mnozstvi, cena, procenta_od, procenta_do, teplota FROM zaznamy ORDER BY datum DESC',
        conn,
    )
    conn.close()
    return df


def get_zaznamy_servis():
    conn = get_connection()
    df = pd.read_sql_query(
        'SELECT id, spz, ridic, datum, km, kategorie, popis, cena FROM servis ORDER BY datum DESC',
        conn,
    )
    conn.close()
    return df


def get_zavady():
    conn = get_connection()
    df = pd.read_sql_query(
        'SELECT id, spz, ridic, datum, popis, stav FROM zavady ORDER BY datum DESC',
        conn,
    )
    conn.close()
    return df


def get_ridici():
    conn = get_connection()
    df = pd.read_sql_query('SELECT id, jmeno, telefon, ridicak_do FROM ridici ORDER BY jmeno ASC', conn)
    conn.close()
    df = df.fillna('Neuveden')
    return df


def pridat_ridice(jmeno, telefon, ridicak_do):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO ridici (jmeno, telefon, ridicak_do) VALUES (?, ?, ?)",
        (jmeno, telefon, str(ridicak_do)),
    )
    conn.commit()
    cursor.close()
    conn.close()


def smazat_ridice(ridic_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM ridici WHERE id = ?', (ridic_id,))
    conn.commit()
    cursor.close()
    conn.close()


def pridat_zavadu(spz, ridic, popis):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO zavady (spz, ridic, popis, stav) VALUES (?, ?, ?, 'Nahlášeno')",
        (spz, ridic, popis),
    )
    conn.commit()
    cursor.close()
    conn.close()


def smazat_zavadu(zavada_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM zavady WHERE id = ?', (zavada_id,))
    conn.commit()
    cursor.close()
    conn.close()


def pridat_zaznam_paliva(spz, ridic, km, zdroj, mnozstvi, cena, p_od=0, p_do=100, teplota=0):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
            INSERT INTO zaznamy (spz, ridic, datum, km, zdroj, mnozstvi, cena, procenta_od, procenta_do, teplota)
            VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?)
        """,
        (spz, ridic, km, zdroj, mnozstvi, cena, p_od, p_do, teplota),
    )
    conn.commit()
    cursor.close()
    conn.close()


def smazat_zaznam_paliva(zaznam_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM zaznamy WHERE id = ?', (zaznam_id,))
    conn.commit()
    cursor.close()
    conn.close()


def smazat_servisni_zaznam(servis_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM servis WHERE id = ?', (servis_id,))
    conn.commit()
    cursor.close()
    conn.close()


def pridat_auto(
    spz, nazev, typ_pohonu, stk_do, dz_do, pojisteni_do, pneu_rozmer, staly_ridic, vin
):
    conn = get_connection()
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
    cursor.close()
    conn.close()


def upravit_auto(
    spz, nazev, typ_pohonu, stk_do, dz_do, pojisteni_do, pneu_rozmer, staly_ridic, vin
):
    conn = get_connection()
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
    cursor.close()
    conn.close()


def smazat_auto(spz):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM auta WHERE spz = ?', (spz,))
    conn.commit()
    cursor.close()
    conn.close()


def pridat_servisni_zaznam(spz, km, kategorie, popis, cena, ridic):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
            INSERT INTO servis (spz, km, kategorie, popis, cena, ridic)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
        (spz, km, kategorie, popis, cena, ridic),
    )
    conn.commit()
    cursor.close()
    conn.close()


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
    conn = get_connection()
    auta_df = pd.read_sql_query("SELECT spz, nazev, stk_do, dz_do, pojisteni_do, typ_pohonu FROM auta", conn)
    try:
        ridici_df = pd.read_sql_query("SELECT jmeno, ridicak_do FROM ridici", conn)
    except Exception:
        ridici_df = pd.DataFrame(columns=['jmeno', 'ridicak_do'])
    conn.close()
    
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
            conn_temp = get_connection()
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
            conn_temp.close()
            
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
    page_title='Správa flotily - RHJ Gastro [v6.2.4]', page_icon='🚀', layout='wide'
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

def zisti_zda_je_ev(spz):
    if not spz:
        return False
    conn = get_connection()
    res = pd.read_sql_query("SELECT typ_pohonu FROM auta WHERE spz = ?", conn, params=(spz,))
    conn.close()
    if res.empty:
        return False
    pohon = str(res.iloc[0]['typ_pohonu']).upper()
    return any(x in pohon for x in ['EV', 'ELEKTŘINA', 'ELEKTRE', 'BAT'])

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
                    <p style="color: #3d3156 !important; margin: 4px 0 0 0; font-size: 15px !important; font-weight: 600;">Rychlý záznam tankování / nabíjení pro vozidlo (v6.2.4)</p>
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
                <p style="color: #3d3156 !important; margin: 4px 0 0 0; font-size: 15px !important; font-weight: 600;">Rozvoz hotových jídel — Fleet Management & Operations System (v6.2.4)</p>
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

# ==================== NAVIGACE ====================
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

            if st.form_submit_button('Uložit vozidlo'):
                if new_spz:
                    pridat_auto(
                        new_spz,
                        new_nazev,
                        new_pohonu,
                        new_stk,
                        new_dz,
                        new_pojisteni,
                        new_pneu,
                        new_ridic,
                        new_vin,
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
                
                palivo_opts = ['Nafta', 'Natural', 'Elektřina', 'LPG']
                akt_paliva = str(row['typ_pohonu']).strip()
                palivo_idx = (
                    palivo_opts.index(akt_paliva)
                    if akt_paliva in palivo_opts
                    else 0
                )
                e_pohon = st.selectbox('Pohonná hmota', palivo_opts, index=palivo_idx)
                
                e_stk_do = st.text_input('STK do', value=row['stk_do'])
                e_dz = st.text_input('DZ do', value=row['dz_do'])
                e_pojisteni = st.text_input('Pojištění do', value=row['pojisteni_do'])
                e_pneu = st.text_input('Pneu rozměr', value=row['pneu_rozmer'])
                e_ridic = st.text_input('Stálý řidič', value=row['staly_ridic'])

                submitted_edit = st.form_submit_button('Uložit změny')
                if submitted_edit:
                    upravit_auto(
                        spz_to_edit,
                        e_nazev,
                        e_pohon,
                        e_stk_do,
                        e_dz,
                        e_pojisteni,
                        e_pneu,
                        e_ridic,
                        e_vin,
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
        c_add, c_reset = st.columns([1, 1])
        with c_add:
            if st.button('➕ Přidat nové vozidlo'):
                st.session_state['car_action'] = 'add'
                st.rerun()
        with c_reset:
            if st.button('🔄 Obnovit/Opravit výchozí data aut z tabulky'):
                obnovit_vychozi_auta()
                st.success('Data aut byla obnovena a uvedena do pořádku!')
                st.rerun()

        st.markdown('')
        df_auta = get_vsechna_auta()

        if not df_auta.empty:
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

                with cols[0]:
                    st.markdown(
                        f"""
                            <div class="{card_class1}">
                                <h3 style="margin: 0; color: #1e1b29;">🚗 {row1['nazev']}</h3>
                                <p style="margin: 4px 0;"><b>SPZ:</b> <span style="font-family: monospace; font-weight: 700;">{row1['spz']}</span></p>
                                <p style="margin: 4px 0;"><b>Pohonná hmota:</b> {row1['typ_pohonu']}</p>
                                <p style="margin: 4px 0;"><b>Stálý řidič:</b> {row1['staly_ridic']}</p>
                                <p style="margin: 4px 0;"><b>STK do:</b> {row1['stk_do']} | <b>DZ do:</b> {row1['dz_do']}</p>
                                <p style="margin: 4px 0;"><b>Pojištění do:</b> {row1['pojisteni_do']}</p>
                                <p style="margin: 4px 0;"><b>Pneu:</b> {row1['pneu_rozmer']}</p>
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

                    with cols[1]:
                        st.markdown(
                            f"""
                                <div class="{card_class2}">
                                    <h3 style="margin: 0; color: #1e1b29;">🚗 {row2['nazev']}</h3>
                                    <p style="margin: 4px 0;"><b>SPZ:</b> <span style="font-family: monospace; font-weight: 700;">{row2['spz']}</span></p>
                                    <p style="margin: 4px 0;"><b>Pohonná hmota:</b> {row2['typ_pohonu']}</p>
                                    <p style="margin: 4px 0;"><b>Stálý řidič:</b> {row2['staly_ridic']}</p>
                                    <p style="margin: 4px 0;"><b>STK do:</b> {row2['stk_do']} | <b>DZ do:</b> {row2['dz_do']}</p>
                                    <p style="margin: 4px 0;"><b>Pojištění do:</b> {row2['pojisteni_do']}</p>
                                    <p style="margin: 4px 0;"><b>Pneu:</b> {row2['pneu_rozmer']}</p>
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
            st.info('V databázi nejsou žádná vozidla.')

# ==================== 2. NASTAVENÍ ====================
elif akt_sekce == '⚙️ Nastavení':
    st.header('⚙️ Nastavení aplikace')
    conn = get_connection()
    cursor = conn.cursor()
    cena_kwh = cursor.execute(
        "SELECT hodnota FROM nastaveni WHERE klic = 'cena_kwh'"
    ).fetchone()[0]
    admin_h = cursor.execute(
        "SELECT hodnota FROM nastaveni WHERE klic = 'admin_heslo'"
    ).fetchone()[0]
    conn.close()

    with st.form('nastaveni_form'):
        nova_cena = st.number_input(
            'Cena elektřiny za kWh (Kč)',
            value=float(cena_kwh),
            format='%.2f',
        )
        nove_heslo = st.text_input('Změnit administrátorské heslo', value=str(admin_h), type='password')
        
        if st.form_submit_button('Uložit nastavení'):
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE nastaveni SET hodnota = ? WHERE klic = "cena_kwh"',
                (str(nova_cena),),
            )
            cursor.execute(
                'UPDATE nastaveni SET hodnota = ? WHERE klic = "admin_heslo"',
                (str(nove_heslo),),
            )
            conn.commit()
            conn.close()
            st.success('Nastavení úspěšně uloženo!')

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
            t_ridic = st.text_input('Řidič')
            t_km = st.number_input('Stav tachometru (km)', min_value=0, step=100)
            t_zdroj = st.selectbox(
                'Zdroj', ['Čerpací stanice', 'Wallbox', 'Zasuvka 220', 'Veřejná nabíječka']
            )
            t_mnozstvi = st.number_input(
                'Množství (litry / kWh)', min_value=0.0, step=1.0
            )
            t_cena = st.number_input('Celková cena (Kč)', min_value=0.0, step=10.0)
            if st.form_submit_button('Uložit záznam'):
                pridat_zaznam_paliva(t_spz, t_ridic, t_km, t_zdroj, t_mnozstvi, t_cena)
                st.success('Záznam o tankování/nabíjení byl přidán!')
                st.session_state['tank_action'] = 'view'
                st.rerun()
    else:
        if st.button('➕ Přidat nový záznam tankování'):
            st.session_state['tank_action'] = 'add'
            st.rerun()
        st.markdown('')
        df_zaz = get_zaznamy_paliva()
        if not df_zaz.empty:
            render_styled_table(df_zaz)
        else:
            st.info('Žádné záznamy o tankování.')

# ==================== 4. SERVIS ====================
elif akt_sekce == '🛠️ Servis':
    st.header('🛠️ Servisní záznamy')
    if st.session_state['servis_action'] == 'add':
        if st.button('🔙 Zpět na přehled servisu'):
            st.session_state['servis_action'] = 'view'
            st.rerun()

        with st.form('add_servis_form'):
            df_auta = get_vsechna_auta()
            spz_list = df_auta['spz'].tolist() if not df_auta.empty else []
            s_spz = st.selectbox('Vozidlo (SPZ)', spz_list)
            s_km = st.number_input('Stav tachometru (km)', min_value=0, step=100)
            s_kat = st.selectbox(
                'Kategorie',
                [
                    'Výměna oleje',
                    'Pneumatiky',
                    'STK oprava',
                    'Brzdy',
                    'Běžný servis',
                    'Ostatní',
                ],
            )
            s_popis = st.text_area('Popis provedeného servisu')
            s_cena = st.number_input('Celková cena (Kč)', min_value=0.0, step=100.0)
            s_ridic = st.text_input('Zodpovědná osoba / Řidič')

            if st.form_submit_button('Uložit servisní záznam'):
                pridat_servisni_zaznam(s_spz, s_km, s_kat, s_popis, s_cena, s_ridic)
                st.success('Servisní záznam byl úspěšně uložen!')
                st.session_state['servis_action'] = 'view'
                st.rerun()
    else:
        if st.button('➕ Přidat nový servisní záznam'):
            st.session_state['servis_action'] = 'add'
            st.rerun()
        st.markdown('')
        df_servis = get_zaznamy_servis()
        if not df_servis.empty:
            render_styled_table(df_servis)
        else:
            st.info('Žádné záznamy v servisu.')

# ==================== 5. ŘIDIČI ====================
elif akt_sekce == '👥 Řidiči':
    st.header('👥 Správa řidičů a řidičských průkazů')
    
    with st.form('add_ridic_form'):
        c_r1, c_r2, c_r3 = st.columns(3)
        with c_r1:
            r_jmeno = st.text_input('Jméno a příjmení řidiče')
        with c_r2:
            r_tel = st.text_input('Telefonní číslo')
        with c_r3:
            r_do = st.text_input('Platnost řidičáku do (YYYY-MM-DD)', value='2028-01-01')
            
        if st.form_submit_button('Uložit / Přidat řidiče'):
            if r_jmeno:
                pridat_ridice(r_jmeno, r_tel, r_do)
                st.success(f"Řidič {r_jmeno} byl úspěšně uložen!")
                st.rerun()
            else:
                st.error("Zadejte jméno řidiče.")
                
    st.markdown('---')
    df_ridici = get_ridici()
    if not df_ridici.empty:
        for idx, r_row in df_ridici.iterrows():
            cols = st.columns([3, 1])
            with cols[0]:
                st.markdown(f"**{r_row['jmeno']}** | Tel: {r_row['telefon']} | Řidičák do: `{r_row['ridicak_do']}`")
            with cols[1]:
                st.markdown('<div class="delete-tile-btn">', unsafe_allow_html=True)
                if st.button(f"Smazat##{r_row['id']}", key=f"del_r_{r_row['id']}"):
                    smazat_ridice(r_row['id'])
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("V databázi nejsou evidováni žádní samostatní řidiči.")

# ==================== 6. STATISTIKY ====================
elif akt_sekce == '📊 Statistiky':
    st.header('📊 Statistiky a přehledy flotily')
    
    col_st1, col_st2, col_st3 = st.columns(3)
    df_auta_stat = get_vsechna_auta()
    df_servis_stat = get_zaznamy_servis()
    df_palivo_stat = get_zaznamy_paliva()
    
    celk_auta = len(df_auta_stat)
    celk_nakl_s = df_servis_stat['cena'].sum() if not df_servis_stat.empty else 0
    celk_nakl_p = df_palivo_stat['cena'].sum() if not df_palivo_stat.empty else 0
    
    with col_st1:
        st.metric("Celkem vozidel", celk_auta)
    with col_st2:
        st.metric("Náklady na servis", f"{celk_nakl_s:,.2f} Kč")
    with col_st3:
        st.metric("Náklady na palivo/energie", f"{celk_nakl_p:,.2f} Kč")
        
    st.markdown('---')
    st.subheader('🚨 Aktuální přehled hlídání termínů a limitů')
    
    col_a1, col_a2 = st.columns(2)
    with col_a1:
        st.markdown('<div class="alert-box">', unsafe_allow_html=True)
        st.markdown('#### 📅 STK vozidel')
        if upoz_stk:
            for item in upoz_stk:
                st.markdown(item)
        else:
            st.success('Všechny STK jsou v pořádku (žádné do 30 dnů nekončí).')
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<br>', unsafe_allow_html=True)
        
        st.markdown('<div class="alert-box">', unsafe_allow_html=True)
        st.markdown('#### 🛡️ Pojištění vozidel')
        if upoz_poj:
            for item in upoz_poj:
                st.markdown(item)
        else:
            st.success('Všechna pojištění jsou v pořádku.')
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<br>', unsafe_allow_html=True)

        st.markdown('<div class="alert-box">', unsafe_allow_html=True)
        st.markdown('#### 🪪 Řidičské průkazy')
        if upoz_ridicaky:
            for item in upoz_ridicaky:
                st.markdown(item)
        else:
            st.success('Všechny řidičské průkazy jsou platné.')
        st.markdown('</div>', unsafe_allow_html=True)

    with col_a2:
        st.markdown('<div class="alert-box">', unsafe_allow_html=True)
        st.markdown('#### 🎫 Dálniční známky (DZ)')
        if upoz_dz:
            for item in upoz_dz:
                st.markdown(item)
        else:
            st.success('Všechny dálniční známky jsou v pořádku.')
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<br>', unsafe_allow_html=True)
        
        st.markdown('<div class="alert-box">', unsafe_allow_html=True)
        st.markdown('#### 🛢️ Výměna motorového oleje')
        if upoz_olej:
            st.markdown('<div class="oil-scroll-container">', unsafe_allow_html=True)
            for item in upoz_olej:
                st.markdown(item)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.success('Všechny výměny oleje jsou v pořádku.')
        st.markdown('</div>', unsafe_allow_html=True)

# ==================== 7. QR KÓD ====================
elif akt_sekce == '📱 QR Kód':
    st.header('📱 Generátor QR kódů pro řidiče')
    
    qr_sub_tab1, qr_sub_tab2 = st.tabs(["Jednotlivý QR kód", "🖨️ Hromadný tisk QR kódů (A4)"])
    
    with qr_sub_tab1:
        st.markdown('Vyberte řidiče a vozidlo pro vygenerování unikátního QR kódu a mobilního odkazu pro zápis tankování/nabíjení a hlášení závad.')

        df_auta = get_vsechna_auta()
        df_ridici_qr = get_ridici()

        seznam_ridicu_qr = []
        if not df_ridici_qr.empty and 'jmeno' in df_ridici_qr.columns:
            seznam_ridicu_qr.extend(df_ridici_qr['jmeno'].dropna().tolist())
        if not df_auta.empty and 'staly_ridic' in df_auta.columns:
            seznam_ridicu_qr.extend(df_auta['staly_ridic'].dropna().tolist())
        
        seznam_ridicu_qr = sorted(list(set([str(r).strip() for r in seznam_ridicu_qr if str(r).strip() and str(r).strip() != 'Neuveden'])))
        if not seznam_ridicu_qr:
            seznam_ridicu_qr = ["Neznámý řidič"]

        col_q1, col_q2 = st.columns(2)
        with col_q1:
            vybrany_ridic_qr = st.selectbox("1. Jméno řidiče", seznam_ridicu_qr, key="qr_select_ridic")
        
        with col_q2:
            if not df_auta.empty:
                df_auta['car_label'] = df_auta.apply(lambda r: f"{r['nazev']} (SPZ: {r['spz']})", axis=1)
                vybrane_auto_label = st.selectbox("2. Typ auta + SPZ", df_auta['car_label'].tolist(), key="qr_select_auto")
                vybrane_auto_row = df_auta[df_auta['car_label'] == vybrane_auto_label].iloc[0]
                vybrana_spz = vybrane_auto_row['spz']
            else:
                vybrana_spz = None

        if vybrana_spz:
            base_url = "https://spr-vaflotily-ys5pzghvkp3zoyxgebryvv.streamlit.app/"
            url_adresa = f"{base_url}?spz={vybrana_spz}&ridic={vybrany_ridic_qr}"

            st.markdown('---')
            st.subheader(f"Vygenerovaný QR kód pro řidiče **{vybrany_ridic_qr}** a vozidlo **{vybrana_spz}**")

            c_qr1, c_qr2 = st.columns([1, 2])
            with c_qr1:
                qr_bytes = generuj_qr_kod(url_adresa)
                st.image(qr_bytes, width=220, caption=f"SPZ: {vybrana_spz} | Řidič: {vybrany_ridic_qr}")
            with c_qr2:
                st.markdown(f"**Odkaz pro QR kód:**")
                st.code(url_adresa)
                st.download_button(
                    label=f"📥 Stáhnout QR kód (PNG)",
                    data=qr_bytes,
                    file_name=f"qr_kod_{vybrana_spz}_{vybrany_ridic_qr.replace(' ', '_')}.png",
                    mime="image/png",
                    key="dl_qr_custom"
                )
        else:
            st.info('V databázi nejsou žádná vozidla pro generování QR kódů.')

    with qr_sub_tab2:
        st.subheader("🖨️ Hromadný přehled QR kódů pro tisk na A4")
        st.markdown("Zde vidíte mřížku všech vozidel. Můžete ji pohodlně vytisknout přes tiskové okno prohlížeče (Ctrl+P / Cmd+P), vystřihnout a zalaminovat do aut.")
        
        if st.button("🖨️ Spustit tisk stránky (Otevřít tiskové okno)"):
            st.markdown("""
                <script>
                    window.print();
                </script>
            """, unsafe_allow_html=True)
            
        st.markdown("---")
        
        df_all_cars_print = get_vsechna_auta()
        if not df_all_cars_print.empty:
            base_url = "https://spr-vaflotily-ys5pzghvkp3zoyxgebryvv.streamlit.app/"
            
            # Vykreslení do mřížky (po 3 sloupcích)
            cars_list_p = df_all_cars_print.to_dict('records')
            for i in range(0, len(cars_list_p), 3):
                p_cols = st.columns(3)
                for j in range(3):
                    if i + j < len(cars_list_p):
                        car = cars_list_p[i + j]
                        car_spz = car['spz']
                        car_nazev = car['nazev']
                        car_ridic = car['staly_ridic'] if car['staly_ridic'] != 'Neuveden' else 'Neznámý řidič'
                        
                        print_url = f"{base_url}?spz={car_spz}&ridic={car_ridic}"
                        q_img_bytes = generuj_qr_kod(print_url)
                        
                        encoded_img = base64.b64encode(q_img_bytes).decode()
                        
                        with p_cols[j]:
                            st.markdown(f"""
                                <div style="border: 2px dashed #5b4b8a; border-radius: 12px; padding: 15px; text-align: center; background: white; margin-bottom: 15px; box-shadow: 0 2px 6px rgba(0,0,0,0.05);">
                                    <h4 style="margin: 0 0 5px 0; color: #5b4b8a; font-size: 16px;">RHJ Gastro – Flotila</h4>
                                    <div style="font-size: 18px; font-weight: 900; color: #1e1b29; margin-bottom: 5px;">{car_spz}</div>
                                    <div style="font-size: 13px; color: #444; margin-bottom: 8px;">{car_nazev}<br>Řidič: <b>{car_ridic}</b></div>
                                    <img src="data:image/png;base64,{encoded_img}" width="150" style="margin: 5px 0;" />
                                    <div style="font-size: 10px; color: #777; margin-top: 5px;">Naskenujte pro zápis tankování / závady</div>
                                </div>
                            """, unsafe_allow_html=True)
        else:
            st.info("V databázi nejsou žádná vozidla pro hromadný tisk.")

# ==================== 8. ZÁVADY ====================
elif akt_sekce == '⚠️ Závady':
    st.header('⚠️ Hlášené závady vozidel')
    df_zav = get_zavady()
    if not df_zav.empty:
        for idx, z_row in df_zav.iterrows():
            with st.container():
                st.markdown(
                    f"""
                    <div style="background: white; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; margin-bottom: 10px;">
                        <b>Vozidlo SPZ:</b> {z_row['spz']} | <b>Řidič:</b> {z_row['ridic']} | <b>Datum:</b> {z_row['datum']}<br>
                        <b>Popis závady:</b> {z_row['popis']}<br>
                        <b>Stav:</b> <span style="color: #ea580c; font-weight: 700;">{z_row['stav']}</span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                if st.button(f"Vyřešit / Smazat závadu ID {z_row['id']}", key=f"del_z_{z_row['id']}"):
                    smazat_zavadu(z_row['id'])
                    st.rerun()
    else:
        st.success('Žádné nahlášené závady.')
