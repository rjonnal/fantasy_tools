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

logging.basicConfig(filename='fantasy_tools.log', level=logging.DEBUG)
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

def build_player_table():
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
            position,rank = posrank_split(row['POS'])
            if not position in ['QB','RB','WR','TE']:
                continue
            team = row['TEAM']

            player_id = get_id(fp_name,position,team)

            for letter in player_id:
                try:
                    assert letter in 'abcdefghijklmnopqrstuvwxyz'
                except:
                    print('%s is not a lower case letter'%letter)
                    sys.exit()
                    
            out_list = row.values.tolist()
            
            name_map_row = fuzzy_get_df(player_name_df,'pff_name',fp_name)
            if name_map_row is None:
                name_map_list = name_row_default
            else:
                name_map_list = name_map_row.values.tolist()[0]

                
            draft_row = fuzzy_get_df(draft_df,'full_name',fp_name,threshold=0.8,verbose=True)
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
            
            out_list = [player_id] + out_list + name_map_list + draft_list
            assert len(out_list)==24
            player_table.append(out_list)
            print(out_list)
            
        fp_columns = ['RK', 'TIERS', 'PLAYER NAME', 'TEAM', 'POS', 'BEST', 'WORST', 'AVG.', 'STD.DEV']
        name_map_columns = ['pff_id', 'pfr_id', 'pff_name', 'pff_url_name']
        draft_columns = ['season', 'team', 'round', 'pick', 'playerid', 'full_name', 'name', 'side', 'category', 'position']
        
        output_columns = ['unique_id']+fp_columns+name_map_columns+draft_columns

        player_df = pd.DataFrame(player_table,columns=output_columns)
        player_df.to_csv('./data/player_table.csv')
    return player_df





def build_league(league_id, year, use_cached=True):

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


    team_lut = {}
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
            player_row = player_data['playerPoolEntry']['player']
            name = player_row['fullName']
            print(player_row.keys())
            print(player_row['stats'])
            sys.exit()

            if name in defense_lut.keys():
                test_name = defense_lut[name]
            else:
                test_name = name

            try:
                series = fuzzy_get_df(adp_df,adp_name_key,search_name).iloc[0]

                try:
                    adp = series[adp_adp_key]
                except:
                    adp = series[adp_rank_key]

                rank = series[adp_rank_key]
                team_name = series[adp_team_key]


                try:
                    age = series[adp_age_key]
                except Exception as e:
                    try:
                        backup_series = fuzzy_get_df(age_df,age_name_key,test_name).iloc[0]
                        age = backup_series[age_age_key]
                    except Exception as e:
                        age = None

                position_rank = series[adp_positionalrank_key]
                position = ''
                for k in range(len(position_rank)):
                    c = position_rank[k]
                    try:
                        junk = int(c)
                        break
                    except:
                        position = position + c

            except Exception as e:
                #logging.info 'Failed to get %s from ADP table'%search_name
                pass

            try:
                series = fuzzy_get_df(age_df,age_name_key,test_name).iloc[0]
                draft_year = series[age_draft_year_key]
                sophomore = draft_year==settings.year-1
                #logging.info test_name,age_name_key,sophomore
            except Exception as e:
                sophomore = False



            try:
                series = fuzzy_get_df(keeper_biases_df,keeper_biases_name_key,test_name).iloc[0]
                bias = series[keeper_biases_bias_key]
            except Exception as e:
                bias = 0


            fpts = 0
            rfpts = -100
            try:

                try:
                    search_name = projections_name_replacements[test_name]
                except KeyError:
                    search_name = test_name


                series = fuzzy_get_df(projections_df,'playerName',search_name)
                if series is None:
                    #logging.info test_name
                    pass
                series = series.iloc[0]
                fpts = series['fantasyPoints']
                rfpts = series['relativeFantasyPoints']
            except Exception as e:
                #logging.info 'Failed to get %s from PROJ table'%search_name
                pass

            p = Player(name,position,rank,adp,sophomore,fpts,rfpts=rfpts,age=age,team=team_name,keeper_value=adp+bias)
            team.add_player(p)

        league.append(team)
        #logging.info team,'%0.1f'%np.mean([p.adp for p in team.get_keepers()])


    league.teams.sort()

        
        
