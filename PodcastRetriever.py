#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#**************************************************************************
#   Copyright (C) 2018, Paul Lutus                                        *
#                                                                         *
#   This program is free software; you can redistribute it and/or modify  *
#   it under the terms of the GNU General Public License as published by  *
#   the Free Software Foundation; either version 2 of the License, or     *
#   (at your option) any later version.                                   *
#                                                                         *
#   This program is distributed in the hope that it will be useful,       *
#   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
#   GNU General Public License for more details.                          *
#                                                                         *
#   You should have received a copy of the GNU General Public License     *
#   along with this program; if not, write to the                         *
#   Free Software Foundation, Inc.,                                       *
#   59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.             *
#**************************************************************************

# this program relies on the recent adoption of a uniform XML format for
# podcast listings in all the sites I've accessed in the past.
# The program automatically gives downloaded files meaningful names based
# on the XML data (proper titles and release dates)
# provided along with the file paths.

import re, sys, os, subprocess, urllib.request, datetime, \
 time, codecs, argparse, copy
 
#import ssl

#try:
#    _create_unverified_https_context = ssl._create_unverified_context
#except AttributeError:
#    # Legacy Python that doesn't verify HTTPS certificates by default
#    pass
#else:
#    # Handle target environment that doesn't support HTTPS verification
#    ssl._create_default_https_context = _create_unverified_https_context

import xml.etree.ElementTree as ET

PVERSION = 1.3 # 2018.10.13

