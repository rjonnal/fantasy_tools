import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from unicodedata import normalize
import relish
from bs4 import BeautifulSoup
import requests
import sys




def url_to_tag(url):
    return url.replace('https://','').replace('http://','').replace('/','_')


def get_soup(url):
    
    tag = url_to_tag(url)
    print(url)
    print(tag)
    try:
        response = relish.load(tag)
        print('Getting cached %s'%tag)
    except Exception as e:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.77 Safari/537.36"}
        response = requests.get(url,headers=headers)
        relish.save(tag,response)
    soup = BeautifulSoup(response.text, 'html.parser')
    return soup

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
