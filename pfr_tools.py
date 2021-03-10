import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from unicodedata import normalize
import relish
from bs4 import BeautifulSoup
import requests
import sys,os
from .tools import Player
import importlib.resources as pkg_resources
from . import data as league_data

with pkg_resources.open_text(league_data, 'pfr_missing.csv') as fid:
    pfr_missing_df = pd.read_csv(fid)

pfr_missing_dict = {}
for idx,row in pfr_missing_df.iterrows():
    pfr_missing_dict[row['unique_id']] = row['pfr_id']

def gamelog_to_fpts(df,position,name):
    print(position)
    requirements = {'QB':['Passing_Cmp','Passing_Yds','Passing_TD','Passing_Int'],
                    'RB':['Rushing_Yds','Rushing_TD'],
                    'WR':['Receiving_Rec','Receiving_Yds','Receiving_TD'],
                    'TE':['Receiving_Rec','Receiving_Yds','Receiving_TD']}

    cols = df.columns
    for req in requirements[position]:
        try:
            assert req in cols
        except AssertionError:
            print(name)
            print(position)
            print(cols)
            print(req)
            sys.exit()
            
    
    scoring_rules = [('Passing_Cmp',0.1), ('Passing_Yds',0.04), ('Passing_TD',4.0), ('Passing_Int',(-2)), ('Rushing_Yds',0.1), ('Rushing_TD',6.0), ('Receiving_Rec',0.5), ('Receiving_Yds',0.1), ('Receiving_TD',6.0), ('Fumbles_Fmb',(-2))]
    pts = 0.0
    for rule in scoring_rules:
        try:
            pts = pts + df[rule[0]]*rule[1]
        except Exception as e:
            print(e)
            
    return pts


    
def get_player_gamelog(player,year):
    pfr_id = player.pfr_id
    if not type(pfr_id)==str:
        pfr_id = pfr_missing_dict[player.get_unique_id()]

    csv_cache = './.gamelogs'
    os.makedirs(csv_cache,exist_ok=True)
    cache_fn = os.path.join(csv_cache,'pfr_gamelog_%s_%d.csv'%(pfr_id,year))
    try:
        df = pd.read_csv(cache_fn)
    except:
        letter = pfr_id[0].upper()
        url = 'https://www.pro-football-reference.com/players/%s/%s/gamelog/%d/'%(letter,pfr_id,year)
        print(url)
        
        dfs = pd.read_html(url)

        # if there are multiple tables, the first one is regular season and the second is playoffs--ignore the latter
        df = dfs[0]

        new_columns = []
        
        for col in df.columns:
            if col[0].find('Unnamed')>-1:
                new_columns.append(col[1])
            else:
                new_columns.append('%s_%s'%(col[0],col[1]))

        df.columns = new_columns

        df = df[:-1]
        zero_strings = ['Inactive','Injured Reserve','Did Not Play','COVID-19 List']
        for zs in zero_strings:
            df = df.replace(zs,np.nan)
        
        
        for col in ['Rk', 'G#', 'Week', 'Age', 'Passing_Cmp', 'Passing_Att',
                    'Passing_Yds', 'Passing_TD', 'Passing_Int', 'Passing_Rate',
                    'Passing_Sk', 'Passing_Yds.1', 'Passing_Y/A', 'Passing_AY/A',
                    'Rushing_Att', 'Rushing_Yds', 'Rushing_Y/A', 'Rushing_TD', 'Scoring_TD',
                    'Scoring_Pts', 'Fumbles_Fmb', 'Fumbles_FL', 'Fumbles_FF', 'Fumbles_FR',
                    'Fumbles_Yds', 'Fumbles_TD', 'Off. Snaps_Num']:
            try:
                df[col] = df[col].astype(np.float64)
            except KeyError:
                pass
        
    fpts = gamelog_to_fpts(df,player.position,player.name)
    df['fpts'] = fpts
    df.to_csv(cache_fn)
    return df
