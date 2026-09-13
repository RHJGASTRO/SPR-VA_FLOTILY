import pandas as pd
from datetime import datetime, timedelta
from db import get_vsechna_auta, get_zaznamy_servis, get_ridici

def ziskej_upozorneni():
    auta_df = get_vsechna_auta()
    servis_df = get_zaznamy_servis()
    ridici_df = get_ridici()
    
    dnes = datetime.today().date()
    limit = dnes + timedelta(days=30)
    
    upoz_stk = []
    upoz_dz = []
    upoz_poj = []
    upoz_olej = []
    upoz_ridicaky = []
    upoz_pneu = []
    
    if not auta_df.empty:
        for _, row in auta_df.iterrows():
            spz = row['spz']
            nazev = row['nazev']
            
            # STK
            if pd.notna(row['stk_do']):
                try:
                    stk_date = datetime.strptime(str(row['stk_do'])[:10], '%Y-%m-%d').date()
                    if stk_date <= limit:
                        upoz_stk.append(f"{spz} ({nazev}) - STK vyprší {stk_date}")
                except:
                    pass
                    
            # Dálniční známka
            if pd.notna(row['dz_do']):
                try:
                    dz_date = datetime.strptime(str(row['dz_do'])[:10], '%Y-%m-%d').date()
                    if dz_date <= limit:
                        upoz_dz.append(f"{spz} ({nazev}) - DZ vyprší {dz_date}")
                except:
                    pass
                    
            # Pojištění
            if pd.notna(row['pojisteni_do']):
                try:
                    poj_date = datetime.strptime(str(row['pojisteni_do'])[:10], '%Y-%m-%d').date()
                    if poj_date <= limit:
                        upoz_poj.append(f"{spz} ({nazev}) - Pojištění vyprší {poj_date}")
                except:
                    pass

    if not ridici_df.empty and 'platnost_ridicaku' in ridici_df.columns:
        for _, row in ridici_df.iterrows():
            jmeno = row['jmeno']
            if pd.notna(row['platnost_ridicaku']):
                try:
                    rid_date = datetime.strptime(str(row['platnost_ridicaku'])[:10], '%Y-%m-%d').date()
                    if rid_date <= limit:
                        upoz_ridicaky.append(f"{jmeno} - Řidičák vyprší {rid_date}")
                except:
                    pass

    return upoz_stk, upoz_dz, upoz_poj, upoz_olej, upoz_ridicaky, upoz_pneu
