#!/usr/bin/python
# -*- coding: utf-8 -*-

#Copyright 2008 Carl Gherardi
#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU Affero General Public License as published by
#the Free Software Foundation, version 3 of the License.
#
#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#GNU General Public License for more details.
#
#You should have received a copy of the GNU Affero General Public License
#along with this program. If not, see <http://www.gnu.org/licenses/>.
#In the "official" distribution you can find the license in
#agpl-3.0.txt in the docs folder of the package.

import Hand
import Tourney
import re
import sys
import traceback
from optparse import OptionParser
import os
import os.path
import xml.dom.minidom
import codecs
from decimal import Decimal
import operator
from xml.dom.minidom import Node
import time
import datetime
from Exceptions import FpdbParseError
import Configuration

import gettext
gettext.install('fpdb')

log = Configuration.get_logger("logging.conf")

import pygtk
import gtk

class HandHistoryConverter():

    READ_CHUNK_SIZE = 10000 # bytes to read at a time from file in tail mode

    # filetype can be "text" or "xml"
    # so far always "text"
    # subclass HHC_xml for xml parsing
    filetype = "text"

    # codepage indicates the encoding of the text file.
    # cp1252 is a safe default
    # "utf_8" is more likely if there are funny characters
    codepage = "cp1252"


    def __init__(self, in_path = '-', out_path = '-', follow=False, index=0, autostart=True, starsArchive=False):
        """\
in_path   (default '-' = sys.stdin)
out_path  (default '-' = sys.stdout)
follow :  whether to tail -f the input"""

        log.info("HandHistory init - %s subclass, in_path '%s'; out_path '%s'" % (self.sitename, in_path, out_path) )
        
        self.index     = index
        self.starsArchive = starsArchive

        self.in_path = in_path
        self.out_path = out_path

        self.processedHands = []
        self.numHands = 0
        self.numErrors = 0

        # Tourney object used to store TourneyInfo when called to deal with a Summary file
        self.tourney = None
        
        if in_path == '-':
            self.in_fh = sys.stdin

        if out_path == '-':
            self.out_fh = sys.stdout
        else:
            # TODO: out_path should be sanity checked.
            out_dir = os.path.dirname(self.out_path)
            if not os.path.isdir(out_dir) and out_dir != '':
                try:
                    os.makedirs(out_dir)
                except: # we get a WindowsError here in Windows.. pretty sure something else for Linux :D
                    log.error("Unable to create output directory %s for HHC!" % out_dir)
                    print "*** ERROR: UNABLE TO CREATE OUTPUT DIRECTORY", out_dir
                    # TODO: pop up a box to allow person to choose output directory?
                    # TODO: shouldn't that be done when we startup, actually?
                else:
                    log.info("Created directory '%s'" % out_dir)
            try:
                self.out_fh = codecs.open(self.out_path, 'w', 'utf8')
            except:
                log.error("out_path %s couldn't be opened" % (self.out_path))
            else:
                log.debug("out_path %s opened as %s" % (self.out_path, self.out_fh))

        self.follow = follow
        self.compiledPlayers   = set()
        self.maxseats  = 10
        
        self.status = True

        self.parsedObjectType = "HH"      #default behaviour : parsing HH files, can be "Summary" if the parsing encounters a Summary File

        if autostart:
            self.start()

    def __str__(self):
        return """
HandHistoryConverter: '%(sitename)s'
    filetype    '%(filetype)s'
    in_path     '%(in_path)s'
    out_path    '%(out_path)s'
    follow      '%(follow)s'
    """ %  locals() 

    def start(self):
        """Process a hand at a time from the input specified by in_path.
If in follow mode, wait for more data to turn up.
Otherwise, finish at EOF.

"""
        while gtk.events_pending():
            gtk.main_iteration(False)

        starttime = time.time()
        if not self.sanityCheck():
            log.warning("Failed sanity check")
            return

        try:
            self.numHands = 0
            self.numErrors = 0
            if self.follow:
                #TODO: See how summary files can be handled on the fly (here they should be rejected as before) 
                log.info("Tailing '%s'" % self.in_path)
                for handText in self.tailHands():
                    try:
                        self.processHand(handText)
                        self.numHands += 1
                    except FpdbParseError, e:
                        self.numErrors += 1
                        log.warning("Failed to convert hand %s" % e.hid)
                        log.warning("Exception msg: '%s'" % str(e))
                        log.debug(handText)
            else:
                handsList = self.allHandsAsList()
                log.info("Parsing %d hands" % len(handsList))
                # Determine if we're dealing with a HH file or a Summary file
                # quick fix : empty files make the handsList[0] fail ==> If empty file, go on with HH parsing
                if len(handsList) == 0 or self.isSummary(handsList[0]) == False:
                    self.parsedObjectType = "HH"
                    for handText in handsList:
                        try:
                            self.processedHands.append(self.processHand(handText))
                        except FpdbParseError, e:
                            self.numErrors += 1
                            log.warning("Failed to convert hand %s" % e.hid)
                            log.warning("Exception msg: '%s'" % str(e))
                            log.debug(handText)
                    self.numHands = len(handsList)
                    endtime = time.time()
                    log.info("Read %d hands (%d failed) in %.3f seconds" % (self.numHands, self.numErrors, endtime - starttime))
                else:
                        self.parsedObjectType = "Summary"
                        summaryParsingStatus = self.readSummaryInfo(handsList)
                        endtime = time.time()
                        if summaryParsingStatus :
                            log.info("Summary file '%s' correctly parsed  (took %.3f seconds)" % (self.in_path, endtime - starttime))
                        else :                            
                            log.warning("Error converting summary file '%s' (took %.3f seconds)" % (self.in_path, endtime - starttime))

        except IOError, ioe:
            log.exception("Error converting '%s'" % self.in_path)
        finally:
            if self.out_fh != sys.stdout:
                self.out_fh.close()


    def tailHands(self):
        """Generator of handTexts from a tailed file:
Tail the in_path file and yield handTexts separated by re_SplitHands.
This requires a regex that greedily groups and matches the 'splitter' between hands,
which it expects to find at self.re_TailSplitHands -- see for e.g. Everleaf.py.

"""
        if self.in_path == '-':
            raise StopIteration
        interval = 1.0 # seconds to sleep between reads for new data
        fd = codecs.open(self.in_path,'r', self.codepage)
        data = ''
        while 1:
            where = fd.tell()
            newdata = fd.read(self.READ_CHUNK_SIZE)
            if not newdata:
                fd_results = os.fstat(fd.fileno())
                try:
                    st_results = os.stat(self.in_path)
                except OSError:
                    st_results = fd_results
                if st_results[1] == fd_results[1]:
                    time.sleep(interval)
                    fd.seek(where)
                else:
                    log.debug("%s changed inode numbers from %d to %d" % (self.in_path, fd_results[1], st_results[1]))
                    fd = codecs.open(self.in_path, 'r', self.codepage)
                    fd.seek(where)
            else:
                # yield hands
                data = data + newdata
                result = self.re_TailSplitHands.split(data)
                result = iter(result)
                data = ''
                # --x       data (- is bit of splitter, x is paragraph)     yield,...,keep
                # [,--,x]    result of re.split (with group around splitter)
                # ,x        our output: yield nothing, keep x
                #
                # --x--x    [,--,x,--,x]  x,x
                # -x--x     [-x,--,x]     x,x
                # x-        [x-]          ,x-
                # x--       [x,--,]       x,--
                # x--x      [x,--,x]      x,x
                # x--x--    [x,--,x,--,]  x,x,--
                
                # The length is always odd.
                # 'odd' indices are always splitters.
                # 'even' indices are always paragraphs or ''
                # We want to discard all the ''
                # We want to discard splitters unless the final item is '' (because the splitter could grow with new data)
                # We want to yield all paragraphs followed by a splitter, i.e. all even indices except the last.
                for para in result:
                    try:
                        result.next()
                        splitter = True
                    except StopIteration:
                        splitter = False
                    if splitter: # para is followed by a splitter
                        if para: yield para # para not ''
                    else:
                        data = para # keep final partial paragraph


    def allHandsAsList(self):
        """Return a list of handtexts in the file at self.in_path"""
        #TODO : any need for this to be generator? e.g. stars support can email one huge file of all hands in a year. Better to read bit by bit than all at once.
        self.readFile()
        self.obs = self.obs.strip()
        self.obs = self.obs.replace('\r\n', '\n')
        if self.starsArchive == True:
            log.debug("Converting starsArchive format to readable")
            m = re.compile('^Hand #\d+', re.MULTILINE)
            self.obs = m.sub('', self.obs)

        if self.obs is None or self.obs == "":
            log.info("Read no hands.")
            return []
        return re.split(self.re_SplitHands,  self.obs)
        
    def processHand(self, handText):
        gametype = self.determineGameType(handText)
        log.debug("gametype %s" % gametype)
        hand = None
        l = None
        if gametype is None: 
            gametype = "unmatched"
            # TODO: not ideal, just trying to not error.
            # TODO: Need to count failed hands.
        else:
            # See if gametype is supported.
            type = gametype['type']
            base = gametype['base']
            limit = gametype['limitType']
            l = [type] + [base] + [limit]
        if l in self.readSupportedGames():
            if gametype['base'] == 'hold':
                log.debug("hand = Hand.HoldemOmahaHand(self, self.sitename, gametype, handtext)")
                hand = Hand.HoldemOmahaHand(self, self.sitename, gametype, handText)
            elif gametype['base'] == 'stud':
                hand = Hand.StudHand(self, self.sitename, gametype, handText)
            elif gametype['base'] == 'draw':
                hand = Hand.DrawHand(self, self.sitename, gametype, handText)
        else:
            log.info("Unsupported game type: %s" % gametype)

        if hand:
            if Configuration.NEWIMPORT == False:
                hand.writeHand(self.out_fh)
            return hand
        else:
            log.info("Unsupported game type: %s" % gametype)
            # TODO: pity we don't know the HID at this stage. Log the entire hand?
            # From the log we can deduce that it is the hand after the one before :)


    # These functions are parse actions that may be overridden by the inheriting class
    # This function should return a list of lists looking like:
    # return [["ring", "hold", "nl"], ["tour", "hold", "nl"]]
    # Showing all supported games limits and types
    
    def readSupportedGames(self): abstract

    # should return a list
    #   type  base limit
    # [ ring, hold, nl   , sb, bb ]
    # Valid types specified in docs/tabledesign.html in Gametypes
    def determineGameType(self, handText): abstract
    """return dict with keys/values:
    'type'       in ('ring', 'tour')
    'limitType'  in ('nl', 'cn', 'pl', 'cp', 'fl')
    'base'       in ('hold', 'stud', 'draw')
    'category'   in ('holdem', 'omahahi', omahahilo', 'razz', 'studhi', 'studhilo', 'fivedraw', '27_1draw', '27_3draw', 'badugi')
    'hilo'       in ('h','l','s')
    'smallBlind' int?
    'bigBlind'   int?
    'smallBet'
    'bigBet'
    'currency'  in ('USD', 'EUR', 'T$', <countrycode>)
or None if we fail to get the info """
    #TODO: which parts are optional/required?

    # Read any of:
    # HID       HandID
    # TABLE     Table name
    # SB        small blind
    # BB        big blind
    # GAMETYPE  gametype
    # YEAR MON DAY HR MIN SEC   datetime
    # BUTTON    button seat number
    def readHandInfo(self, hand): abstract

    # Needs to return a list of lists in the format
    # [['seat#', 'player1name', 'stacksize'] ['seat#', 'player2name', 'stacksize'] [...]]
    def readPlayerStacks(self, hand): abstract
    
    def compilePlayerRegexs(self): abstract
    """Compile dynamic regexes -- these explicitly match known player names and must be updated if a new player joins"""
    
    # Needs to return a MatchObject with group names identifying the streets into the Hand object
    # so groups are called by street names 'PREFLOP', 'FLOP', 'STREET2' etc
    # blinds are done seperately
    def markStreets(self, hand): abstract

    #Needs to return a list in the format
    # ['player1name', 'player2name', ...] where player1name is the sb and player2name is bb, 
    # addtional players are assumed to post a bb oop
    def readBlinds(self, hand): abstract
    def readAntes(self, hand): abstract
    def readBringIn(self, hand): abstract
    def readButton(self, hand): abstract
    def readHeroCards(self, hand): abstract
    def readPlayerCards(self, hand, street): abstract
    def readAction(self, hand, street): abstract
    def readCollectPot(self, hand): abstract
    def readShownCards(self, hand): abstract

    # Some sites do odd stuff that doesn't fall in to the normal HH parsing.
    # e.g., FTP doesn't put mixed game info in the HH, but puts in in the 
    # file name. Use readOther() to clean up those messes.
    def readOther(self, hand): pass
    
    # Some sites don't report the rake. This will be called at the end of the hand after the pot total has been calculated
    # an inheriting class can calculate it for the specific site if need be.
    def getRake(self, hand):
        hand.rake = hand.totalpot - hand.totalcollected #  * Decimal('0.05') # probably not quite right
    
    
    def sanityCheck(self):
        """Check we aren't going to do some stupid things"""
        #TODO: the hhbase stuff needs to be in fpdb_import
        sane = False
        base_w = False
        #~ #Check if hhbase exists and is writable
        #~ #Note: Will not try to create the base HH directory
        #~ if not (os.access(self.hhbase, os.W_OK) and os.path.isdir(self.hhbase)):
            #~ print "HH Sanity Check: Directory hhbase '" + self.hhbase + "' doesn't exist or is not writable"
        #~ else:
            #~ #Check if hhdir exists and is writable
            #~ if not os.path.isdir(self.hhdir):
                #~ # In first pass, dir may not exist. Attempt to create dir
                #~ print "Creating directory: '%s'" % (self.hhdir)
                #~ os.mkdir(self.hhdir)
                #~ sane = True
            #~ elif os.access(self.hhdir, os.W_OK):
                #~ sane = True
            #~ else:
                #~ print "HH Sanity Check: Directory hhdir '" + self.hhdir + "' or its parent directory are not writable"

        # Make sure input and output files are different or we'll overwrite the source file
        if True: # basically.. I don't know
            sane = True
        
        if self.in_path != '-' and self.out_path == self.in_path:
            print "HH Sanity Check: output and input files are the same, check config"
            sane = False


        return sane

    # Functions not necessary to implement in sub class
    def setFileType(self, filetype = "text", codepage='utf8'):
        self.filetype = filetype
        self.codepage = codepage

    #This function doesn't appear to be used
    def splitFileIntoHands(self):
        hands = []
        self.obs = self.obs.strip()
        list = self.re_SplitHands.split(self.obs)
        list.pop() #Last entry is empty
        for l in list:
