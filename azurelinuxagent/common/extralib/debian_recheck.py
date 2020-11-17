#######################################################################
# debian_recheck.py 
# - if distro appears to be debian, re-check
# OO version of check_debian_plain.py
# - if distro appears to be debian, re-check to see if it's actually devuan
#######################################################################
from __future__ import print_function
import platform
import os
import re
# need io for file read compatibility between python v2 and v3
import io
# for some reason this breaks travis builds (works in local builds)
# move to inside check_debian_plain() - seems to work then.
# from azurelinuxagent.common import logger

import sys

class DebianRecheck:

    debugfl=1

    localdistinfo={
        'ID' : '',
        'RELEASE' : '',
        'CODENAME' : '',
        'DESCRIPTION' : '',
    }

    sourcedata={
        'url' : '',
        'codename' : '',
        'domain' : '',
        'host' : '',
        'section' : '',
        'relfilename' : '',
        'version' : '',
        'id' : '',
    }

    def localdbg(self,msg):
        if self.debugfl==1:
            print("localdbg: ",msg,file=sys.stderr)

    def dump_distinfo(self,distinfo):
        self.localdbg("Contents of distinfo:")
        for k in distinfo.keys():
            self.localdbg(k+" => "+distinfo[k])

    def __init__(self,distinfo):
        self.localdbg("__init__: entered")
        self.dump_distinfo(distinfo)
# copy in existing keys/values from distinfo:
        for k in distinfo.keys():
            self.localdistinfo[k]=distinfo[k]

        self.find_distid()
        self.dump_sourcedata()
        if self.sourcedata['id'] == "":
# report error: unable to find distribution id
# fail gracefully - return what we were given
            self.localdbg("Unable to find distribution id") 
        else:
            self.find_sourcedata()
            self.dump_sourcedata()

            self.find_release_file()
            if self.sourcedata['relfilename'] == "":
# report error: unable to find release file
# fail gracefully - return what we were given
                self.localdbg('[kilroy] unable to find release file - giving up')
            else:
                self.find_version()
                self.dump_sourcedata()
                if self.sourcedata['version'] == "":
# report error: unable to find version
# fail gracefully - return what we were given
                    self.localdbg("Unable to find version")

        self.dump_sourcedata()

        self.localdistinfo['ID']=self.sourcedata['id']
# REVISIT: need to sort out version/release etc. 
# version should be major; release should be minor
# don't think debian adheres to this though
        self.localdistinfo['RELEASE']=self.sourcedata['version']
        self.localdistinfo['CODENAME']=self.sourcedata['codename']
        self.localdistinfo['DESCRIPTION']=self.sourcedata['id']+' GNU/Linux '+self.sourcedata['version']+' ('+self.sourcedata['codename']+')'
        

    def get_localdistinfo(self):
        return self.localdistinfo

# access methods:

    def get_id(self):
        return self.localdistinfo['ID']

    def get_release(self):
        return self.localdistinfo['RELEASE']

    def get_codename(self):
        return self.localdistinfo['CODENAME']

    def get_description(self):
        return self.localdistinfo['DESCRIPTION']


    def find_distid(self):
        originsfilename="/etc/dpkg/origins/default"
        distid=""
        sline=""

        try: 
            originsfile=io.open(originsfilename,'r')
        except: # pylint: disable bare-except
            return 

        for line in originsfile:
            if re.search("^Vendor:",line):
                sline=line
                break
        sline=sline.strip()
        if sline=="":
#           logger.error("check_debian_plain: did not find a vendor")
            self.localdbg("[kilroy] check_debian_plain: did not find a vendor")
            return 

        originsfile.close()
        distid=sline.split()[1]
        self.localdbg('[kilroy] distid='+distid)
#       logger.info("check_debian_plain: distid="+distid)
        self.sourcedata['id']=distid

    def dump_tokenlist(self,tokenlist):
        self.localdbg("tokenlist:")
        for i in range(len(tokenlist)): # pylint: disable consider-using-enumerate
            self.localdbg(str(i)+" => "+tokenlist[i])

    def find_sourcedata(self):
# extract dist/version/release data from sources.list entry
        if not os.path.isfile("/etc/apt/sources.list"):
#           logger.error("check_debian_plain: WARNING: did not find sources.list file")
            self.localdbg("[kilroy] check_debian_plain: WARNING: did not find sources.list file")
        else:
            slfile=io.open("/etc/apt/sources.list","r")
            sline=""
            for line in slfile:
# skip lines relating to a cdrom
                if re.search("cdrom:",line):
                    continue
# Find first non-commented line starting with "deb"
                if re.search("^deb",line):
                    sline=line
                    break

            slfile.close()
            sline=sline.strip()
            if sline=="":