class PodcastRetriever:
  
  def __init__(self):
    
    self.monthhash = {'Jan':1,'Feb':2,'Mar':3,'Apr':4,'May':5,'Jun':6,'Jul':7,'Aug':8,'Sep':9,'Oct':10,'Nov':11,'Dec':12,}

    self.ever_downloaded = []
    
    # retries in the event of download errors
    self.retries = 4
    self.sleep_time = .25
    
  def make_dir_if_needed(self,ds):
    if not os.path.exists(ds):
      os.makedirs(ds)

  def file_size(self,path):
    return os.stat(path).st_size

  def add_to_downloaded(self,s):
    # avoid recording duplicates
    if(s not in self.ever_downloaded):
      self.ever_downloaded.append(s)
      
  def read_downloaded(self):
    data = ''
    # this file may not exist, so ...
    try:
      with(codecs.open(self.ever_down_path,encoding='utf-8')) as f:
        data = f.read()
    except IOError:
      None
    except Exception as e:
      print('Error loading "%s": %s' % (self.ever_down_path,e))
      
    for item in data.strip().split(os.linesep):
      if(len(item) > 0):
        self.add_to_downloaded(item)
        
  def write_downloaded(self):
    if(len(self.ever_downloaded) > 0):
      ever_text = os.linesep.join(sorted(self.ever_downloaded)) + os.linesep
      with(codecs.open(self.ever_down_path,'w',encoding='utf-8')) as f:
        f.write(ever_text)
      
  def downloadProgress(self,count, blockSize, totalSize):
    percent = int(count*blockSize*100/totalSize)
    sys.stdout.write("\r%s ... %d%% " % (self.targetfile,percent))
    sys.stdout.flush()
      
  def download_file(self,url,title,destpath):
    self.targetfile = '  Downloading podcast "%s"' % title
    finished = False
    count = self.retries
    while(not finished and count > 0):
      try:
        urllib.request.urlretrieve(url,destpath,reporthook=self.downloadProgress)
        finished = True
      except Exception as e:
        print('  Error for media title "%s", URL "%s": "%s", trying again.' % (title,url,e))
        time.sleep(self.sleep_time)
      print('')
      count -= 1
    if(count == 0):
      print('  Download failed for media title "%s".' % title)

  def download_rss_file(self,podsub,url):
    data = ''
    finished = False
    count = self.retries
    while(not finished and count > 0):
      try:
        req = urllib.request.Request(
          url,
          data = None, 
          headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'
            }
        )
        resp = urllib.request.urlopen(req)
        data = resp.read().decode('utf-8')
        finished = (len(data) > 0)
      except Exception as e:
        print('  Error for RSS title "%s", URL "%s": "%s", trying again.' % (podsub,url,e))
        time.sleep(self.sleep_time)
      count -= 1
    if(count == 0):
      print('  Download failed for RSS title "%s".' % podsub)
    return data
    
  def beautify_html(self,page):
    output = ''
    lines = re.split('%s+' % os.linesep,page)
    tab = '  '
    indent = 0
    for line in lines:
      if(re.search('</\w',line)): indent -= 1
      output += (tab * indent) + line + os.linesep
      # look for a tag opening '<\w' not followed by '/>'
      if(re.search('<\w((?!/>).)*$',line)): indent += 1
    return output
    
  def wrap_tag(self,tag,content,extension = ''):
    if(len(extension) > 0):
      extension = ' ' + extension
    return '<%s%s>%s%s%s</%s>%s' % (tag,extension,os.linesep,content,os.linesep,tag,os.linesep)
    
  def create_webpage(self,sites):
    xmltop = '<?xml version="1.0" encoding="UTF-8"?>' + os.linesep
    meta = '<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />' + os.linesep
    css = """
body {
  font-family: Verdana, Tahoma, Helvetica, Arial;
  background-color:#fcf8e9;
}
a {
  color:black;
  text-decoration:none;
}
a:visited {
  color:#c0c0c0;
}
a:hover {
  background-color:#f0f0f0;
}
b:hover {
  cursor:hand;
  cursor:pointer;
}
.boxed {
  background-color:white;
  padding:4px;
  box-shadow: 0px 0px 1px 1px #dda;
}
"""
    page = ''
    for title in sorted(sites.keys()):
      site = sites[title]
      description = site['desc']
      items = ''
      for key in sorted(site['items'].keys()):
        path = site['items'][key]['path']
        desc = site['items'][key]['desc']
        if(desc):
          # sanitize the description
          desc = re.sub('(?s)<!--.*-->','',desc)
          desc = re.sub('(?s)<.*?>','',desc)
          desc = re.sub('(?s)"',r'&quot;',desc)
        else:
          desc=""
        if(os.path.exists(path)):
          link = self.wrap_tag('a',key,'href="%s" title="%s"' % (path,desc))
          items += self.wrap_tag('li',link)
      if(len(items) > 0):
        page += self.wrap_tag('b',title,'title = "%s"' % description)
        box = self.wrap_tag('ul',items)
        page += self.wrap_tag('blockquote',box,'class="boxed"')
    pagelink = self.wrap_tag('a','PodcastRetriever','href="http://arachnoid.com/python/PodcastRetriever"')
    copyright = self.wrap_tag('center',pagelink + u'&nbsp;Copyright © 2015, P. Lutus')  
    page = self.wrap_tag('body',page + copyright)
    htitle = self.wrap_tag('title','PodcastRetriever : Available Podcasts')
    csstag = self.wrap_tag('style',css,'type="text/css"')
    page = self.wrap_tag('head',htitle+meta+csstag) + page
    page = self.wrap_tag('html',page)
    page = self.beautify_html(page)
    page = xmltop + page
    with codecs.open('%s/index.html' % self.wpd,'w',encoding='utf-8') as f:
      f.write(page)
              
  def main(self):
    
    def_year = datetime.datetime.now().year - 1
    
    parser = argparse.ArgumentParser()
    parser.add_argument('-p','--podcasts', help='Podcast storage directory, default "podcasts"', default='podcasts')
    parser.add_argument('-w','--webpage', help='Web page directory, default "webpage"', default='webpage')
    parser.add_argument('-r','--rss', help='RSS feeds storage directory, default "rss"', default='rss')
    parser.add_argument('-s','--state', help='Program state storage directory, default "state"', default='state')
    parser.add_argument('-y','--year', help='Earliest year, default %d' % def_year, type=int, default=def_year)
    parser.add_argument('-m','--month', help='Earliest month, default 1', type=int, default=1)
    parser.add_argument('-d','--day', help='Earliest day, default 1', type=int, default=1)
    parser.add_argument('-k','--keep', help='Keep window open after retrieval is finished',action="store_true")
    self.args = parser.parse_args()
    
    self.pod_dir = os.path.abspath(self.args.podcasts)
    self.make_dir_if_needed(self.pod_dir)
    
    self.edp = os.path.abspath(self.args.state)
    self.make_dir_if_needed(self.edp)
    self.ever_down_path = os.path.join(self.edp,'ever_downloaded.txt')
    self.resource_path = os.path.join(self.edp,'resources.txt')
    
    self.rssf = os.path.abspath(self.args.rss)
    self.make_dir_if_needed(self.rssf)
    
    self.wpd = os.path.abspath(self.args.webpage)
    self.make_dir_if_needed(self.wpd)
    
    self.read_downloaded()
    
    self.original_downloaded = copy.deepcopy(self.ever_downloaded)
    
    try:
      with(codecs.open(self.resource_path,encoding='utf-8')) as f:
        data = f.read()
    except:
      print("No resource file %s, quitting." % self.resource_path)
    else:
      
      self.resources = [re.split(r'\s*,\s*',x) for x in re.findall(r'\s*(.*?)\s*\n+',data) if len(x) > 0 and x[0] != '#']

      new_downloads = 0
      
      sites = {}
      
      for url,podsub in self.resources:
  
        destdir = os.path.join(self.pod_dir,podsub)
        self.make_dir_if_needed(destdir)
        
        print('Checking online "%s" resource ...' % podsub)
            
        rsspath = os.path.join(self.rssf,'%s.xml' % (podsub))
        
        data = self.download_rss_file(podsub,url)
          
        # save the rss feed for later perusal
        if(len(data) > 0):  
          with codecs.open(rsspath,'w',encoding='utf-8') as f:
            f.write(data)
        else:
          try:
            with(codecs.open(rsspath,encoding='utf-8')) as f:
              data = f.read()
          except:
            # no online access, no old RSS file to read
            continue 
        
        root = ET.fromstring(data)
        
        channel = root.find('channel')
        
        ctitle = channel.find('title').text
        try:
          desc = channel.find('description').text
        except:
          desc = ''
        
        sites[ctitle] = { 'sub' : podsub, 'desc' : desc }
        
        items = {}
        
        for item in channel.findall('item'):
          url = item.find('enclosure').get('url')
          suffix = re.sub('.*\.([a-zA-Z0-9]+).*',r'\1',url)
          day,month,year = re.sub(r'\S+\s+(\S+)\s+(\S+)\s+(\S+).*',r'\1,\2,\3',item.find('pubDate').text).split(',')
          day,month,year = [int(x) for x in (day,self.monthhash[month],year)]
          fmtdate = '%04d.%02d.%02d' % (year,month,day)
          pdesc = item.find('description').text
          ptitle = item.find('title').text
          title = ptitle.strip()
          title = re.sub('[^A-Za-z0-9]','_',title)
          title = re.sub('_+','_',title)
          # solve title too long problem
          title = title[:128]
          dest_tag = os.path.join(podsub,'%s.%s.%s' % (fmtdate,title,suffix))
          destpath = os.path.join(self.pod_dir,dest_tag)
          if(year >= self.args.year and month >= self.args.month and day >= self.args.day):  
            if((not os.path.exists(destpath) or self.file_size(destpath) == 0) and (dest_tag not in self.ever_downloaded)):
              self.download_file(url,title,destpath)
              if(os.path.exists(destpath)):
                if(self.file_size(destpath) == 0):
                  print('  Removing zero-length file %s ...' % destpath)
                  os.remove(destpath)
                else:
                  self.add_to_downloaded(dest_tag)
                  # set file time to release date
                  t = datetime.datetime(year,month,day).timestamp()
                  os.utime(destpath,(t,t))
                  new_downloads += 1
            else:
              self.add_to_downloaded(dest_tag)
            pagetitle = '%s.%s' % (fmtdate,ptitle)
            items[pagetitle] = { 'path' : destpath, 'desc' : pdesc }
        sites[ctitle]['items'] = items
      
      if(len(sites) > 0):        
        self.create_webpage(sites)
      
      # write downloaded files table
      if(self.original_downloaded != self.ever_downloaded):
        self.write_downloaded()
  
      print('Finished, downloaded %d new podcasts.' % new_downloads)

    if(self.args.keep):
      input('Press Enter to close:')

# if not called as a module, then run main()
if(__name__ == '__main__'):
  PodcastRetriever().main()