#           print "'" + l + "'"
            hands = hands + [Hand.Hand(self.sitename, self.gametype, l)]
        # TODO: This looks like it could be replaced with a list comp.. ?
        return hands

    def __listof(self, x):
        if isinstance(x, list) or isinstance(x, tuple):
            return x
        else:
            return [x]

    def readFile(self):
        """Open in_path according to self.codepage. Exceptions caught further up"""
        
        if self.filetype == "text":
            if self.in_path == '-':
                # read from stdin
                log.debug("Reading stdin with %s" % self.codepage) # is this necessary? or possible? or what?
                in_fh = codecs.getreader('cp1252')(sys.stdin)
            else:
                for kodec in self.__listof(self.codepage):
                    #print "trying", kodec
                    try:
                        in_fh = codecs.open(self.in_path, 'r', kodec)
                        in_fh.seek(self.index)
                        log.debug("Opened in_path: '%s' with %s" % (self.in_path, kodec))
                        self.obs = in_fh.read()
                        self.index = in_fh.tell()
                        in_fh.close()
                        break
                    except:
                        pass
                else:
                    print "unable to read file with any codec in list!", self.in_path
        elif self.filetype == "xml":
            doc = xml.dom.minidom.parse(filename)
            self.doc = doc

    def guessMaxSeats(self, hand):
        """Return a guess at maxseats when not specified in HH."""
        # if some other code prior to this has already set it, return it
        if maxseats > 1 and maxseats < 11:
            return maxseats
        mo = self.maxOccSeat(hand)

        if mo == 10: return 10 #that was easy

        if hand.gametype['base'] == 'stud':
            if mo <= 8: return 8
            else: return mo 

        if hand.gametype['base'] == 'draw':
            if mo <= 6: return 6
            else: return mo

        if mo == 2: return 2
        if mo <= 6: return 6
        return 10

    def maxOccSeat(self, hand):
        max = 0
        for player in hand.players:
            if player[0] > max:
                max = player[0]
        return max

    def getStatus(self):
        #TODO: Return a status of true if file processed ok
        return self.status

    def getProcessedHands(self):
        return self.processedHands

    def getProcessedFile(self):
        return self.out_path

    def getLastCharacterRead(self):
        return self.index

    def isSummary(self, topline):
        return " Tournament Summary " in topline

    def getParsedObjectType(self):
        return self.parsedObjectType

    #returns a status (True/False) indicating wether the parsing could be done correctly or not    
    def readSummaryInfo(self, summaryInfoList): abstract
    
    def getTourney(self):
        return self.tourney

    @staticmethod
    def getTableTitleRe(type, table_name=None, tournament = None, table_number=None):
        "Returns string to search in windows titles"
        if type=="tour":
            return "%s.+Table\s%s" % (tournament, table_number)
        else:
            return table_name



def getTableTitleRe(config, sitename, *args, **kwargs):
    "Returns string to search in windows titles for current site"
    return getSiteHhc(config, sitename).getTableTitleRe(*args, **kwargs)

def getSiteHhc(config, sitename):
    "Returns HHC class for current site"
    hhcName = config.supported_sites[sitename].converter
    hhcModule = __import__(hhcName)
    return getattr(hhcModule, hhcName[:-6])
    
    