#               logger.error("check_debian_plain: unable to find useful line in sources.list")
                self.localdbg("[kilroy] check_debian_plain: unable to find useful line in sources.list")
            else:
                tokenlist=sline.split(' ')
                self.dump_tokenlist(tokenlist)
                self.sourcedata['url']=tokenlist[1]
                self.sourcedata['codename']=tokenlist[2]
                self.sourcedata['domain']=tokenlist[3]
# extract the host and dir from the url:
                parts=re.search(r'^http://(.*?)/(.*)',self.sourcedata['url'])
                self.sourcedata['host']=parts.group(1)
                tmpsect=parts.group(2)
                self.localdbg("tmpsect="+tmpsect)
# remove trailing backslash if exists
                if re.search(r'/$',tmpsect):
# (need to test that the following will work)
                    tmpsect=tmpsect[:-1]
                self.sourcedata['section']=tmpsect

    def dump_sourcedata(self):
        self.localdbg("sourcedata - current contents - START -")
        for k in self.sourcedata.keys():
            self.localdbg('    '+k+' : '+self.sourcedata[k])

        self.localdbg("sourcedata - current contents - END   -")


    def find_release_file(self):
# Get the release file from /etc/apt/sources.list
# (use the first line starting with "deb")
#
        aptdir="/var/lib/apt/lists/"
        relfilename=""
        testfilename=""
        filenamebase=""
        self.localdbg("find_release_file: sourcedata on entry:")
        self.dump_sourcedata()
        if self.sourcedata['url'] != '':
# looks as though source line was found and successfully parsed    
            filenamebase=self.sourcedata['host']+'_'+self.sourcedata['section']+'_dists_'+self.sourcedata['codename']+'_'

# release file name may end in _Release or _InRelease - check for both
            testfilename=aptdir+filenamebase+'InRelease'
            self.localdbg("trying testfilename="+testfilename)
            if os.path.isfile(testfilename):
                relfilename=testfilename
            else:
                testfilename=aptdir+filenamebase+'Release'
                self.localdbg("not found: trying testfilename="+testfilename)
                if os.path.isfile(testfilename):
                    relfilename=testfilename
                else:
                    self.localdbg('[kilroy] no release file found')

        self.localdbg('[kilroy] relfilename='+relfilename)
        self.sourcedata['relfilename']=relfilename

    def find_version(self):
#  Get version etc. from the release file
# (for some reason, os.path.isfile sometimes doesn't seem to work)
        try:
            relfile=io.open(self.sourcedata['relfilename'],"r")
        except: # pylint: disable=bare-except
            self.localdbg('[kilroy] file '+self.sourcedata['relfilename']+' does NOT exist after all')
            return

        for line in relfile:
            if re.search('Packages$',line):
                break
            parts = re.search('Version: (.*)',line)
            if parts:
                self.sourcedata['version']=parts.group(1)
                break

        relfile.close()

        if self.sourcedata['version'] == "":
#           logger.error("check_debian_plain: unable to find version")
            self.localdbg("[kilroy] check_debian_plain: unable to find version")

def test():
# need to do this using the actual output from platform.linux_distribution
    distinfo_proto={
        'ID' : "",
        'RELEASE' : "",
        'CODENAME' : "",
    }
# (format of result is (distname,version,id))
# NB: platform.linux_distribution is deprecated (and will be removed in
# python 3.8. Suggestion is to use the distro package)
# (at coding time, the distro package appears to be even more unstable than platform)
# pylint complains that linux_distribution() is deprecated
# (disabling the check: the whole point of this code is to work around deficiencies
# in the python and debian/devuan distro checking: when these are fixed, this 
# code will become redundant and can be binned!)
# (Disabling the pylint error here - this code would only be called if it was 
# run as a main script)
    platforminfo=platform.linux_distribution() # pylint: disable=deprecated-method,no-member
    print("platforminfo:")
    print(platforminfo)
# if we got anything vaguely useful, copy it into distinfo_proto
    if platforminfo[0]!='':
        distinfo_proto['ID']=platforminfo[0]
    if platforminfo[1]!='':
        distinfo_proto['RELEASE']=platforminfo[1]
# what about the third element?
    print("(before ***** start ******)")
    print(distinfo_proto)
    print("(before ***** end ******)")
# NB: for actual use, we can construct the dictionary in the
# function call (no need to use a pre-constructed dictionary)
#    distinfo_actual=check_debian_plain(distinfo_proto)
    recheck=DebianRecheck(distinfo_proto)
    distinfo_actual=recheck.get_localdistinfo()
    print("(after ***** start ******)")
    print(distinfo_actual)
    print("(after ***** end ******)")

if __name__ == "__main__":
    test()
