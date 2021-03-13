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