if __name__=='__main__':
    get_league(2020,172550)

if False:

    pickle_filename = settings.pickle_filename
    adp_name_key = 'Overall'
    adp_adp_key = 'ADP'
    adp_age_key = 'Age'
    adp_rank_key = 'Rank'
    adp_team_key = 'Team'
    adp_positionalrank_key = 'Pos'

    age_age_key = 'age'
    age_draft_year_key = 'draft_year'
    age_ecr = 'ecr_1qb'
    age_ecr_pos = 'ecr_pos'
    age_mkt_value = 'value_1qb'
    age_name_key = 'player'

    owners_df = pd.read_csv('data/owners.csv')
    adp_df = pd.read_csv('data/adp/adp.csv')
    keeper_biases_df = pd.read_csv('./data/keeper_biases.csv')
    keeper_biases_name_key = 'name'
    keeper_biases_bias_key = 'bias'

    # download this, if possible, and updated
    # https://docs.google.com/spreadsheets/d/19YvN6ac_2VEsdumylgsBd4hi_YTmeBUIi6s0hmSV3RA/edit?usp=sharing

    age_df = pd.read_csv('data/player_age_mkt_value.csv')

    projections_df = pd.read_csv('data/projections/pff_projections_with_value.csv')

    try:
        infile = open(pickle_filename,'rb')
        league = pickle.load(infile)
        infile.close()
    except Exception as e:
        #logging.info e

        requests_cache.install_cache(cache_name='espn_cache', backend='sqlite', expire_after=7200)

        league_id = 172550
        year = settings.year
        url = "https://fantasy.espn.com/apis/v3/games/ffl/seasons/%d/segments/0/leagues/%d"%(year,league_id)

        swid_cookie = '720838F2-19CB-4C50-8AB7-41E1D10796F0'
        espn_s2_cookie = 'AECabeD%2F6A2ggL51TfzwstV8JoDHLvMAbfcbnSaJe6765VrE%2FYsS%2BHv1Zja6Hc6HFDU12buqeI61zjprVioYcZga8NMV1zlabmxIenG4anG7YclvaQH68VsyA0LqvfnSTSOM%2BoiivVS1kvA0%2BZ29cMjnq5dFOozySFshoxNLYUJGBNt7045cKBHJDI1oDcmnEdl3OGvDY8E2bP%2B4cUFIWqA4PkFv3leHeFzNKZPkrEJ%2FYET0F2oaLcr7ta7VCXZ%2Bt4rQ%2Bl8l5ylCMH8jyJOBtR7z'
        now = time.ctime(int(time.time()))
        roster_page = requests.get(url,
                                   cookies={"swid": swid_cookie,
                                            "espn_s2": espn_s2_cookie},
                                   params={"view": "mRoster"})
        #logging.info "Time: {0} / Used Cache: {1}".format(now, roster_page.from_cache)
        now = time.ctime(int(time.time()))
        team_page = requests.get(url,
                                   cookies={"swid": swid_cookie,
                                            "espn_s2": espn_s2_cookie},
                                   params={"view": "mTeam"})
        #print "Time: {0} / Used Cache: {1}".format(now, team_page.from_cache)


        # possible views are:
        #     mMatchup
        #     mTeam
        #     mBoxscore
        #     mRoster
        #     mSettings
        #     kona_player_info
        #     player_wl
        #     mSchedule

        position_dict = {1:'QB',
                         2:'RB',
                         3:'WR',
                         4:'TE',
                         5:'K',
                         16:'D/ST'}
        roster_dict = roster_page.json()
        team_dict = team_page.json()


        team_lut = {}
        teams_df = pd.read_csv('data/nfl_teams.csv')
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
                player_row = player_data['playerPoolEntry']['player']
                name = player_row['fullName']


                if name in defense_lut.keys():
                    test_name = defense_lut[name]
                else:
                    test_name = name

                adp = 500.0
                rank = 500.0
                age = None
                position = None
                sophomore = False
                team_name = None
                try:

                    try:
                        search_name = adp_name_replacements[test_name]
                    except KeyError:
                        search_name = test_name

                    #print test_name,'->',search_name
                    series = fuzzy_get_df(adp_df,adp_name_key,search_name).iloc[0]

                    try:
                        adp = series[adp_adp_key]
                    except:
                        adp = series[adp_rank_key]

                    rank = series[adp_rank_key]
                    team_name = series[adp_team_key]


                    try:
                        age = series[adp_age_key]
                    except Exception as e:
                        try:
                            backup_series = fuzzy_get_df(age_df,age_name_key,test_name).iloc[0]
                            age = backup_series[age_age_key]
                        except Exception as e:
                            age = None

                    position_rank = series[adp_positionalrank_key]
                    position = ''
                    for k in range(len(position_rank)):
                        c = position_rank[k]
                        try:
                            junk = int(c)
                            break
                        except:
                            position = position + c

                except Exception as e:
                    #print 'Failed to get %s from ADP table'%search_name
                    pass

                try:
                    series = fuzzy_get_df(age_df,age_name_key,test_name).iloc[0]
                    draft_year = series[age_draft_year_key]
                    sophomore = draft_year==settings.year-1
                    #print test_name,age_name_key,sophomore
                except Exception as e:
                    sophomore = False



                try:
                    series = fuzzy_get_df(keeper_biases_df,keeper_biases_name_key,test_name).iloc[0]
                    bias = series[keeper_biases_bias_key]
                except Exception as e:
                    bias = 0


                fpts = 0
                rfpts = -100
                try:

                    try:
                        search_name = projections_name_replacements[test_name]
                    except KeyError:
                        search_name = test_name


                    series = fuzzy_get_df(projections_df,'playerName',search_name)
                    if series is None:
                        #print test_name
                        pass
                    series = series.iloc[0]
                    fpts = series['fantasyPoints']
                    rfpts = series['relativeFantasyPoints']
                except Exception as e:
                    #print 'Failed to get %s from PROJ table'%search_name
                    pass

                p = Player(name,position,rank,adp,sophomore,fpts,rfpts=rfpts,age=age,team=team_name,keeper_value=adp+bias)
                team.add_player(p)

            league.append(team)
            #print team,'%0.1f'%np.mean([p.adp for p in team.get_keepers()])


        league.teams.sort()

        outfile = open(pickle_filename,'wb')
        pickle.dump(league,outfile)
        outfile.close()


    if __name__=='__main__':

        ##print_knk(league)
        all_keepers = league.get_all_keepers()
        all_keeper_names = [k.name for k in all_keepers]
        available_players = []
        replacements = {'D.J. Chark':'DJ Chark Jr.'}
        for index,in_row in adp_df.iterrows():
            name = in_row[adp_name_key]
            if name in replacements.keys():
                name = replacements[name]
            keeper = fuzzy_in(all_keeper_names,name)
            if not keeper:
                available_players.append(in_row)

        available_df = pd.DataFrame(available_players)

        n_rows = len(draft_order_df.index)
        available_df = available_df.head(n_rows)

        columns = ['pick','owner','rank','name','pos','team','age','pts','rpts']
        df_list = []
        replacements = {'D.J. Chark':'D.J. Chark Jr.'}
        for k in range(n_rows):
            player_series = available_df.iloc[k]
            draft_series = draft_order_df.iloc[k]

            pick = draft_series['pick']
            owner = draft_series['owner']
            name = player_series[adp_name_key]
            rank = player_series[adp_rank_key]
            try:
                age = player_series[adp_age_key]
            except Exception as e:
                try:
                    backup_series = fuzzy_get_df(age_df,age_name_key,test_name).iloc[0]
                    age = backup_series[age_age_key]
                except Exception as e:
                    age = 99

            nflteam = player_series[adp_team_key]
            pos = player_series[adp_positionalrank_key]
            if name in replacements.keys():
                pname = replacements[name]
            else:
                pname = name

            pts = 0.0
            rpts = -200.0
            try:
                pts = fuzzy_get_df(projections_df,'playerName',pname).iloc[0]['fantasyPoints']
                rpts = fuzzy_get_df(projections_df,'playerName',pname).iloc[0]['relativeFantasyPoints']
            except Exception as e:
                pass

            out_series = [pick,owner,rank,name,pos,nflteam,age,pts,rpts]
            df_list.append(out_series)

        output_df = pd.DataFrame(df_list,columns=columns)
        output_df.to_csv('cheatsheet.csv')
        #print_knk(league)
