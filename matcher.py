from difflib import SequenceMatcher
import numpy as np
import sys,os
from matplotlib import pyplot as plt

def similarity(a, b):
    try:
        return SequenceMatcher(None, a, b).ratio()
    except Exception as e:
        return 0.0
    
def fuzzy_get_df(df,column,string,threshold=.85,verbose=False):
    # return row of df where its column matches (or near matches) string
    match = df[df[column]==string]
    if len(match)>=1: # a perfect match
        return match
    elif len(match)==0:
        scores = []
        for candidate in df[column]:
            try:
                scores.append(similarity(candidate,string))
            except Exception as e:
                if verbose:
                    print('Cannot compute similarity between %s and %s. Using 0.0.'%(candidate,string))
                scores.append(0.0)
        if np.max(scores)>threshold:
            return df[df[column]==df[column][np.argmax(scores)]]
        else:
            if verbose:
                print('No valid entry for %s.'%string)
            return None

def fuzzy_in(L,string,threshold=.8,verbose=False):
    # return true if string is fuzzy member of L

    found = False
    try:
        match = L.index(string)
        if verbose:
            print('Found exact match for %s at index %d'%(string,match))
        return True
    except Exception as e:
        scores = []
        for candidate in L:
            scores.append(similarity(candidate,string))
        if np.max(scores)>threshold:
            match = np.argmax(scores)
            winner = L[match]
            if verbose:
                print('Found fuzzy match %s for %s at index %d (%0.2f)'%(winner,string,match,scores[match]))
            return True
        else:
            if verbose:
                print('No match for %s. Closest was %s at index %d (%0.2f)'%(string,winner,match,scores[match]))
            return False


def get_matching_name(name,pos,name_list,position_list,match_threshold=0.9,verbose=False,debug=False):
    # given a name, position, and name and position lists,
    # return the item from the name list corresponding to the inputs
    name = name.lower().strip()
    pos = pos.lower().strip()
    sims = []
    for kn,kp in zip(name_list,position_list):
        if not (type(kn)==str and type(kp)==str):
            continue
        knl = kn.lower().strip()
        kpl = kp.lower().strip()
        if debug:
            print(name,pos,knl,kpl)
            sys.exit()
        if knl==name and kpl==pos:
            if verbose:
                print('%s,%s matches %s,%s (exact)'%(name,pos,kn,kp))
            return kn
        if not len(kn.split())==len(name.split()):
            n_terms = max(len(kn.split()),len(name.split()))
            if all([t1==t2 for t1,t2 in zip(knl.split()[:n_terms],name.split()[:n_terms])]) and kpl==pos:
                if verbose:
                    print('%s,%s matches %s,%s (truncation)'%(name,pos,kn,kp))
                return kn

        sims.append(similarity(knl,name))

    max_idx = np.argmax(sims)
    max_sim = sims[max_idx]
    if max_sim>=match_threshold and pos==position_list[max_idx].lower():
        if verbose:
            print('%s,%s matches %s,%s (statistical)'%(name,pos,name_list[max_idx],position_list[max_idx]))
        return name_list[max_idx]
    else:
        if verbose:
            print('%s,%s is not found'%(name,pos))
        return None

        
class Matcher:

    def __init__(self,whitelist_filename='./mwl.txt'):
        self.whitelist_filename = whitelist_filename
        try:
            self.whitelist = self.file_to_list(self.whitelist_filename,min_items=2)
        except Exception as e:
            self.whitelist = []

    def get_dictionary(self,dataframe,name,position,name_header='name',position_header='pos',threshold=0.85,inquire=True,preserve_case=False,fmt_str='%s|%s',verbose=False):
        series = self.get_series(dataframe,name,position,name_header,position_header,threshold,inquire,preserve_case,fmt_str)
        out = {}
        if not series is None:
            for key in series.columns:
                out[key]=series[key].item()
        return out
            
    def get_series(self,dataframe,name,position,name_header='name',position_header='pos',threshold=0.85,inquire=True,preserve_case=False,fmt_str='%s|%s',verbose=False):
        nlist = dataframe[name_header].tolist()
        plist = dataframe[position_header].tolist()
        nwinner = get_matching_name(name,position,nlist,plist,verbose=verbose,match_threshold=threshold)
        if nwinner is None:
            return None
        pwinner = plist[nlist.index(nwinner)]
        prospect = dataframe[(dataframe[name_header]==nwinner)
                             & (dataframe[position_header]==pwinner)]
        return prospect
        
    def get_series_old(self,dataframe,name,position,name_header='name',position_header='pos',threshold=0.85,inquire=True,preserve_case=False,fmt_str='%s|%s'):
        
        nlist = dataframe[name_header].tolist()
        plist = dataframe[position_header].tolist()
        
        keys = [fmt_str%(n,p) for n,p in zip(nlist,plist)]
        test = fmt_str%(name,position)
        if not preserve_case:
            keys = [k.lower() for k in keys]
            test = test.lower()
        sims = []
        if test in keys:
            pwinner = plist[keys.index(test)]
            nwinner = nlist[keys.index(test)]
            score = 1.0
        else:
            sims = []
            for k in keys:
                sims.append(similarity(test,k))
            pwinner = plist[np.argmax(sims)]
            nwinner = nlist[np.argmax(sims)]
            score = np.max(sims)
        prospect = dataframe[(dataframe[name_header]==nwinner)
                             & (dataframe[position_header]==pwinner)]
        if score>=threshold:
            return prospect
        else:
            return None
        
            # if not inquire:
            #     return None
            # else:
            #     print
            #     add = raw_input('Match %s with %s? (y/n) '%(name,prospect[name_header].item()))
            #     if add.lower()=='y':
            #         self.add_to_whitelist(fmt_str%(name,position),
            #                               fmt_str%(prospect[name_header].item(),
            #                                        prospect[position_header].item()))
            #         return prospect
            #     else:
            #         return None
                            
            
    def add_to_whitelist(self,item1,item2):
        entered = False
        for entries in self.whitelist:
            if item1==entries[0] and item2==entries[1]:
                entered = True
                break
        if not entered:
            self.whitelist.append([item1,item2])
            self.list_to_file(self.whitelist,self.whitelist_filename)

    def list_to_file(self,l,fn,min_items=2):
        fid = open(fn,'w')
        for sublist in l:
            if len(sublist)>=min_items:
                line = ','.join(sublist)+'\n'
                fid.write(line)
        fid.close()

    def file_to_list(self,fn,min_items=2):
        fid = open(fn,'r')
        lines = fid.readlines()
        fid.close()

        out = []
        for line in lines:
            sublist = line.strip().split(',')
            if len(sublist)>=min_items:
                out.append(sublist)
        return out


