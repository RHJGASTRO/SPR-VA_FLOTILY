import sqlite3
import pandas as pd
from datetime import datetime

DB_NAME = 'flotila.db'

def get_connection():
    return sqlite3.connect(DB_NAME, timeout=10)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Vytvoření tabulek
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS auta (
            spz TEXT PRIMARY KEY,
            nazev TEXT,
            typ_pohonu TEXT,
            stk_do TEXT,
            dz_do TEXT,
            pojisteni_do TEXT,
            pneu_rozmer TEXT,
            pneu_druh TEXT,
            staly_ridic TEXT,
            vin TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS zaznamy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spz TEXT,
            ridic TEXT,
            km INTEGER,
            zdroj TEXT,
            mnozstvi REAL,
            cena REAL,
            stav_baterie_pred INTEGER,
            stav_baterie_po INTEGER,
            zbyva_kwh REAL,
            datum TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS servis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spz TEXT,
            km INTEGER,
            kategorie TEXT,
            popis TEXT,
            cena REAL,
            ridic TEXT,
            datum TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS zavady (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spz TEXT,
            ridic TEXT,
            popis TEXT,
            stav TEXT DEFAULT 'Nahlášeno',
            datum TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ridici (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jmeno TEXT,
            telefon TEXT,
            platnost_ridicaku TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS karty (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cislo_karty TEXT UNIQUE,
            ridic TEXT,
            mesicni_limit REAL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS nastaveni (
            klic TEXT PRIMARY KEY,
            hodnota TEXT
        )
    ''')
    
    # Výchozí nastavení
    cursor.execute('INSERT OR IGNORE INTO nastaveni (klic, hodnota) VALUES ("cena_kwh", "6.50")')
    cursor.execute('INSERT OR IGNORE INTO nastaveni (klic, hodnota) VALUES ("admin_heslo", "admin123")')
    cursor.execute('INSERT OR IGNORE INTO nastaveni (klic, hodnota) VALUES ("sefka_mail", "rhjvedeni@gmail.com")')
    cursor.execute('INSERT OR IGNORE INTO nastaveni (klic, hodnota) VALUES ("sefka_mobil", "+420777000000")')

    conn.commit()
    
    # Kontrola, zda jsou v DB auta, pokud ne, naplníme fiktivními data
    cursor.execute('SELECT COUNT(*) FROM auta')
    count = cursor.fetchone()[0]
    if count == 0:
        obnovit_vychozi_auta_db(cursor)
        conn.commit()
        
    cursor.close()
    conn.close()

def obnovit_vychozi_auta():
    conn = get_connection()
    cursor = conn.cursor()
    obnovit_vychozi_auta_db(cursor)
    conn.commit()
    cursor.close()
    conn.close()

def obnovit_vychozi_auta_db(cursor):
    ukazkova_auta = [
        ('2M88435', 'Ford Transit', 'Nafta', '2027-05-10', '2027-01-01', '2027-03-15', '215/65 R16', 'Celoroční', 'Kolářová Zuzana', 'WF0XXGBFSK8855123'),
        ('1A23456', 'Renault Master', 'Nafta', '2026-10-12', '2027-01-01', '2027-06-01', '225/65 R16', 'Letní', 'Novák Petr', 'VF1FOB40512345678'),
        ('5Z49372', 'Škoda Citigo eIV', 'Elektřina', '2027-08-20', '2027-01-01', '2027-02-10', '165/70 R14', 'Zimní', 'Testovací řidič', 'TMBZZZAAZLK987654'),
        ('3B11122', 'Peugeot Boxer', 'Nafta', '2026-09-15', '2027-01-01', '2027-04-01', '215/70 R15', 'Celoroční', 'Svoboda Jan', 'VF3YCTMFC12398765')
    ]
    cursor.executemany('''
        INSERT OR REPLACE INTO auta (spz, nazev, typ_pohonu, stk_do, dz_do, pojisteni_do, pneu_rozmer, pneu_druh, staly_ridic, vin)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', ukazkova_auta)

def ziskej_admin_heslo():
    conn = get_connection()
    cursor = conn.cursor()
    res = cursor.execute("SELECT hodnota FROM nastaveni WHERE klic = 'admin_heslo'").fetchone()
    conn.close()
    return res[0] if res else 'admin123'

def get_vsechna_auta():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM auta", conn)
    conn.close()
    return df

def pridat_auto(spz, nazev, typ_pohonu, stk_do, dz_do, pojisteni_do, pneu_rozmer, pneu_druh, staly_ridic, vin):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO auta (spz, nazev, typ_pohonu, stk_do, dz_do, pojisteni_do, pneu_rozmer, pneu_druh, staly_ridic, vin)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (spz, nazev, typ_pohonu, stk_do, dz_do, pojisteni_do, pneu_rozmer, pneu_druh, staly_ridic, vin))
    conn.commit()
    cursor.close()
    conn.close()

def upravit_auto(spz, nazev, typ_pohonu, stk_do, dz_do, pojisteni_do, pneu_rozmer, pneu_druh, staly_ridic, vin):
    pridat_auto(spz, nazev, typ_pohonu, stk_do, dz_do, pojisteni_do, pneu_rozmer, pneu_druh, staly_ridic, vin)

def smazat_auto(spz):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM auta WHERE spz = ?", (spz,))
    conn.commit()
    cursor.close()
    conn.close()

def get_zaznamy_paliva():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM zaznamy", conn)
    conn.close()
    return df

def pridat_zaznam_paliva(spz, ridic, km, zdroj, mnozstvi, cena, stav_baterie_pred=0, stav_baterie_po=100, zbyva_kwh=0.0):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO zaznamy (spz, ridic, km, zdroj, mnozstvi, cena, stav_baterie_pred, stav_baterie_po, zbyva_kwh)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (spz, ridic, km, zdroj, mnozstvi, cena, stav_baterie_pred, stav_baterie_po, zbyva_kwh))
    conn.commit()
    cursor.close()
    conn.close()

def get_zaznamy_servis():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM servis", conn)
    conn.close()
    return df

def pridat_servisni_zaznam(spz, km, kategorie, popis, cena, ridic):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO servis (spz, km, kategorie, popis, cena, ridic)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (spz, km, kategorie, popis, cena, ridic))
    conn.commit()
    cursor.close()
    conn.close()

def get_zavady():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM zavady", conn)
    conn.close()
    return df

def pridat_zavadu(spz, ridic, popis):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO zavady (spz, ridic, popis, stav)
        VALUES (?, ?, ?, 'Nahlášeno')
    ''', (spz, ridic, popis))
    conn.commit()
    cursor.close()
    conn.close()

def smazat_zavadu(zavada_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM zavady WHERE id = ?", (zavada_id,))
    conn.commit()
    cursor.close()
    conn.close()

def get_ridici():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM ridici", conn)
    conn.close()
    return df

def pridat_ridice(jmeno, telefon, platnost_ridicaku):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO ridici (jmeno, telefon, platnost_ridicaku)
        VALUES (?, ?, ?)
    ''', (jmeno, telefon, platnost_ridicaku))
    conn.commit()
    cursor.close()
    conn.close()

def smazat_ridice(ridic_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ridici WHERE id = ?", (ridic_id,))
    conn.commit()
    cursor.close()
    conn.close()

def get_karty():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM karty", conn)
    conn.close()
    return df

def pridat_kartu(cislo_karty, ridic, mesicni_limit):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO karty (cislo_karty, ridic, mesicni_limit)
        VALUES (?, ?, ?)
    ''', (cislo_karty, ridic, mesicni_limit))
    conn.commit()
    cursor.close()
    conn.close()

def smazat_kartu(cislo_karty):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM karty WHERE cislo_karty = ?", (cislo_karty,))
    conn.commit()
    cursor.close()
    conn.close()
