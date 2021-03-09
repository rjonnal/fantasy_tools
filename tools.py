import numpy as np
import logging

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
                
    
    def fix_roster(self,roster,rookie_year):

        out = [p for p in roster]

        def remove_worst(position,plist):
            wild = position=='*'
            poslist = [p for p in plist if (p.position==position or wild)]
            nposlist = [p for p in plist if ((not p.position==position) and (not wild))]
            poslist.sort()
            poslist.pop(-1)
            return sorted(poslist+nposlist)
        
        while self.npos('QB',out)>3:
            out = remove_worst('QB',out)

        if self.npos('QB',out)==3 and not self.has_rookie(self.get_corps('QB',out), rookie_year):
            out = remove_worst('QB',out)

        while self.npos('RB',out)>3:
            out = remove_worst('RB',out)

        if self.npos('RB',out)==3 and not self.has_rookie(self.get_corps('RB',out), rookie_year):
            out = remove_worst('RB',out)

        while self.npos('WR',out)>3:
            out = remove_worst('WR',out)

        if self.npos('WR',out)==3 and not self.has_rookie(self.get_corps('WR',out), rookie_year):
            out = remove_worst('WR',out)

        while self.npos('TE',out)>2:
            out = remove_worst('TE',out)

        if self.npos('TE',out)==2 and not self.has_rookie(self.get_corps('TE',out), rookie_year):
            out = remove_worst('TE',out)

        while len(out)>9:
            out = remove_worst('*',out)
            
        return out

    
    def get_keepers0(self,rookie_year,verbose=False):
        self.players.sort()

        players = [p for p in self.players]
        
        if verbose:
            logging.info('get_keepers run by %s'%self)
            
        positions = ['QB','RB','WR','TE']
        counts = {}
        limits = {}
        for pos in positions:
            counts[pos] = 0
        
        limits['QB'] = 2
        limits['RB'] = 3
        limits['WR'] = 3
        limits['TE'] = 2

        keepers = []

        # first let's add our highest rank rookie
        rookies = [p for p in self.players if p.draft_year==rookie_year]
        try:
            rookies.sort()
            keepers.append(rookies[0])
            players.remove(rookies[0])
            counts[rookies[0].position]+=1
            rookies.pop(0)
            total_limit = 9
        except:
            # no rookies!
            total_limit = 8
        
        for pos in positions:
            if verbose:
                logging.info('Getting initial %ss.'%pos)
            candidates = self.get_corps(pos,players)
            candidates.sort()#key = lambda c: c.rank)
            if verbose:
                logging.info('%s candidates:'%pos)
                logging.info(candidates)
            while counts[pos]<limits[pos] and len(candidates)>=1:
                temp = candidates.pop(0)
                players.remove(temp)
                if verbose:
                    logging.info('Adding %s to keepers.'%temp)
                keepers.append(temp)
                counts[pos]+=1

        #keepers = self.fix_roster(keepers,rookie_year)

        while len(keepers)>total_limit:
            rk = [p for p in keepers if p.draft_year==rookie_year]
            vk = [p for p in keepers if not p in rk]
            rk.sort()
            vk.sort()
            keepers.remove(vk[-1])
            
        if verbose:
            logging.info('Keeping (%d):'%len(keepers))
            logging.info(keepers)
            logging.info('Dropping (%d):'%len(players))
            logging.info(players)

        if verbose:
            logging.info('')

        return keepers



    def get_keepers(self,rookie_year,verbose=False):

        # It's simple. You have to keep 9 playrs. You can keep up to 2 QBs, 5 WR/RBs,
        # 1 TE and as many place kickers and defenses you want. However, if a player
        # is a rookie, you can keep that player in excess of the limits set forth above
        # except you can never under any circumstance keep more than 3 RBs or more than 3 WRs!

        # 1. Set up initial limits 2 QB, 2 WR, 2 RB, 1 TE, and fill them by rank
        # 2. Take next highest rank and:
        #    a. If rookie, add to his slot, and go to step 3.
        #    b. If he's a veteran and his slot contains a rookie, add him to his slot, and go to step 3.
        #    c. Repeat 2
        # 3. If keepers contain 2 RBs and 2 WRs, add highest RB/WR and quit
        #    Otherwise, if keepers contain 3 RBs, add highest WR and quit
        #    Otherwise, if keepers contain 3 WRs, add highest RB and quit

        self.players.sort()

        players = [p for p in self.players]
        
        if verbose:
            logging.info('get_keepers run by %s'%self)
            
        positions = ['QB','RB','WR','TE']
        counts = {}
        initial_limits = {}
        
        for pos in positions:
            counts[pos] = 0
        
        initial_limits['QB'] = 2
        initial_limits['RB'] = 2
        initial_limits['WR'] = 2
        initial_limits['TE'] = 1

        
        keepers = {}
        for pos in positions:
            keepers[pos] = sorted(self.get_corps(pos))[:initial_limits[pos]]
            for k in keepers[pos]:
                players.remove(k)

        if verbose:
            logging.info('Step 1')
            logging.info(keepers)
            logging.info(players)
            logging.info()
        
                
        players.sort()

        for idx,p in enumerate(players):
            if p.draft_year==rookie_year:
                keepers[p.position].append(p)
                players.remove(p)
                break
            elif any([a.draft_year==rookie_year for a in keepers[p.position]]):
                keepers[p.position].append(p)
                players.remove(p)
                break

        if verbose:
            logging.info('Step 2')
            logging.info(keepers)
            logging.info(players)
            logging.info()

        wrrbs = [p for p in players if p.position in ['RB','WR']]
        rbs = [p for p in players if p.position in ['RB']]
        wrs = [p for p in players if p.position in ['WR']]
        wrrbs.sort()
        rbs.sort()
        wrs.sort()
        
        if len(keepers['WR'])==2 and len(keepers['RB'])==2:
            p = wrrbs[0]
            keepers[p.position].append(p)
            players.remove(p)
        elif len(keepers['WR'])==3 and any([a.draft_year==rookie_year for a in keepers['WR']]):
            p = rbs[0]
            keepers[p.position].append(p)
            players.remove(p)
        elif len(keepers['RB'])==3 and any([a.draft_year==rookie_year for a in keepers['RB']]):
            p = wrs[0]
            keepers[p.position].append(p)
            players.remove(p)

        if verbose:
            logging.info('Step 3')
            logging.info(keepers)
            logging.info(players)
            logging.info()
            logging.info()
        
        out = []
        for pos in positions:
            out = out + sorted(keepers[pos])
        return out
    
