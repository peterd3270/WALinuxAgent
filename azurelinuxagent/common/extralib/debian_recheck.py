#######################################################################
# debian_recheck.py
# - if distro appears to be debian, re-check
# OO version of check_debian_plain.py
# - if distro appears to be debian, re-check to see if it's actually devuan
#######################################################################
"""
debian_recheck.py - if distro is reported as being debian,
re-check it ( due to current problems with the platform.linux_distribution
module, it may actually be devuan )
"""
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

class DebianRecheck():
    """
    DebianRecheck - assemble information required to
    re-check whether the distro is debian or devuan.
    Take the information already ascertained from the platform.* modules,
    and re-check each item. Fail safe - if anything unexpected is
    encountered, re-set all the information to that given at the start
    """

    debugfl = 1

    localdistinfo = {
        'ID' : '',
        'RELEASE' : '',
        'CODENAME' : '',
        'DESCRIPTION' : '',
    }

    sourcedata = {
        'ok' : 1,
        'url' : '',
        'codename' : '',
        'domain' : '',
        'host' : '',
        'section' : '',
        'relfilename' : '',
        'version' : '',
        'id' : '',
    }

    def localdbg(self, msg):
        """
        output a message to stderr if a flag is set
        seems to be the only way to get extra information from within
        travis builds
        """
        if self.debugfl == 1:
            print("localdbg: ", msg, file=sys.stderr)

    def dump_distinfo(self, distinfo):
        """
        dump out the keys/values in the distinfo dict
        (as an aid to checking the values which will be
        returned by the access methods)
        """
        self.localdbg("Contents of distinfo:")
        for k in distinfo.keys():
            self.localdbg(k+" => "+distinfo[k])

    def __init__(self, distinfo):
##################################################################
# 2020-11-18:
# We ***have*** to ensure that if something doesn't look right, we
# preserve and return the information with which we were provided
# Added 'ok' flag to sourcedata dict - be optimistic and initialise
# it to 1. If anything goes wrong, set it to 0. At the end, only
# update localdistinfo with the "real" information if the flag
# is still set to 1
##################################################################
        self.localdbg("__init__: entered")
        self.dump_distinfo(distinfo)
# copy in existing keys/values from distinfo:
        for k in distinfo.keys():
            self.localdistinfo[k] = distinfo[k]

        self.find_distid()
        self.dump_sourcedata()
        if self.sourcedata['ok'] == 0:
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
# Need to retain what we were given for RELEASE - otherwise we'll hit the
# horrible version attribute error problem:
                    self.sourcedata['version'] = distinfo['RELEASE']

        self.dump_sourcedata()

        if self.sourcedata['ok'] == 1:
            self.localdistinfo['ID'] = self.sourcedata['id']
# REVISIT: need to sort out version/release etc.
# version should be major; release should be minor
# don't think debian adheres to this though
            self.localdistinfo['RELEASE'] = self.sourcedata['version']
            self.localdistinfo['CODENAME'] = self.sourcedata['codename']
            self.localdistinfo['DESCRIPTION'] = self.sourcedata['id']+\
' GNU/Linux '+\
self.sourcedata['version']+' ('+\
self.sourcedata['codename']+')'
        else:
            self.localdbg("ok == 0 - not updating localdistinfo")


    def get_localdistinfo(self):
        """
        return the localdistinfo dict
        """
        return self.localdistinfo

# access methods:

    def get_id(self):
        """
        return the value for ID
        """
        return self.localdistinfo['ID']

    def get_release(self):
        """
        return the value for RELEASE
        """
        return self.localdistinfo['RELEASE']

    def get_codename(self):
        """
        return the value for CODENAME
        """
        return self.localdistinfo['CODENAME']

    def get_description(self):
        """
        return the value for DESCRIPTION
        """
        return self.localdistinfo['DESCRIPTION']


    def find_distid(self):
        """
        try to find the distribution ID
        if found, add it to sourcedata
        if not, set sourcedata['ok'] to 0
        """
        originsfilename = "/etc/dpkg/origins/default"
        distid = ""
        sline = ""

        try:
            originsfile = io.open(originsfilename, 'r')
        except: # pylint: disable=bare-except
            self.sourcedata['ok'] = 0
            return

        for line in originsfile:
            if re.search("^Vendor:", line):
                sline = line
                break
        sline = sline.strip()
        if sline == "":
#           logger.error("check_debian_plain: did not find a vendor")
            self.localdbg("[kilroy] check_debian_plain: did not find a vendor")
            self.sourcedata['ok'] = 0
            return

        originsfile.close()
        distid = sline.split()[1]
        self.localdbg('[kilroy] distid='+distid)
#       logger.info("check_debian_plain: distid="+distid)
        self.sourcedata['id'] = distid

    def dump_tokenlist(self, tokenlist):
        """
        dump out the list of tokens (for debugging)
        """
        self.localdbg("tokenlist:")
        for i in range(len(tokenlist)): # pylint: disable=consider-using-enumerate
            self.localdbg(str(i)+" => "+tokenlist[i])

    def find_sourcedata(self):
        """
        look up the the line in the sources.list file which seems
        to point to the primary source;
        """
# extract dist/version/release data from sources.list entry
        if not os.path.isfile("/etc/apt/sources.list"):
#           logger.error("check_debian_plain: WARNING: did not find sources.list file")
            self.localdbg("[kilroy] check_debian_plain: WARNING: did not find sources.list file")
            self.sourcedata['ok'] = 0
        else:
            slfile = io.open("/etc/apt/sources.list", "r")
            sline = ""
            for line in slfile:
