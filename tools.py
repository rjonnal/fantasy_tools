import numpy as np
import logging

logging.basicConfig(filename='fantasy_tools.log', level=logging.DEBUG)
logging.getLogger().addHandler(logging.StreamHandler())


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
            self.rank = data_row['RK'].values[0]
            try:
                self.tier = data_row['TIERS'].values[0]
            except:
                self.tier = 0
            self.draft_year = data_row['season'].values[0]
            self.draft_round = data_row['round'].values[0]
            self.draft_pick = data_row['pick'].values[0]
            self.pff_id = data_row['pff_id'].values[0]
            self.pfr_id = data_row['pfr_id'].values[0]
            self.pff_name = data_row['pff_name'].values[0]
            self.pff_url_name = data_row['pff_url_name'].values[0]
            self.posrank = data_row['POS'].values[0]


        # do some checks:
        try:
            int(self.draft_year)
        except:
            self.draft_year = 0
            
    def __lt__(self,other):
        return self.rank<other.rank

    def __str__(self):
        return '%s / %s / %s (%d)'%(self.name,self.posrank,self.team,self.draft_year)
    
    def __repr__(self):
        return '%s / %s'%(' '.join(self.name.split()[1:]),self.posrank)
        
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

    def get_corps(self,position):
        player_list = self.players
        out = []
        for p in player_list:
            if p.position==position:
                out.append(p)
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
        
    def get_keepers(self,verbose=True):
        if verbose:
            logging.
        positions = ['QB','RB','WR','TE']
        counts = {}
        limits = {}
        for pos in positions:
            counts[pos] = 0
        
        limits['QB'] = 2
        limits['RB'] = 2
        limits['WR'] = 2
        limits['TE'] = 1

        keepers = []
        for pos in positions:
            candidates = self.get_corps(pos)
            candidates.sort(key = lambda c: c.rank)
            while counts[pos]<limits[pos] and len(candidates)>1:
                keepers.append(candidates.pop(0))
                counts[pos]+=1
        print('keepers:',keepers)
