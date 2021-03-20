from . import build_league,build_player_table,position_color_dict,posrank_split
from .pfr_tools import get_player_gamelog
import sys,os,glob
from matplotlib import pyplot as plt
import numpy as np
import logging


default_figsize = (6,4)
markersize = 5

def make_attribute_plot(player_set,func1,func2,marker='ko',title=None,ylim=None,xlim=None,verbose=False,plotfunc=plt.plot):

    fig = plt.figure(figsize=default_figsize)

    xvec = []
    yvec = []
    for p in player_set:
        x = func1(p,verbose=verbose)
        y = func2(p,verbose=verbose)
        if np.isnan(x) or np.isnan(y):
            continue
        xvec.append(x)
        yvec.append(y)
        
        if type(marker)==str:
            plotfunc(x,y,marker,markersize=markersize)
        else:
            plotfunc(x,y,marker(p))

    padfrac = 0.05
    if xlim is None:
        xr = np.ptp(xvec)
        pad = xr*padfrac
        xlim = (np.min(xvec)-pad,np.max(xvec)+pad)
        
    if ylim is None:
        yr = np.ptp(yvec)
        pad = yr*padfrac
        ylim = (np.min(yvec)-pad,np.max(yvec)+pad)

    plt.xlim(xlim)
    plt.ylim(ylim)
    plt.xlabel(func1.__doc__)
    plt.ylabel(func2.__doc__)
    plt.box(False)
    
    if not title is None:
        plt.title(title)
    tag1 = func1.__doc__.lower().replace(' ','_')
    tag2 = func2.__doc__.lower().replace(' ','_')
    tag = '%s_v_%s'%(tag1,tag2)
    tag = tag.replace('(','').replace(')','')
    os.makedirs('plots',exist_ok=True)
    out_fn = os.path.join('plots','%s.png'%tag)
    plt.savefig(out_fn)


def make_league_plot(league,rookie_year,func,description='generic',mode='keepers',ylim=(None,None),ytickfmt='%0.1f',verbose=False,plotfunc=plt.plot):

    # func must be a function that takes a player and returns a single, plottable value
    # mode can be 'keepers' or 'players'
    
    xticklabels = []
    n_teams = len(league.teams)
    xticks = range(n_teams)

    shifts = {'QB':-1.5,'RB':-.5,'WR':.5,'TE':1.5}

    positional = False

    markeredgewidth = 0.75

    marker = 'o'

    plot_orientation = True # orient like a plot (origin @ lower left)
    try:
        # if ylims are reversed, make plot_orientation False
        plot_orientation = ylim[0]<ylim[1]
    except TypeError:
        # None values, use default ylims
        pass

    topped = False
    bottomed = False
    plt.figure(figsize=default_figsize)
    for idx,team in enumerate(league.teams):

        if mode=='keepers':
            players = team.get_keepers(rookie_year=rookie_year)
        elif mode=='players':
            players = team.players
        else:
            sys.exit('Bad mode %s.'%mode)
        
        logging.info('%s (%s)'%(team.team_name,team.team_abbr))
        logging.info(players)

        for k in players:
            r = func(k,verbose=verbose)
            if r is None:
                continue
            posrank = k.posrank
            p,pr = posrank_split(posrank)
            if k.draft_year==rookie_year:
                markeredgecolor = 'k'
            else:
                markeredgecolor = 'none'

            try:
                if r>max(ylim):
                    r = max(ylim)
                    topped = True
            except TypeError:
                pass
            
            try:
                if r<min(ylim):
                    r = min(ylim)
                    bottomed = True
            except TypeError:
                pass

            plotfunc(idx+shifts[p]*.15,r,'%s%s'%(position_color_dict[k.position],marker),markersize=markersize,markeredgecolor=markeredgecolor,markeredgewidth=markeredgewidth)
        xticklabels.append(team.team_abbr)

    for k in ['QB','RB','WR','TE']:
        plotfunc(-10,-10,'%s%s'%(position_color_dict[k],marker),label=k,markersize=markersize)
    plotfunc(-10,-10,'wo',markersize=markersize,label='rookie',markeredgecolor='k',markeredgewidth=markeredgewidth)
    #plotfunc(-10,-10,'r%s'%marker,label='rookie',markersize=markersize,markerfacecolor='w',markeredgecolor=markeredgecolor,markeredgewidth=2)


    plt.legend()
    plt.ylabel(func.__doc__)
    plt.xlabel('team')

    plt.xticks(xticks)
    plt.gca().set_xticklabels(xticklabels)

    plt.xlim((-1,n_teams+1))


    if ylim[0] is None and ylim[1] is None:
        ylim = plt.ylim()
    
    try:
        if ylim[1]>ylim[0]:
            plt.ylim((ylim[0]-1,ylim[1]+1))
        else:
            plt.ylim((ylim[0]+1,ylim[1]-1))
    except TypeError:
        plt.ylim(ylim)
        
    yticks = plt.gca().get_yticks()
    dy = np.diff(yticks).mean()

    if topped and bottomed:
        yticks = list(np.arange(min(ylim),max(ylim),dy))+[max(ylim)]
    elif topped:
        yticks = list(np.arange(max(ylim),min(ylim),-dy))[::-1]
    elif bottomed:
        yticks = list(np.arange(min(ylim),max(ylim),dy))
    else:
        yticks = np.arange(min(ylim),max(ylim)+1,dy)

        
        
    yticklabels = [ytickfmt%t for t in yticks]

    if topped:
        yticklabels[-1]+='+'
    if bottomed:
        yticklabels[0]+='-'
    
    plt.yticks(yticks)
    plt.gca().set_yticklabels(yticklabels)

    plt.gca().spines["top"].set_visible(False)
    plt.gca().spines["right"].set_visible(False)
    plt.gca().spines["bottom"].set_visible(False)
    plt.gca().spines["left"].set_visible(False)

    out_fn = os.path.join('plots',func.__doc__.lower().replace(' ','_').replace('(','').replace(')','')+'_%s'%mode+'.png')
    os.makedirs('plots',exist_ok=True)
    plt.savefig(out_fn)
