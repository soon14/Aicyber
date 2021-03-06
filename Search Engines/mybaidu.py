# -*- coding: utf-8 -*-
import os
from Tkinter import *
import urllib2
from BeautifulSoup import*
from urlparse import urljoin
from pysqlite2 import dbapi2 as sqlite
ignorewords=set(['the','of','to','and','a','in','is','it'])
class crawler:
    def __init__(self,dbname):
        self.con=sqlite.connect(dbname)

    def __del__(self):
        self.con.close()

    def dbcommit(self):
        self.con.commit()

    def getentryid(self,table,field,value,createnew=True):
        cur=self.con.execute(\
            "select rowid from %s where %s='%s'" %(table,field,value))
        res=cur.fetchone()
        if res==None:
            cur=self.con.execute(\
            "insert into %s (%s) values ('%s')" % (table,field,value))
            return cur.lastrowid
        else:
            return res[0]

    def addtoindex(self,url,soup):
        if self.isindexed(url): return
        print 'Indexing' + url

        text=self.gettextonly(soup)
        words=self.separatewords(text)

        urlid=self.getentryid('urllist','url',url)

        for i in range(len(words)):
            word=words[i]
            if word in ignorewords:continue
            wordid=self.getentryid('wordlist','word',word)
            self.con.execute("insert into wordlocation(urlid,wordid,location)\
                values (%d,%d,%d)" % (urlid,wordid,i))

    def gettextonly(self,soup):
        v=soup.string
        if v==None:
            c=soup.contents
            resulttext=''
            for t in c:
                subtext=self.gettextonly(t)
                resulttext +=subtext+'\n'
            return resulttext
        else:
            return v.strip()

    def separatewords(self,text):
        splitter=re.compile('\\W*')
        return [s.lower() for s in splitter.split(text) if s != '']

    def isindexed(self,url):
        u=self.con.execute \
           ("select rowid from urllist where url='%s'" % url).fetchone()
        if u!=None:
            v=self.con.execute(\
                'select * from wordlocation where urlid=%d' % u[0]).fetchone()
            if v!=None:return True
        return False

    def addlinkref(self,urlFrom,urlTo,linkText):
        words=self.separatewords(linkText)
        fromid=self.getentryid('urllist','url',urlFrom)
        toid=self.getentryid('urllist','url',urlTo)
        if fromid==toid: return
        cur=self.con.execute("insert into link(fromid,toid) values (%d,%d)" % (fromid,toid))
        linkid=cur.lastrowid
        for word in words:
          if word in ignorewords: continue
          wordid=self.getentryid('wordlist','word',word)
          self.con.execute("insert into linkwords(linkid,wordid) values (%d,%d)" % (linkid,wordid))



    def crawl(self,pages,depth=2):
        for i in range(depth):
            newpages=set()
            for page in pages:
                try:
                    c=urllib2.urlopen(page)
                except:
                    print "Could not open %s" % page
                    continue
                soup=BeautifulSoup(c.read())
                self.addtoindex(page,soup)

                links=soup('a')
                for link in links:
                    if('href' in dict(link.attrs)):
                        url=urljoin(page,link['href'])
                        if url.find("'")!=-1:continue
                        url=url.split('#')[0]
                        if url[0:4]=='http' and not self.isindexed(url):
                            newpages.add(url)
                        linkText=self.gettextonly(link)
                        self.addlinkref(page,url,linkText)
                self.dbcommit()
            pages=newpages

    def createindextables(self):
        self.con.execute('create table urllist(url)')
        self.con.execute('create table wordlist(word)')
        self.con.execute('create table wordlocation(urlid,wordid,location)')
        self.con.execute('create table link(fromid integer,toid integer)')
        self.con.execute('create table linkwords(wordid,linkid)')
        self.con.execute('create index wordidx on wordlist(word)')
        self.con.execute('create index urlidx on urllist(url)')
        self.con.execute('create index wordurlidx on wordlocation(wordid)')
        self.con.execute('create index urltodix on link(toid)')
        self.con.execute('create index urlfromidx on link(fromid)')
        self.dbcommit()
    def calculatepagerank(self,iterations=20):
        self.con.execute('drop table if exists pagerank')
        self.con.execute('create table pagerank(urlid primary key,score)')

        self.con.execute('insert into pagerank select rowid, 1.0 from urllist')
        self.dbcommit()

        for i in range(iterations):
            print "Iteration %d" % (i)
            for (urlid,) in self.con.execute('select rowid from urllist'):
                pr = 0.15

                for (linker,) in self.con.execute(\
                    'select distinct fromid from link where toid=%d' % urlid):
                    linkingpr=self.con.execute(\
                        'select score from pagerank where urlid=%d' % linker).fetchone()[0]
                    
                    linkingcount=self.con.execute(\
                        'select count(*) from link where fromid=%d' % linker).fetchone()[0]
                    pr +=0.85*(linkingpr/linkingcount)
                    self.con.execute(\
                        'update pagerank set score=%f where urlid=%d' % (pr,urlid))
            self.dbcommit()    
                     
