import relish
import logging
import requests
import requests_cache
import sys,os,glob,time
import pandas as pd
import importlib.resources as pkg_resources
from . import data as league_data
from .tools import League,Player,Team,posrank_split,players_df_to_players
from nfldata import data as sharpe_data
from .matcher import fuzzy_get_df
from .pfr_tools import check_position_mascot
from .scraper import get_soup,get_pfr_id_from_google
import re
import numpy as np
from .pfr_id_explicit import dictionary as pfr_id_dict
from .entry_years import dictionary as entry_years_dictionary

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


position_color_dict = {'QB':'b','RB':'g','WR':'r','TE':'y','D/ST':'k','K':'k'}

class MultipleWinnerException(Exception):
    pass
def poll_list0(L):
    counts = []
    for item1 in L:
        count = 0
        for item2 in L:
            count+=item1==item2
        counts.append(count)
    try:
        assert not all([c==1 for c in counts])
    except AssertionError:
        raise MultipleWinnerException
    return L[np.argmax(counts)]
        
def poll_list(L):
    counts = {}
    for k in L:
        if k in counts.keys():
            counts[k]+=1
        else:
            counts[k]=1

    print(counts)
    keys = [k for k in counts.keys()]
    vals = [counts[k] for k in keys]
    max_count = np.max(vals)
    print(max_count)
    winners = []
    for idx,val in enumerate(vals):
        if val==max_count:
            winners.append(keys[idx])
    return winners
    
def get_id(name,position,team):
    name = name.replace(' ','')
    name = name.replace('.','')
    name = name.replace(',','')
    name = name.replace('-','')
    name = name.replace("'","")
    out = name.lower().strip()+position.lower().strip()+team.lower().strip()
    return out

def build_player_table_initial(rankings_file):
    rankings_file_stat = os.stat(rankings_file)
    rankings_age_days = (time.time()-rankings_file_stat.st_mtime)/(24.0*3600.0)
    logging.info('Rankings page is %0.1f days old.'%rankings_age_days)
    max_age_days = 30
    if rankings_age_days>max_age_days:
        sys.exit('Rankings old! Get some new ones at https://www.fantasypros.com/nfl/rankings/half-point-ppr-cheatsheets.php and put them in the local data folder.')
    rankings_df = pd.read_csv(rankings_file)

    # This function builds a big table of player data out of Lee Sharpe's pff_pfr_map and FP's rankings;
    # it uses FP's rankings to identify the players of interest (skipping defense and kicker),
    # and then Sharpe's table to connect with PFF and PFR IDs

    try:
        player_df = pd.read_csv('./data/player_table_initial.csv')
    except Exception:
        player_table = []
        # Here we want to add the following columns to this row:
        # pfr_id, which is player_name_df['pfr_id'] and draft_df['playerid'], and
        #     which we will also google to verify
        # draft_year,draft_pick,draft_round from draft_df['season','round','pick']

        # new columns:
        col_pfr_id = []
        col_draft_year = []
        col_draft_round = []
        col_draft_pick = []
        col_unique_id = []
        
        player_df_list = []

        n_rows = len(rankings_df)
        for idx,row in rankings_df.iterrows():
            fp_name = row['PLAYER NAME']
            print('%04d of %04d: %s'%(idx+1,n_rows,fp_name))
            position,rank = posrank_split(row['POS'])
            if not position in ['QB','RB','WR','TE']:
                continue


            player_df_list.append(row)
            
            team = row['TEAM']
            team_row = teams_df[teams_df['Abbreviation']==team]
            team_name = team_row['Name'].values[0]
            mascot = team_name.split(' ')[-1]
        
            unique_id = get_id(fp_name,position,team)
            col_unique_id.append(unique_id)
            
            for letter in unique_id:
                try:
                    assert letter in 'abcdefghijklmnopqrstuvwxyz'
                except:
                    print('%s is not a lower case letter'%letter)
                    sys.exit()
                    
            pfr_id_relish = 'pfr_id_%s'%unique_id

            player_name_sub_df = fuzzy_get_df(player_name_df,'pff_name',fp_name,return_empty=True)
            draft_sub_df = fuzzy_get_df(draft_df,'pfr_name',fp_name,threshold=0.8,verbose=False,return_empty=True)

            try:
                pfr_id = relish.load(pfr_id_relish)
            except:
                verbose = True
                if verbose:
                    print('Determining pfr_id for player %s.'%fp_name)

                pfr_id_candidates = []
                pfr_id_candidates.append(get_pfr_id_from_google(fp_name))

                if len(player_name_sub_df)>=1:
                    pfr_id_candidates+=player_name_sub_df['pfr_id'].values.tolist()

                if len(draft_sub_df)>=1:
                    pfr_id_candidates+=draft_sub_df['pfr_id'].values.tolist()

                if verbose:
                    print('candidates from google, player_name_sub_df, draft_sub_df:')
                    print('\t',pfr_id_candidates)

                pfr_id_candidates = [p for p in pfr_id_candidates if type(p)==str]
                pfr_id_candidates = [p for p in pfr_id_candidates if len(p)>4]

                if len(pfr_id_candidates)>0:
                    if verbose:
                        print('candidates after cleanup')
                        print(pfr_id_candidates)

                    winners = poll_list(pfr_id_candidates)
                    if verbose:
                        print('candidates after polling')
                        print(winners)

                    for w in winners:
                        if check_position_mascot(w,position,mascot):
                            pfr_id = w
                            break

                    if verbose:
                        print('winning candidate for %s is %s'%(fp_name,pfr_id))

                    if pfr_id=='':
                        if verbose:
                            print('winning candidate was empty string')

                        def pair_to_pfr(pair):
                            return pair[1][:4]+pair[0][:2]

                        def fix(s):
                            out = []
                            for a in s:
                                test = a.replace("'",'').replace(',','').replace('-','')
                                if a==test:
                                    out.append(a)
                                else:
                                    out = out + [a,test]
                            return out

                        name_parts = fp_name.split()
                        name_parts = fix(name_parts)
                        np = len(name_parts)
                        for k1 in range(np):
                            for k2 in range(k1+1,np):
                                try:
                                    test = pair_to_pfr([name_parts[k1],name_parts[k2]])
                                    for n in range(10):
                                        testn = test + '%02d'%n
                                        if verbose:
                                            print('Brute force checking %s.'%testn)
                                        if check_position_mascot(testn,position,mascot,verbose=True):
                                            print('%s checks out. Using it unless dictionary specifies otherwise.'%testn)
                                            pfr_id = testn
                                            break
                                except Exception as e:
                                    print(e)
                else:
                    pfr_id = ''

                # last, last ditch:
                try:
                    pfr_id = pfr_id_dict[fp_name]
                    if verbose:
                        print('%s specified in dictionary. Using it.'%pfr_id)
                except:
                    pass

                if pfr_id=='':
                    print(fp_name,'no pfr_id')

                relish.save(pfr_id_relish,pfr_id)

            col_pfr_id.append(pfr_id)

            try:
                y,r,p = entry_years_dictionary[unique_id]
                col_draft_year.append(y)
                col_draft_round.append(r)
                col_draft_pick.append(p)
            except KeyError:
                if pfr_id=='':
                    col_draft_year.append(2021)
                    col_draft_round.append(0)
                    col_draft_pick.append(0)
                else:
                    if len(draft_sub_df)>1:
                        draft_sub_df = draft_sub_df[draft_sub_df['pfr_id']==pfr_id]
                    if len(draft_sub_df)==0:
                        col_draft_year.append(0)
                        col_draft_round.append(0)
                        col_draft_pick.append(0)
                    elif len(draft_sub_df)==1:
                        col_draft_year.append(draft_sub_df['season'].values[0])
                        col_draft_round.append(draft_sub_df['round'].values[0])
                        col_draft_pick.append(draft_sub_df['pick'].values[0])

        player_df = pd.DataFrame(player_df_list)
        player_df['pfr_id'] = col_pfr_id
        player_df['draft_year'] = col_draft_year
        player_df['draft_round'] = col_draft_round
        player_df['draft_pick'] = col_draft_pick
        player_df['unique_id'] = col_unique_id
        
        player_df.to_csv('./data/player_table_initial.csv')
    return player_df


