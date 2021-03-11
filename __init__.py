import relish
import logging
import requests
import requests_cache
import sys,os,glob,time
import pandas as pd
import importlib.resources as pkg_resources
from . import data as league_data
from .tools import League,Player,Team
from nfldata import data as sharpe_data
from .matcher import fuzzy_get_df
from .pfr_tools import pfr_id_to_url
from .scraper import get_soup
import re

logging.basicConfig(filename='fantasy_tools.log', level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler())

with pkg_resources.open_text(league_data, 'nfl_teams.csv') as fid:
    teams_df = pd.read_csv(fid)
        
with pkg_resources.open_text(league_data, 'owners.csv') as fid:
    owners_df = pd.read_csv(fid)

with pkg_resources.open_text(sharpe_data, 'pff_pfr_map_v1.csv') as fid:
    player_name_df = pd.read_csv(fid)

with pkg_resources.open_text(sharpe_data, 'draft_picks.csv') as fid:
    draft_df = pd.read_csv(fid)

# For the next dataset, we need to download ECR table from FP:
# 1. Go to the URL https://www.fantasypros.com/nfl/rankings/half-point-ppr-cheatsheets.php
# 2. Make sure 'Overall' is selected
# 3. Click the download button and save
# 4. Copy the file to the local data directory, e.g. BLL2021/data/fp_rankings.csv
# Check and warn if the file is old
def get_rankings_df(max_age_days=30):
    rankings_file_stat = os.stat('./data/fp_rankings.csv')
    rankings_age_days = (time.time()-rankings_file_stat.st_mtime)/(24.0*3600.0)
    if rankings_age_days>max_age_days:
        sys.exit('Rankings old! Get some new ones at https://www.fantasypros.com/nfl/rankings/half-point-ppr-cheatsheets.php and put them in the local data folder.')
    rankings_df = pd.read_csv('./data/fp_rankings.csv')
    return rankings_df


position_color_dict = {'QB':'b','RB':'g','WR':'r','TE':'y','D/ST':'k','K':'k'}

def posrank_split(posrank):
    temp = posrank[::-1]
    rev_rank_string = ''
    rev_pos_string = ''
    
    for idx in range(len(temp)):
        try:
            int(temp[idx])
            rev_rank_string = rev_rank_string + temp[idx]
        except:
            rev_pos_string = rev_pos_string + temp[idx]
    return rev_pos_string[::-1],int(rev_rank_string[::-1])


def get_id(name,position,team):
    name = name.replace(' ','')
    name = name.replace('.','')
    name = name.replace(',','')
    name = name.replace('-','')
    name = name.replace("'","")
    out = name.lower().strip()+position.lower().strip()+team.lower().strip()
    return out

def build_player_table0():
    # This function builds a big table of player data out of Lee Sharpe's pff_pfr_map and FP's rankings;
    # it uses FP's rankings to identify the players of interest (skipping defense and kicker),
    # and then Sharpe's table to connect with PFF and PFR IDs

    try:
        player_df = pd.read_csv('./data/player_table.csv')
    except Exception:
        rankings_df = get_rankings_df()
        
        
        name_row_default = ['']*4
        draft_row_default = ['']*10
        # Now we look for matches in sharpe column 'pff_name', using FP 'PLAYER NAME':
        
        player_table = []
        for idx,row in rankings_df.iterrows():
            fp_name = row['PLAYER NAME']
            
            #if not fp_name=='Josh Allen':
            #    continue

            position,rank = posrank_split(row['POS'])
            if not position in ['QB','RB','WR','TE']:
                continue
            team = row['TEAM']

            team_row = teams_df[teams_df['Abbreviation']==team]
            team_name = team_row['Name'].values[0]
            
            mascot = team_name.split(' ')[-1]
        
            player_id = get_id(fp_name,position,team)

            for letter in player_id:
                try:
                    assert letter in 'abcdefghijklmnopqrstuvwxyz'
                except:
                    print('%s is not a lower case letter'%letter)
                    sys.exit()
                    
            out_list = row.values.tolist()
            
            name_map_df = fuzzy_get_df(player_name_df,'pff_name',fp_name)

            if name_map_df is not None:
                if len(name_map_df)>1:
                    for idx,row in name_map_df.iterrows():
                        url = pfr_id_to_url(row['pfr_id'])
                        soup = get_soup(url)
                        metas = soup.findAll('meta')
                        for k in range(len(metas)):
                            meta = metas.pop(0)
                            content = meta.get('content')
                            if content is not None:
                                if content.find('Pos:')>-1:
                                    term_list = [k.upper() for k in re.split('\W+',content)]
                                    if position.upper() in term_list and mascot.upper() in term_list:
                                        
                                        name_map_df = pd.DataFrame([row])
                                        break
                                
            if name_map_df is None:
                name_map_list = name_row_default
            else:
                name_map_list = name_map_df.values.tolist()[0]

            draft_row = fuzzy_get_df(draft_df,'pfr_name',fp_name,threshold=0.8,verbose=True)
            if draft_row is None:
                draft_list = draft_row_default
            else:
                if len(draft_row)>1:
                    draft_row = draft_row[draft_row['position']==position]
                    if len(draft_row)>1:
                        draft_row = draft_row[draft_row['team']==team]
                        if len(draft_row)>1:
                            sys.exit('Too many %s named %s playing for %s.'%(position,fp_name,team))
                try:
                    draft_list = draft_row.values.tolist()[0]
                except:
                    print('fault:',draft_row)
                    draft_list = draft_row_default


            print(player_id)
            print(out_list)
            print(name_map_list)
            print(draft_list)
            out_list = [player_id] + out_list + name_map_list + draft_list
            print(len(out_list),out_list)
            assert len(out_list)==24
            player_table.append(out_list)
            
        fp_columns = ['RK', 'TIERS', 'PLAYER NAME', 'TEAM', 'POS', 'BEST', 'WORST', 'AVG.', 'STD.DEV']
        name_map_columns = ['pff_id', 'pfr_id', 'pff_name', 'pff_url_name']
        draft_columns = ['season', 'team', 'round', 'pick', 'playerid', 'full_name', 'name', 'side', 'category', 'position']
        
        output_columns = ['unique_id']+fp_columns+name_map_columns+draft_columns

        player_df = pd.DataFrame(player_table,columns=output_columns)
        player_df.to_csv('./data/player_table.csv')
    return player_df



