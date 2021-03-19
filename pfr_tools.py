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
from .scraper import get_soup
import re

with pkg_resources.open_text(league_data, 'pfr_missing.csv') as fid:
    pfr_missing_df = pd.read_csv(fid)

pfr_missing_dict = {}
for idx,row in pfr_missing_df.iterrows():
    pfr_missing_dict[row['unique_id']] = row['pfr_id']
    
def pfr_id_to_url(pfr_id):
    letter = pfr_id[0].upper()
    url = 'https://www.pro-football-reference.com/players/%s/%s.htm'%(letter,pfr_id)
    return url

def pfr_id_to_gamelog_url(pfr_id,year):
    letter = pfr_id[0].upper()
    url = 'https://www.pro-football-reference.com/players/%s/%s/gamelog/%d/'%(letter,pfr_id,year)
    return url


def check_position_mascot(pfr_id,position,mascot,verbose=False,strict=False):
    url = pfr_id_to_url(pfr_id)
    try:
        soup = get_soup(url,verbose=verbose)
        metas = soup.findAll('meta')
        for k in range(len(metas)):
            meta = metas.pop(0)
            content = meta.get('content')
            if content is not None:
                if content.find('Pos:')>-1:
                    term_list = [k.upper() for k in re.split('\W+',content)]
                    if verbose:
                        print(position.upper(),mascot.upper(),term_list)
                    if position.upper() in term_list:
                        if (not strict) or (mascot.upper() in term_list):
                                return True
    except:
        return False
    return False

    
def gamelog_to_fpts(df,position,name):
    #print(position)
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
            return 0.0
            
    scoring_rules = [('Passing_Cmp',0.1), ('Passing_Yds',0.04), ('Passing_TD',4.0), ('Passing_Int',(-2)), ('Rushing_Yds',0.1), ('Rushing_TD',6.0), ('Receiving_Rec',0.5), ('Receiving_Yds',0.1), ('Receiving_TD',6.0), ('Fumbles_Fmb',(-2))]
    pts = 0.0
    for rule in scoring_rules:
        try:
            pts = pts + df[rule[0]]*rule[1]
        except Exception as e:
            pass
            
    return pts


    
def get_player_gamelog(player,year):
    try:
        pfr_id = player.pfr_id
        
        if pfr_id=='NoId':
            return pd.DataFrame([])
        
        csv_cache = './.gamelogs'
        os.makedirs(csv_cache,exist_ok=True)
        cache_fn = os.path.join(csv_cache,'pfr_gamelog_%s_%d.csv'%(pfr_id,year))
        try:
            df = pd.read_csv(cache_fn)
            logging.info('Getting %s log from %s.'%(player.name,cache_fn))
        except:

            try:
                url = pfr_id_to_gamelog_url(pfr_id,year)
                dfs = pd.read_html(url)
                logging.info('Getting %s log from %s.'%(player.name,url))
            except:
                return pd.DataFrame([])

            

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
            zero_strings = ['Inactive','Injured Reserve','Did Not Play','COVID-19 List','Suspended','Exempt List']
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
            
    except KeyError:
        df = pd.DataFrame([])
    return df


class Attributes:
    def __init__(self,name):
        self.name = name
        self.height = np.nan
        self.weight = np.nan
        self.salary = np.nan
        self.hs = ''
        self.college = ''
        self.position = ''
        self.throws = ''
        
    def __str__(self):
        tup = (self.name,self.position,self.height,self.weight,self.salary,self.throws)
        try:
            return '%s (%s): %0.1f ft / %0.0f lb / $%d / %s '%tup
        except Exception as e:
            return '%s: no PFR attributes'%self.name

def get_player_attributes(player,verbose=False):
    
    pfr_id = player.pfr_id

    relish_tag = '%s_attributes'%player.unique_id

    try:
        att = relish.load(relish_tag)
    except:
        
        att = Attributes(player.name)
        
        if pfr_id=='NoId':
            return att
        
        try:
            url = pfr_id_to_url(pfr_id)
        except:
            # if the pfr_id is empty or nan
            return att


        soup = get_soup(url,verbose=verbose)
        ps = soup.findAll('p')
        scanning_for_hs = False
        scanning_for_college = False
        
        for k in range(len(ps)):
            text = ps[k].text
            if text.find('Position')>-1:
                try:
                    position = text.strip()[len('Position: '):].replace('\n',' ').replace('  ',' ').strip()
                    if position.find('Throws')>-1:
                        pos_root = position.split()[0]
                        if position.find('Right')>-1:
                            att.throws = 'right'
                        elif position.find('Left')>-1:
                            att.throws = 'left'
                        att.position = pos_root
                    else:
                        att.position = position
                except:
                    pass
            elif text.find('lb')>-1 and text.find(',')>-1:
                try:
                    temp = text[:text.find('lb')]
                    assert len(temp)>5
                    toks = temp.split()
                    htoks = toks[0].replace(',','').split('-')
                    height = float(htoks[0])+float(htoks[1])/12.0
                    weight = float(toks[1])
                    att.height = height
                    att.weight = weight
                except:
                    pass
            elif text.find('Current salary:')>-1:
                try:
                    att.salary = float(text[len('Current salary:'):].strip().replace(',',''))
                except:
                    pass
            # elif text.find('College:')>-1:
            #     scanning_for_college = True
            # elif text.find('High school:')>-1:
            #     scanning_for_hs = True

            # if scanning_for_college:
            #     print(text)
            #     if len(text)>3:
            #         att.college = text.strip()
            #         scanning_for_college = False

            # if scanning_for_hs:
            #     if len(text)>3:
            #         att.hs = text.strip()
            #         scanning_for_hs = False
        relish.save(relish_tag,att)
    return att