# skip lines relating to a cdrom
                if re.search("cdrom:", line):
                    continue
# Find first non-commented line starting with "deb"
                if re.search("^deb", line):
                    sline = line
                    break

            slfile.close()
            sline = sline.strip()
            if sline == "":
#               logger.error("check_debian_plain: unable to find useful line in sources.list")
                self.localdbg("[kilroy] check_debian_plain: "+\
"unable to find useful line in sources.list")
                self.sourcedata['ok'] = 0
            else:
                tokenlist = sline.split(' ')
                self.dump_tokenlist(tokenlist)
                self.sourcedata['url'] = tokenlist[1]
                self.sourcedata['codename'] = tokenlist[2]
                self.sourcedata['domain'] = tokenlist[3]
# extract the host and dir from the url:
                parts = re.search(r'^http://(.*?)/(.*)', self.sourcedata['url'])
                self.sourcedata['host'] = parts.group(1)
                tmpsect = parts.group(2)
                self.localdbg("tmpsect="+tmpsect)
# remove trailing backslash if exists
                if re.search(r'/$', tmpsect):
# (need to test that the following will work)
                    tmpsect = tmpsect[:-1]
                self.sourcedata['section'] = tmpsect

    def dump_sourcedata(self):
        """
        dump out the current keys/values in sourcedata
        (primarily for debugging)
        """
        self.localdbg("sourcedata - current contents - START -")
        for k in self.sourcedata.keys():
            self.localdbg('    '+str(k)+' : '+str(self.sourcedata[k]))

        self.localdbg("sourcedata - current contents - END   -")


    def find_release_file(self):
# Get the release file from /etc/apt/sources.list
# (use the first line starting with "deb")
#
        """
        Having got the details of the release file from
        the sources.list file, construct the name of the
        release file, and check if it exists.
        If unsuccessful, set sourcedata['ok'] to 0
        """
        aptdir = "/var/lib/apt/lists/"
        relfilename = ""
        testfilename = ""
        filenamebase = ""
        self.localdbg("find_release_file: sourcedata on entry:")
        self.dump_sourcedata()
        if self.sourcedata['url'] != '':
# looks as though source line was found and successfully parsed
            filenamebase = self.sourcedata['host']+'_'+\
self.sourcedata['section']+\
'_dists_'+self.sourcedata['codename']+'_'

# release file name may end in _Release or _InRelease - check for both
            testfilename = aptdir+filenamebase+'InRelease'
            self.localdbg("trying testfilename="+testfilename)
            if os.path.isfile(testfilename):
                relfilename = testfilename
            else:
                testfilename = aptdir+filenamebase+'Release'
                self.localdbg("not found: trying testfilename="+testfilename)
                if os.path.isfile(testfilename):
                    relfilename = testfilename
                else:
                    self.localdbg('[kilroy] no release file found')

        self.localdbg('[kilroy] relfilename='+relfilename)
        self.sourcedata['relfilename'] = relfilename

    def find_version(self):
        """
        Having found a valid release file name, and having checked
        that it exists, read it to determine the distro version
        """
#  Get version etc. from the release file
# (for some reason, os.path.isfile sometimes doesn't seem to work)
        try:
            relfile = io.open(self.sourcedata['relfilename'], "r")
        except: # pylint: disable=bare-except
            self.localdbg('[kilroy] file '+self.sourcedata['relfilename']+\
' does NOT exist after all')
            self.sourcedata['ok'] = 0
            return

        for line in relfile:
            if re.search('Packages$', line):
                break
            parts = re.search('Version: (.*)', line)
            if parts:
                self.sourcedata['version'] = parts.group(1)
                break

        relfile.close()

        if self.sourcedata['version'] == "":
#           logger.error("check_debian_plain: unable to find version")
            self.localdbg("[kilroy] check_debian_plain: unable to find version")
            self.sourcedata['ok'] = 0

def test():
    """
    If run as a script, test functionality
    """
# need to do this using the actual output from platform.linux_distribution
    distinfo_proto = {
        'ID' : "",
        'RELEASE' : "",
        'CODENAME' : "",
    }
# (format of result is (distname, version, id))
# NB: platform.linux_distribution is deprecated (and will be removed in
# python 3.8. Suggestion is to use the distro package)
# (at coding time, the distro package appears to be even more unstable than platform)
# pylint complains that linux_distribution() is deprecated
# (disabling the check: the whole point of this code is to work around deficiencies
# in the python and debian/devuan distro checking: when these are fixed, this
# code will become redundant and can be binned!)
# (Disabling the pylint error here - this code would only be called if it was
# run as a main script)
    platforminfo = platform.linux_distribution() # pylint: disable=deprecated-method, no-member
    print("platforminfo:")
    print(platforminfo)
# if we got anything vaguely useful, copy it into distinfo_proto
    if platforminfo[0] != '':
        distinfo_proto['ID'] = platforminfo[0]
    if platforminfo[1] != '':
        distinfo_proto['RELEASE'] = platforminfo[1]
# what about the third element?
    print("(before ***** start ******)")
    print(distinfo_proto)
    print("(before ***** end ******)")
# NB: for actual use, we can construct the dictionary in the
# function call (no need to use a pre-constructed dictionary)
#    distinfo_actual=check_debian_plain(distinfo_proto)
    recheck = DebianRecheck(distinfo_proto)
    distinfo_actual = recheck.get_localdistinfo()
    print("(after ***** start ******)")
    print(distinfo_actual)
    print("(after ***** end ******)")

if __name__ == "__main__":
    test()
