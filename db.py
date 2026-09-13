import sqlite3
import pandas as pd
from datetime import datetime

DB_NAME = 'flotila.db'

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

    try:
        cursor.execute("SELECT pneu_druh FROM auta LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE auta ADD COLUMN pneu_druh TEXT DEFAULT 'Celoroční'")

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
        CREATE TABLE IF NOT EXISTS karty (
            cislo_karty TEXT PRIMARY KEY,
            ridic TEXT NOT NULL,
            mesicni_limit REAL DEFAULT 0
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
        'SELECT spz, nazev, typ_pohonu, stk_do, dz_do, pojisteni_do, pneu_rozmer, pneu_druh, staly_ridic, vin, olej_interval FROM auta ORDER BY spz ASC',
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

def get_karty():
    conn = get_connection()
    df = pd.read_sql_query('SELECT cislo_karty, ridic, mesicni_limit FROM karty ORDER BY ridic ASC', conn)
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

def pridat_kartu(cislo, ridic, limit):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT OR REPLACE INTO karty (cislo_karty, ridic, mesicni_limit) VALUES (?, ?, ?)',
        (cislo, ridic, float(limit))
    )
    conn.commit()
    cursor.close()
    conn.close()

def smazat_kartu(cislo):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM karty WHERE cislo_karty = ?', (cislo,))
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

def pridat_auto(spz, nazev, typ_pohonu, stk_do, dz_do, pojisteni_do, pneu_rozmer, pneu_druh, staly_ridic, vin):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
            INSERT INTO auta (spz, nazev, typ_pohonu, stk_do, dz_do, pojisteni_do, pneu_rozmer, pneu_druh, staly_ridic, vin, olej_interval)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 10000)
        """,
        (spz, nazev, typ_pohonu, str(stk_do), str(dz_do), str(pojisteni_do), pneu_rozmer, pneu_druh, staly_ridic, vin),
    )
    conn.commit()
    cursor.close()
    conn.close()

def upravit_auto(spz, nazev, typ_pohonu, stk_do, dz_do, pojisteni_do, pneu_rozmer, pneu_druh, staly_ridic, vin):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
            UPDATE auta 
            SET nazev = ?, typ_pohonu = ?, stk_do = ?, dz_do = ?, pojisteni_do = ?, pneu_rozmer = ?, pneu_druh = ?, staly_ridic = ?, vin = ?, olej_interval = 10000
            WHERE spz = ?
        """,
        (nazev, typ_pohonu, str(stk_do), str(dz_do), str(pojisteni_do), pneu_rozmer, pneu_druh, staly_ridic, vin, spz),
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

def ziskej_upozorneni():
    conn = get_connection()
    auta_df = pd.read_sql_query("SELECT spz, nazev, stk_do, dz_do, pojisteni_do, typ_pohonu, pneu_druh FROM auta", conn)
    
    km_df = pd.read_sql_query("""
        SELECT spz, MAX(km) as max_km FROM (
            SELECT spz, km FROM zaznamy
            UNION ALL
            SELECT spz, km FROM servis
        ) GROUP BY spz
    """, conn)
    
    olej_df = pd.read_sql_query("""
        SELECT spz, MAX(km) as max_olej_km FROM servis 
        WHERE kategorie='Výměna oleje' GROUP BY spz
    """, conn)
    
    try:
        ridici_df = pd.read_sql_query("SELECT jmeno, ridicak_do FROM ridici", conn)
    except Exception:
        ridici_df = pd.DataFrame(columns=['jmeno', 'ridicak_do'])
    conn.close()
    
    km_dict = dict(zip(km_df['spz'], km_df['max_km'])) if not km_df.empty else {}
    olej_dict = dict(zip(olej_df['spz'], olej_df['max_olej_km'])) if not olej_df.empty else {}
    
    upozorneni_stk = []
    upozorneni_dz = []
    upozorneni_poj = []
    upozorneni_olej = []
    upozorneni_ridicaky = []
    upozorneni_pneu = []
    
    dnes = datetime.now().date()
    akt_mesic = dnes.month
    
    for _, auto in auta_df.iterrows():
        spz = auto['spz']
        
        druh_pneu = auto.get('pneu_druh', 'Celoroční')
        if akt_mesic in [10, 11] and druh_pneu == 'Letní':
            upozorneni_pneu.append(f"❄️ **{spz}**: Blíží se zima, zvažte přezutí (Nyní: Letní).")
        elif akt_mesic in [4, 5] and druh_pneu == 'Zimní':
            upozorneni_pneu.append(f"☀️ **{spz}**: Jaro je tu, zvažte přezutí (Nyní: Zimní).")
        
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
            aktualni_km = int(km_dict.get(spz, 0))
            posledni_olej_km = olej_dict.get(spz, None)
            
            if posledni_olej_km is not None and not pd.isna(posledni_olej_km):
                posledni_olej_km = int(posledni_olej_km)
                zbyva_km = (posledni_olej_km + 10000) - aktualni_km
                if zbyva_km < 0:
                    upozorneni_olej.append(f"🚨 **{spz}**: Přejeta výměna o {abs(zbyva_km)} km!")
                elif zbyva_km <= 1000:
                    upozorneni_olej.append(f"🛢️ **{spz}**: Zbývá {zbyva_km} km do výměny.")
            else:
                upozorneni_olej.append(f"ℹ️ **{spz}**: Chybí záznam výměny v Servisu.")

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

    return upozorneni_stk, upozorneni_dz, upozorneni_poj, upozorneni_olej, upozorneni_ridicaky, upozorneni_pneu

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