class searcher:
    def __init__(self,dbname):
        self.con=sqlite.connect(dbname)

    def __del__(self):
        self.con.close()

    def getmatchrows(self,q):
        fieldlist='w0.urlid'
        tablelist=''
        clauselist=''
        wordids=[]

        words=q.split(' ')
        tablenumber=0
        #pp
        pp = []
        for word in words:
            #='%s'
            wordrow=self.con.execute(\
                "select rowid from wordlist where word =  '%s%s%s'" % ('',word,'')).fetchone()
            if wordrow != None:
                wordbxz=self.con.execute(\
                "select word from wordlist where rowid = %s" % (wordrow[0])).fetchone()
                print "匹配单词",
                print wordbxz[0]
                pp.append(wordbxz[0])
                wordid=wordrow[0]
                wordids.append(wordid)
                if tablenumber>0:
                    tablelist +=','
                    clauselist +=' and '
                    clauselist +='w%d.urlid=w%d.urlid and ' % (tablenumber-1,tablenumber)
                fieldlist += ',w%d.location' % tablenumber
                tablelist +='wordlocation w%d' % tablenumber
                clauselist +='w%d.wordid=%d' % (tablenumber,wordid)
                tablenumber +=1
        fullquery='select %s from %s where %s' % (fieldlist,tablelist,clauselist)
        cur=self.con.execute(fullquery)
        rows=[row for row in cur]
        #print pp
        return rows,wordids
    def getscoredlist(self,rows,wordids):
        totalscores=dict([(row[0],0) for row in rows])

        weights=[(1.0,self.frequencyscore(rows)),\
                 (1.5,self.locationscore(rows)),\
                 (1.0,self.pagerankscore(rows))]
                 #(1.0,self.linktextscore(rows,wordids))]

        for (weight,scores) in weights:
            for url in totalscores:
                totalscores[url] += weight*scores[url]
        return totalscores
    def geturlname(self,id):
        return self.con.execute(\
            "select url from urllist where rowid=%d" % id).fetchone()[0]
        
    def query(self,q):
        #####
        rows,wordids=self.getmatchrows(q)
        scores=self.getscoredlist(rows,wordids)
        rankedscores=sorted([(score,url) for (url,score) in scores.items()],reverse=1)
        print '\t'
        for (score,urlid) in rankedscores[0:4]:
            print '%f\t%s' % (score,self.geturlname(urlid))
    def que(self,q):
        qq = q.split(' ')
        if qq[-1] == '': qq.pop()
        if len(qq) > 1 and len(qq[-1]) > 3:
            wordbxz=self.con.execute(\
                "select rowid from wordlist where word like '%s%s%s'" % ('%',qq[-1],'%')).fetchmany(5)
            for i in wordbxz:
                word=self.con.execute(\
                    "select word from wordlist where rowid = %s" % (i[0])).fetchone()
                self.query(qq[0]+' '+word[0])
        else:         
            wordbxz=self.con.execute(\
                    "select rowid from wordlist where word like '%s%s%s'" % ('%',qq[0],'%')).fetchmany(10)
            for i in wordbxz:
                word=self.con.execute(\
                    "select word from wordlist where rowid = %s" % (i[0])).fetchone()
                self.query(word[0])

    def normalizescores(self,scores,smallIsBetter=0):
        vsmall=0.00001
        if smallIsBetter:
            minscore=min(scores.values())
            return dict([(u,float(minscore)/max(vsmall,l)) for (u,l)\
                         in scores.items()])
        else:
            maxscore=max(scores.values())
            if maxscore==0: maxscore=vsmall
            return dict([(u,float(c)/maxscore) for (u,c) in scores.items()])

    def frequencyscore(self,rows):
        counts=dict([(row[0],0) for row in rows])
        for row in rows: counts[row[0]] +=1
        return self.normalizescores(counts)

    def locationscore(self,rows):
        locations=dict([(row[0],1000000) for row in rows])
        for row in rows:
            loc=sum(row[1:])
            if loc<locations[row[0]] : locations[row[0]]=loc
        return self.normalizescores(locations,smallIsBetter=1)

    def distancescore(self,rows):
        if len(rows[0])<=2:return dict([(row[0],1.0) for row in rows])

        mindistance=dict([(row[0],1000000) for row in rows])

        for row in rows:
            dist=sum([abs(row[i]-row[i-1]) for i in range(2,len(row))])
            if dist<mindistance[row[0]]: mindistance[row[0]]=dist
        return self.normalizescores(mindistance,smallIsBetter=1)

    def inboundlinkscore(self,rows):
        uniqueurls=set([row[0] for row in rows])
        inboundcount=dict([(u,self.con.execute(\
            'select count(*) from link where toid=%d' % u).fetchone()[0])\
            for u in uniqueurls])
        return self.normalizescores(inboundcount)
    def pagerankscore(self,rows):
        pageranks=dict([(row[0],self.con.execute('select score from pagerank where\
             urlid=%d' % row[0]).fetchone()[0]) for row in rows])
        maxrank=max(pageranks.values())
        normalizedscores=dict([(u,float(l)/maxrank) for (u,l) in pageranks.items()])
        return normalizedscores

    def linktextscore(self,rows,wordids):
        linkscores=dict([(row[0],0) for row in rows])
        for wordid in wordids:
            cur=self.con.execute('select link.fromid,link.toid from linkwords,\
        link where wordid=%d and linkwords.linkid=link.rowid' % wordid)
            for(fromid,toid) in cur:
                if toid in linkscores:
                    pr=self.con.execute('select score from pagerank where \
                    urlid=%d' % fromid).fetchone()[0]
                    linkscores[toid] += pr
        maxscore=max(linkscores.values())
        normalizedscores=dict([(u,float(1)/maxscore) for (u,l) in linkscores.items()])
        return normalizedscores