def build_player_table():
    # This function builds a big table of player data out of Lee Sharpe's pff_pfr_map and FP's rankings;
    # it uses FP's rankings to identify the players of interest (skipping defense and kicker),
    # and then Sharpe's table to connect with PFF and PFR IDs

    try:
        foob=boof
        player_df = pd.read_csv('./data/player_table.csv')
    except Exception:
        rankings_df = get_rankings_df()
        
        player_name_sub_df_default = ['']*4
        draft_sub_df_default = ['']*10

        fp_columns = ['RK', 'TIERS', 'PLAYER NAME', 'TEAM', 'POS', 'BEST', 'WORST', 'AVG.', 'STD.DEV']
        name_map_columns = ['pff_id', 'pfr_id', 'pff_name', 'pff_url_name']
        draft_columns = ['season', 'team', 'round', 'pick', 'playerid', 'full_name', 'name', 'side', 'category', 'position']
        
        output_columns = ['unique_id']+fp_columns+name_map_columns+draft_columns

        
        player_table = []
        for idx,row in rankings_df.iterrows():
            fp_name = row['PLAYER NAME']

            # we need to merge rows from the name_map and draft data frames with
            # the row from this player
            # first, let's reconcile the two columns name_map_df['pfr_id'] and draft_df['playerid']
            # not sure why Lee Sharpe has different values for some players:
            player_name_sub_df = fuzzy_get_df(player_name_df,'pff_name',fp_name)
            draft_sub_df = fuzzy_get_df(draft_df,'pfr_name',fp_name,threshold=0.8,verbose=True)


            # both of these dataframes have pfr_ids let's make sure they're the same

            



            
            
            
            #if not fp_name=='Josh Allen':
            #    continue

            position,rank = posrank_split(row['POS'])
            if not position in ['QB','RB','WR','TE']:
                continue
            team = row['TEAM']

            team_row = teams_df[teams_df['Abbreviation']==team]
            team_name = team_row['Name'].values[0]
            
            mascot = team_name.split(' ')[-1]
        
            player_id = get_id(fp_name,position,team)

            for letter in player_id:
                try:
                    assert letter in 'abcdefghijklmnopqrstuvwxyz'
                except:
                    print('%s is not a lower case letter'%letter)
                    sys.exit()
                    
            out_list = row.values.tolist()
            

            if player_name_sub_df is not None:
                if len(player_name_sub_df)>1:
                    for idx,row in player_name_sub_df.iterrows():
                        url = pfr_id_to_url(row['pfr_id'])
                        soup = get_soup(url)
                        metas = soup.findAll('meta')
                        for k in range(len(metas)):
                            meta = metas.pop(0)
                            content = meta.get('content')
                            if content is not None:
                                if content.find('Pos:')>-1:
                                    term_list = [k.upper() for k in re.split('\W+',content)]
                                    if position.upper() in term_list and mascot.upper() in term_list:
                                        
                                        player_name_sub_df = pd.DataFrame([row])
                                        break
                                
            if player_name_sub_df is None:
                name_map_list = player_name_sub_df_default
            else:
                name_map_list = player_name_sub_df.values.tolist()[0]


            if draft_sub_df is None:
                draft_list = draft_sub_df_default
            else:
                if len(draft_sub_df)>1:
                    draft_sub_df = draft_sub_df[draft_sub_df['position']==position]
                    if len(draft_sub_df)>1:
                        draft_sub_df = draft_sub_df[draft_sub_df['team']==team]
                        if len(draft_sub_df)>1:
                            sys.exit('Too many %s named %s playing for %s.'%(position,fp_name,team))
                try:
                    draft_list = draft_sub_df.values.tolist()[0]
                except:
                    print('fault:',draft_sub_df)
                    draft_list = draft_sub_df_default

            out_list = [player_id] + out_list + name_map_list + draft_list

            for c,v in zip(output_columns,out_list):
                print(c,v)
            print()
            continue
            
            assert len(out_list)==24
            player_table.append(out_list)
            

        player_df = pd.DataFrame(player_table,columns=output_columns)
        player_df.to_csv('./data/player_table.csv')
    return player_df



