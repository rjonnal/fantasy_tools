import numpy as np

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
    
    def __init__(self,name,position):
        
        self.name = name
        self.position = position
        
    def __lt__(self,other):
        # need a dummy comparator until rank is implemented
        return self.name<other.name

        
class Team:

    def __init__(self,team_id,team_abbr,team_name,owner):
        self.team_id = team_id
        self.team_abbr = team_abbr
        self.team_name = team_name
        self.owner = owner
        self.players = []

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
        