'''    
crawler=crawler('searchindex.db')

crawler.createindextables()
pagelist=['http://www.chinadaily.com.cn/']
crawler.crawl(pagelist)
'''
e=searcher('searchindex.db')
a = []
souleng = [0]
def printkey(event):
    print '\n'*80
    if event.char == ' ' or (event.char >= 'A' and event.char <= 'z'):
        a.append(event.char)
    else:
        if len(a) > 0:
            a.pop()
        if len(souleng) > 2:
            souleng.pop()
    b = ''.join(a)
    print '现在搜索'+b
    if len(b) > 3 and len(b) > souleng[-1]:
        e.que(b)
        souleng.append(len(b))
root = Tk()
root.title(unicode('Googlee','eucgb2312_cn'))
entry = Entry(root)
entry.bind('<Key>', printkey)
entry.pack()
root.mainloop()

#[row for row in crawler.con.execute('select rowid from wordlocation where wordid=1')]
#e=searcher('searchindex.db')
#e.query('showcode')
#e=searcher('searchindex.db')
#e.getmatchrows('china')
#e.getmatchrows('china')
'''
crawler=crawler('searchindex.db')
crawler.calculatepagerank()
cur=crawler.con.execute('select * from pagerank order by score desc')
for i in range(3): print cur.next()
'''
