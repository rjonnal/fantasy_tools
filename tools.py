import numpy as np
import logging
import relish
import itertools

try:
    keeper_dictionary = relish.load('keeper_dictionary')
except:
    keeper_dictionary = {}
    relish.save('keeper_dictionary',keeper_dictionary)

class League:
    
    def __init__(self):
        self.teams = []

    def get_all_keepers(self):
        out = []
        for t in self.teams:
            out = out + t.get_keepers()
        return out

    def __len__(self):
        return len(self.teams)
 
    def append(self, item):
        self.teams.append(item)
 
    def remove(self, item):
        self.teams.remove(item)
 
    def __getitem__(self, sliced):
        return self.teams[sliced]

        
class Player:
    
    def __init__(self,name,position,team,data_row=None):
        self.name = name
        self.position = position
        self.team = team
        if data_row is None:
            self.rank = 1000
            self.tier = 1000
            self.draft_year = 0
            self.draft_round = 0
            self.draft_pick = 0
            self.pff_id = ''
            self.pfr_id = ''
            self.pff_name = ''
            self.pff_url_name = ''
            self.posrank = ''
            
        else:
            # Unnamed: 0  RK  TIERS PLAYER NAME TEAM   POS  BEST  WORST  AVG.  STD.DEV    pfr_id  draft_year  draft_round  draft_pick      unique_id
            # 35          35  36      5  Mike Evans   TB  WR15    25     49  36.6      4.9  EvanMi00        2014            1           7  mikeevanswrtb
            self.rank = data_row['RK'].values[0]
            try:
                self.tier = data_row['TIERS'].values[0]
            except:
                self.tier = 0
            self.draft_year = data_row['draft_year'].values[0]
            self.draft_round = data_row['draft_round'].values[0]
            self.draft_pick = data_row['draft_pick'].values[0]
            self.pfr_id = data_row['pfr_id'].values[0]
            self.posrank = data_row['POS'].values[0]


        # do some checks:
        try:
            int(self.draft_year)
        except:
            self.draft_year = 0
            
        self.unique_id = self.get_unique_id()
            
    def get_unique_id(self):
        
        def cleanup(s):
            for item in [' ','-',"'",',','.']:
                s = s.replace(item,'')
            return s
        
        return '-'.join([cleanup(item.lower().strip()) for item in [self.name,self.position,self.team]])
            
    def __lt__(self,other):
        return self.rank<other.rank

    def __str__(self):
        return '%s / %s / %s (%d)'%(self.name,self.posrank,self.team,self.draft_year)
    
    def __repr__(self):
        if self.draft_year==2020:
            rstr = '*'
        else:
            rstr=''
        return '%s-%s%s'%(' '.join(self.name.split()[1:]),self.posrank,rstr)
        
class Team:

    def __init__(self,team_id,team_abbr,team_name,owner):
        self.team_id = team_id
        self.team_abbr = team_abbr
        self.team_name = team_name
        self.owner = owner
        self.players = []


    def __lt__(self,other):
        return np.sum([p.rank for p in sorted(self.players)[:9]])<np.sum([p.rank for p in sorted(other.players)[:9]])

    def __len__(self):
        return len(self.players)
 
    def append(self, item):
        self.players.append(item)
 
    def remove(self, item):
        self.players.remove(item)
 
    def __getitem__(self, sliced):
        return self.players[sliced]
        
    def add_player(self,player):
        self.players.append(player)
        
    def __str__(self):
        return self.team_name

    def __repr__(self):
        return self.team_name

    def print_players(self):
        for p in self.players:
            print(p)

    def get_corps(self,position,player_list=None):
        if player_list is None:
            player_list = self.players
        out = []
        for p in player_list:
            if p.position==position:
                out.append(p)
        out.sort()
        return out

    
    def swap_in(self,player_list,player):
        # remove from player_list the worst
        # player with player's position and
        # insert player
        pdict = {}
        player_list.sort()
        for p in player_list:
            pos = p.position
            #print pos
            if pos in list(pdict.keys()):
                pdict[pos].append(p)
            else:
                pdict[pos] = [p]
        pdict[player.position].pop(-1)
        pdict[player.position].append(player)
        out = []
        for k in list(pdict.keys()):
            out = out + pdict[k]
        out.sort()
        return out
            
    def sort_by_position(self,player_list=None):
        if player_list is None:
            player_list = self.players
        qbs = self.get_corps('QB',player_list)
        tes = self.get_corps('TE',player_list)
        rbs = self.get_corps('RB',player_list)
        wrs = self.get_corps('WR',player_list)
        dsts = self.get_corps('DST',player_list)
        ks = self.get_corps('K',player_list)
        return qbs+rbs+wrs+tes+dsts+ks


    def npos(self,pos,player_list=None):
        if player_list is None:
            player_list = self.players
        return len(self.get_corps(pos,player_list=player_list))

    def has_rookie(self,plist,rookie_year):
        return any([p.draft_year==rookie_year for p in plist])
                
    def get_keepers(self,rookie_year,verbose=False):
        players = [p for p in self.players if p.position in ['QB','RB','WR','TE']]
        key = '-'.join(sorted([p.unique_id for p in players]))
        try:
            unique_ids = keeper_dictionary[key]
            out = [p for p in players if p.unique_id in unique_ids]
        except KeyError as e:
            perms = itertools.combinations(players,9)
            candidates = []

            def npos(pos,player_list):
                return len(self.get_corps(pos,player_list=player_list))

            def has_rookie(plist,pos=None):
                if pos is None:
                    return any([p.draft_year==rookie_year for p in plist])
                else:
                    return any([p.draft_year==rookie_year for p in plist if p.position in pos])

            def valid(k):
                positions = ['QB','RB','WR','TE']
                try:

                    assert npos('QB',k)<3 or (npos('QB',k)==3 and has_rookie(k,['QB']))

                    assert npos('RB',k)<=3

                    assert npos('WR',k)<=3

                    assert (npos('RB',k)+npos('WR',k)<6) or (npos('RB',k)+npos('WR',k)==6 and (has_rookie(k,['RB','WR'])))

                    assert (npos('TE',k)<2) or (npos('TE',k)==2 and has_rookie(k,['TE']))
                except AssertionError:
                    return False
                return True


            def score(k):
                return np.mean([p.rank for p in k])


            candidates = []
            scores = []

            for perm in perms:
                perm = list(perm)
                out = [p for p in perm if p.position=='QB']+[p for p in perm if p.position=='RB']+[p for p in perm if p.position=='WR']+[p for p in perm if p.position=='TE']
                if valid(out):
                    candidates.append(out)
                    scores.append(score(out))

            minscore = np.argmin(scores)
            out = candidates[minscore]
            keeper_dictionary[key] = [p.unique_id for p in out]

            relish.save('keeper_dictionary',keeper_dictionary)
            
        out = self.sort_by_position(out)
        return out