def build_league(league_id, year, use_cached=False):

    players_df = build_player_table()
    
    relish_id = 'league_%d_%d'%(league_id,year)

    if use_cached:
        try:
            league = relish.load(relish_id)
            logging.info('Getting data from cache file.')
            return league
        except FileNotFoundError:
            logging.info('No cached version of League object (%s) exists, rebuilding.'%relish_id)
            
    os.makedirs('.requests_cache',exist_ok=True)
    
    requests_cache.install_cache(cache_name='.requests_cache/espn_cache', backend='sqlite', expire_after=7200)

    url = "https://fantasy.espn.com/apis/v3/games/ffl/seasons/%d/segments/0/leagues/%d"%(year,league_id)
    swid_cookie = '720838F2-19CB-4C50-8AB7-41E1D10796F0'
    espn_s2_cookie = 'AECabeD%2F6A2ggL51TfzwstV8JoDHLvMAbfcbnSaJe6765VrE%2FYsS%2BHv1Zja6Hc6HFDU12buqeI61zjprVioYcZga8NMV1zlabmxIenG4anG7YclvaQH68VsyA0LqvfnSTSOM%2BoiivVS1kvA0%2BZ29cMjnq5dFOozySFshoxNLYUJGBNt7045cKBHJDI1oDcmnEdl3OGvDY8E2bP%2B4cUFIWqA4PkFv3leHeFzNKZPkrEJ%2FYET0F2oaLcr7ta7VCXZ%2Bt4rQ%2Bl8l5ylCMH8jyJOBtR7z'
    now = time.ctime(int(time.time()))
    roster_page = requests.get(url,
                               cookies={"swid": swid_cookie,
                                        "espn_s2": espn_s2_cookie},
                               params={"view": "mRoster"})
    logging.info("Got ESPN roster data; time: {0} / used cache: {1}".format(now, roster_page.from_cache))
    now = time.ctime(int(time.time()))
    team_page = requests.get(url,
                               cookies={"swid": swid_cookie,
                                        "espn_s2": espn_s2_cookie},
                               params={"view": "mTeam"})
    logging.info("Got ESPN team data; time: {0} / used cache: {1}".format(now, team_page.from_cache))


    position_dict = {1:'QB',
                     2:'RB',
                     3:'WR',
                     4:'TE',
                     5:'K',
                     16:'D/ST'}
    roster_dict = roster_page.json()
    team_dict = team_page.json()


    defense_lut = {}
    for idx,row in teams_df.iterrows():
        name = [k.strip() for k in row['Name'].split(' ')]
        city = ' '.join(name[:-1])
        mascot = name[-1]
        abbreviation = row['Abbreviation']
        key = '%s D/ST'%mascot
        value = '%s (%s)'%(city,abbreviation)
        defense_lut[key] = value

    league = League()
    for item in roster_dict['teams']:
        team_id = item['id']
        owner_series = owners_df.loc[owners_df['id'] == team_id].iloc[0]
        owner = owner_series['OWNER NAME']
        team_abbr = owner_series['ABBRV']
        team_name = owner_series['NAME']

        team = Team(team_id,team_abbr,team_name,owner)

        team_roster = item['roster']
        
        for player_data in team_roster['entries']:
            espn_row = player_data['playerPoolEntry']['player']
            name = espn_row['fullName']
            position = position_dict[espn_row['defaultPositionId']]
            team_name = teams_df[teams_df['ESPN_ID']==espn_row['proTeamId']]['Abbreviation'].values[0]
            try:
                test_id = get_id(name,position,team_name)
                players = players_df[players_df['unique_id']==test_id]
                assert len(players)==1
            except AssertionError as ae:
                players = fuzzy_get_df(players_df,'PLAYER NAME',name)
                if not players is None:
                    if len(players)>1:
                        players = players[players['POS']==position]
                    if len(players)>1:
                        players = players[players['TEAM']==team_name]
                    if not len(players)==1:
                        sys.exit('Could not locate player with name %s, team %s, position %s in player table.'%(name,team_name,position))

            # At this stage, players is either a 1 row dataframe containing the player info or None, in the case
            # of unranked players, kickers, defenses, etc.
            p = Player(name,position,team_name,players)
            team.add_player(p)

        league.append(team)

    league.teams.sort()
    #relish.save(relish_id,league)
    return league
