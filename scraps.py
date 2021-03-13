


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