def build_player_table(player_table_initial_filename,fp_pfr_lookup_filename,player_table_filename,rookie_year=0):
    player_df = pd.read_csv(player_table_initial_filename)
    lookup = pd.read_csv(fp_pfr_lookup_filename)
    out = []
    outcols = player_df.columns
    for idx,row in player_df.iterrows():
        name = row['PLAYER NAME']
        temp = lookup[lookup['player_name']==name]
        if len(temp)==1:
            row['pfr_id'] = temp['pfr_id'].values[0]
            test = temp['pfr_id'].values[0]
            if not type(test)==str:
                # assume rookie
                row['pfr_id'] = ''
                row['draft_year'] = rookie_year
                row['draft_round'] = 0
                row['draft_pick'] = 0
        else:
            logging.error('Fatal error--multiple matches in pfr lookup file.')
            for eidx,erow in temp.iterrows():
                logging.error(erow.tolist())
        out.append(row)
    outdf = pd.DataFrame(out,columns=outcols)
    outdf.to_csv(player_table_filename)

def fp_pfr_lookup_helper(player_table_initial_filename,html_output_filename,csv_output_filename):
    players_df = pd.read_csv(player_table_initial_filename)
    players = players_df_to_players(players_df)

    with open(html_output_filename,'w') as fid:
        fid.write("<html><head></head><body>")
        for p in players:
            try:
                url = pfr_id_to_url(p.pfr_id)
                urltext = url
            except:
                url = ''
                urltext = 'no url'

            fid.write("<p>%s / %s / %s:<a href='%s'>%s</a></p>"%(p.name,p.position,p.team,url,urltext))
        fid.write("</body></html>")

    with open(csv_output_filename,'w') as fid:
        fid.write('player_name,pfr_id\n')
        for p in players:
            fid.write("%s,%s\n"%(p.name,p.pfr_id))

    logging.info("Wrote helper files to %s and %s."%(html_output_filename,csv_output_filename))


def build_league(league_id, year, player_table_filename, use_cached=False):

    players_df = pd.read_csv(player_table_filename)
    relish_id = 'league_%d_%d'%(league_id,year)

    if use_cached:
        try:
            league = relish.load(relish_id)
            logging.info('Getting data from cache file.')
            return league
        except FileNotFoundError:
            logging.info('No cached version of League object (%s) exists, rebuilding.'%relish_id)
            
    os.makedirs('.requests_cache',exist_ok=True)
    
    requests_cache.install_cache(cache_name='.requests_cache/espn_cache', backend='sqlite', expire_after=72000000)

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
    relish.save(relish_id,league)
    return league
