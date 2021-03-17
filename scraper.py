import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from unicodedata import normalize
import relish
from bs4 import BeautifulSoup
import requests
import sys
import re
import time

class BadResponseException(Exception):
    pass

def url_to_tag(url):
    return '_'.join(re.split('\W+',url))

def get_soup(url,sleep=0,verbose=False):
    tag = url_to_tag(url)

    try:
        response = relish.load(tag)
        if verbose:
            print('Getting cached %s'%tag)
    except Exception as e:
        if sleep:
            if verbose:
                print('Sleeping %0.3f seconds.'%sleep)
        time.sleep(sleep)
        
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.77 Safari/537.36"}
        response = requests.get(url,headers=headers)
        if verbose:
            print('%s, status: %d'%(url,response.status_code))
        relish.save(tag,response)
        if not response.status_code==200:
            raise BadResponseException

    soup = BeautifulSoup(response.text, 'html.parser')
    return soup


def get_pfr_id_from_google(fp_name,sleep_time=45):
    name_string = '+'.join(fp_name.split())
    google_url = 'https://www.google.com/search?q=%s+site:pro-football-reference.com'%name_string

    # can we just use google to get the pfr_id?
    # we can, but it takes a long time--must sleep at least
    # 45 sec between calls--maybe more, and once you get
    # a 429 response (too many calls), may have to wait hours
    # before trying again.
    print('Googling %s, waiting %d s.'%(fp_name,sleep_time))
    google_soup = get_soup(google_url,sleep=sleep_time,verbose=False)
    links = google_soup.find_all('a')
    pfr_id_google = ''
    for k in range(len(links)):
        item = links.pop(0)
        pfr_url_google = item.get('href')
        if not type(pfr_url_google) is str:
            continue
        front = 'https://www.pro-football-reference.com/players/'
        if pfr_url_google.find(front)>-1:
            toks = pfr_url_google.split('/')
            # make sure the pfr url letter matches the first letter
            # of one of the names
            if not any([toks[-2]==n[0] for n in fp_name.split()]):
                continue
            pfr_id_google = toks[-1].split('.')[0]
    return pfr_id_google


def foo():
    table = soup.find('table')

    records = []
    columns = []
    for idx,tr in enumerate(table.findAll("tr")):
        ths = tr.findAll("th")
        if idx==0:
            continue
        else:
            trs = tr.findAll("td")
            record = []
            record.append(trs[0].text.replace('+','').strip())
            record.append('https://www.pro-football-reference.com'+trs[0].find('a')['href'])
            record.append(float(trs[1].text.replace(',','')))
            records.append(record)


    columns = ['name','url','yds']
    leaders_df = pd.DataFrame(data=records, columns = columns)

    dat = []
    names = []
    for idx,leader_row in leaders_df.iterrows():
        if idx>=100:
            break
        name = leader_row['name']
        relish_tag = name.replace(' ','_')
        try:
            df = relish.load(relish_tag)
        except Exception as e:
            print('getting data from site for %s'%name)
            url = leader_row['url']
            tables = pd.read_html(url)
            for t in tables:
                if len(t.columns)==32:
                    df = t
                    break

            relish.save(relish_tag,df)

        newcols = []
        for col in df.columns:
            newcols.append(col[1])
        df.columns = newcols


        poslist = df['Pos'].tolist()
        is_wr = False
        for item in poslist:
            try:
                if item.lower()=='wr':
                    is_wr = True
                    break
            except:
                pass

        if not is_wr:
            continue

        for idx,year_row in df.iterrows():
            try:
                year = float(year_row['Year'][:4])
                #print(idx,year)
                if idx==0:
                    rookie_year = year
                age = float(year_row['Age'])
                rel_year = year-rookie_year
                if rel_year<0:
                    print(name,year,rookie_year)
                    sys.exit()
                #print(dir(year_row['Yds']))
                try:
                    yds = float(year_row['Yds'].values[0].replace(',',''))
                except:
                    yds = float(year_row['Yds'].values[0])
                dat.append([age,rel_year,yds])
                names.append(name)
                #print('Adding %s (%d).'%(name,year))
            except Exception as e:
                #print(name)
                #print(e)
                #print()
                continue


    dat = np.array(dat)


    rel_years = np.arange(0,16)
    ry_means = np.zeros(rel_years.shape)
    ry_sem = np.zeros(rel_years.shape)

    for idx,ry in enumerate(rel_years):
        valid = np.where(dat[:,1]==ry)[0]
        vals = dat[valid,2]
        ry_means[idx] = np.mean(vals)
        ry_sem[idx] = np.std(vals)/np.sqrt(len(vals))

    ages = np.arange(22,36)
    age_means = np.zeros(ages.shape)
    age_sem = np.zeros(ages.shape)

    for idx,a in enumerate(ages):
        valid = np.where(dat[:,0]==a)[0]
        vals = dat[valid,2]
        age_means[idx] = np.mean(vals)
        age_sem[idx] = np.std(vals)/np.sqrt(len(vals))


    ax1 = plt.axes([.15,.1,.8,.8])
    #ax2 = plt.axes([.15,.15,.8,.8])

    #ax1.errorbar(rel_years,ry_means,yerr=ry_sem)
    #ax1.set_xlabel('year in league')
    #ax1.set_xlim([rel_years.min(),rel_years.max()-1])

    ax1.set_ylabel('yards')
    ax1.set_title('all time top 100 receivers (career yardage)\n(error bars are SEM)')

    ax1.errorbar(ages,age_means,yerr=age_sem)
    ax1.set_xlim([ages.min(),ages.max()-1])
    ax1.set_xlabel('age')

    plt.savefig('rec_traj_age.png',dpi=100)

    plt.show()
