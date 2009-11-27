#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#    Copyright 2008, Carl Gherardi
#    
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#    
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#    GNU General Public License for more details.
#    
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
########################################################################

import sys
import logging
from HandHistoryConverter import *

# Fulltilt HH Format converter
# TODO: cat tourno and table to make table name for tournaments

class Fulltilt(HandHistoryConverter):
    
    sitename = "Full Tilt Poker"
    filetype = "text"
    codepage = ["utf-16", "cp1252"]
    siteId   = 1 # Needs to match id entry in Sites database

    # Static regexes
    re_GameInfo     = re.compile('''.*\#(?P<HID>[0-9]+):\s
                                    (?:(?P<TOURNAMENT>.+)\s\((?P<TOURNO>\d+)\),\s)?
                                    .+
                                    -\s(?P<CURRENCY>\$|)?
                                    (?P<SB>[.0-9]+)/
                                    \$?(?P<BB>[.0-9]+)\s
                                    (Ante\s\$?(?P<ANTE>[.0-9]+)\s)?-\s
                                    \$?(?P<CAP>[.0-9]+\sCap\s)?
                                    (?P<LIMIT>(No\sLimit|Pot\sLimit|Limit))?\s
                                    (?P<GAME>(Hold\'em|Omaha\sHi|Omaha\sH/L|7\sCard\sStud|Stud\sH/L|Razz|Stud\sHi))
                                 ''', re.VERBOSE)
    re_SplitHands   = re.compile(r"\n\n+")
    re_TailSplitHands   = re.compile(r"(\n\n+)")
    re_HandInfo     = re.compile(r'''.*\#(?P<HID>[0-9]+):\s
                                    (?:(?P<TOURNAMENT>.+)\s\((?P<TOURNO>\d+)\),\s)?
                                    (Table|Match)\s 
                                    (?P<PLAY>Play\sChip\s|PC)?
                                    (?P<TABLE>[-\s\da-zA-Z]+)\s
                                    (\((?P<TABLEATTRIBUTES>.+)\)\s)?-\s
                                    \$?(?P<SB>[.0-9]+)/\$?(?P<BB>[.0-9]+)\s(Ante\s\$?(?P<ANTE>[.0-9]+)\s)?-\s
                                    \$?(?P<CAP>[.0-9]+\sCap\s)?
                                    (?P<GAMETYPE>[a-zA-Z\/\'\s]+)\s-\s
                                    (?P<DATETIME>\d+:\d+:\d+\s\w+\s-\s\d+/\d+/\d+)\s?
                                    (?P<PARTIAL>\(partial\))?\n
                                    (?:.*?\n(?P<CANCELLED>Hand\s\#(?P=HID)\shas\sbeen\scanceled))?
                                 ''', re.VERBOSE|re.DOTALL)
    re_TourneyExtraInfo  = re.compile('''(((?P<TOURNEY_NAME>[^$]+)?
                                         (?P<CURRENCY>\$)?(?P<BUYIN>[.0-9]+)?\s*\+\s*\$?(?P<FEE>[.0-9]+)?
                                         (\s(?P<SPECIAL>(KO|Heads\sUp|Matrix\s\dx|Rebuy|Madness)))?
                                         (\s(?P<SHOOTOUT>Shootout))?
                                         (\s(?P<SNG>Sit\s&\sGo))?
                                         (\s\((?P<TURBO>Turbo)\))?)|(?P<UNREADABLE_INFO>.+))
                                    ''', re.VERBOSE)
    re_Button       = re.compile('^The button is in seat #(?P<BUTTON>\d+)', re.MULTILINE)
    re_PlayerInfo   = re.compile('Seat (?P<SEAT>[0-9]+): (?P<PNAME>.*) \(\$(?P<CASH>[,.0-9]+)\)$', re.MULTILINE)
    re_TourneyPlayerInfo   = re.compile('Seat (?P<SEAT>[0-9]+): (?P<PNAME>.*) \(\$?(?P<CASH>[,.0-9]+)\)', re.MULTILINE)
    re_Board        = re.compile(r"\[(?P<CARDS>.+)\]")

    #static regex for tourney purpose
    re_TourneyInfo  = re.compile('''Tournament\sSummary\s
                                    (?P<TOURNAMENT_NAME>[^$(]+)?\s*
                                    ((?P<CURRENCY>\$|)?(?P<BUYIN>[.0-9]+)\s*\+\s*\$?(?P<FEE>[.0-9]+)\s)?
                                    ((?P<SPECIAL>(KO|Heads\sUp|Matrix\s\dx|Rebuy|Madness))\s)?
                                    ((?P<SHOOTOUT>Shootout)\s)?
                                    ((?P<SNG>Sit\s&\sGo)\s)?
                                    (\((?P<TURBO1>Turbo)\)\s)?
                                    \((?P<TOURNO>\d+)\)\s
                                    ((?P<MATCHNO>Match\s\d)\s)?
                                    (?P<GAME>(Hold\'em|Omaha\sHi|Omaha\sH/L|7\sCard\sStud|Stud\sH/L|Razz|Stud\sHi))\s
                                    (\((?P<TURBO2>Turbo)\)\s)?
                                    (?P<LIMIT>(No\sLimit|Pot\sLimit|Limit))?
                                ''', re.VERBOSE)
    re_TourneyBuyInFee      = re.compile("Buy-In: (?P<BUYIN_CURRENCY>\$|)?(?P<BUYIN>[.0-9]+) \+ \$?(?P<FEE>[.0-9]+)")
    re_TourneyBuyInChips    = re.compile("Buy-In Chips: (?P<BUYINCHIPS>\d+)")
    re_TourneyEntries       = re.compile("(?P<ENTRIES>\d+) Entries")
    re_TourneyPrizePool     = re.compile("Total Prize Pool: (?P<PRIZEPOOL_CURRENCY>\$|)?(?P<PRIZEPOOL>[.,0-9]+)")
    re_TourneyRebuyAmount   = re.compile("Rebuy: (?P<REBUY_CURRENCY>\$|)?(?P<REBUY_AMOUNT>[.,0-9]+)")
    re_TourneyAddOnAmount   = re.compile("Add-On: (?P<ADDON_CURRENCY>\$|)?(?P<ADDON_AMOUNT>[.,0-9]+)")
    re_TourneyRebuyCount    = re.compile("performed (?P<REBUY_COUNT>\d+) Rebuy")
    re_TourneyAddOnCount    = re.compile("performed (?P<ADDON_COUNT>\d+) Add-On")
    re_TourneyRebuysTotal   = re.compile("Total Rebuys: (?P<REBUY_TOTAL>\d+)")
    re_TourneyAddOnsTotal   = re.compile("Total Add-Ons: (?P<ADDONS_TOTAL>\d+)")
    re_TourneyRebuyChips    = re.compile("Rebuy Chips: (?P<REBUY_CHIPS>\d+)")
    re_TourneyAddOnChips    = re.compile("Add-On Chips: (?P<ADDON_CHIPS>\d+)")
    re_TourneyKOBounty      = re.compile("Knockout Bounty: (?P<KO_BOUNTY_CURRENCY>\$|)?(?P<KO_BOUNTY_AMOUNT>[.,0-9]+)")
    re_TourneyCountKO       = re.compile("received (?P<COUNT_KO>\d+) Knockout Bounty Award(s)?")
    re_TourneyTimeInfo      = re.compile("Tournament started: (?P<STARTTIME>.*)\nTournament ((?P<IN_PROGRESS>is still in progress)?|(finished:(?P<ENDTIME>.*))?)$")

    re_TourneyPlayersSummary = re.compile("^(?P<RANK>(Still Playing|\d+))( - |: )(?P<PNAME>[^\n,]+)(, )?(?P<WINNING_CURRENCY>\$|)?(?P<WINNING>[.\d]+)?", re.MULTILINE)
    re_TourneyHeroFinishingP = re.compile("(?P<HERO_NAME>.*) finished in (?P<HERO_FINISHING_POS>\d+)(st|nd|rd|th) place")

#TODO: See if we need to deal with play money tourney summaries -- Not right now (they shouldn't pass the re_TourneyInfo)
##Full Tilt Poker Tournament Summary 250 Play Money Sit & Go (102909471) Hold'em No Limit
##Buy-In: 250 Play Chips + 0 Play Chips
##Buy-In Chips: 1500
##6 Entries
##Total Prize Pool: 1,500 Play Chips

# These regexes are for FTP only
    re_Mixed        = re.compile(r'\s\-\s(?P<MIXED>HA|HORSE|HOSE)\s\-\s', re.VERBOSE)
    re_Max          = re.compile("(?P<MAX>\d+)( max)?", re.MULTILINE)
    # NB: if we ever match "Full Tilt Poker" we should also match "FullTiltPoker", which PT Stud erroneously exports.




    mixes = { 'HORSE': 'horse', '7-Game': '7game', 'HOSE': 'hose', 'HA': 'ha'}


    def compilePlayerRegexs(self,  hand):
        players = set([player[1] for player in hand.players])
        if not players <= self.compiledPlayers: # x <= y means 'x is subset of y'
            # we need to recompile the player regexs.
            self.compiledPlayers = players
            player_re = "(?P<PNAME>" + "|".join(map(re.escape, players)) + ")"
            logging.debug("player_re: " + player_re)
            self.re_PostSB           = re.compile(r"^%s posts the small blind of \$?(?P<SB>[.0-9]+)" %  player_re, re.MULTILINE)
            self.re_PostBB           = re.compile(r"^%s posts (the big blind of )?\$?(?P<BB>[.0-9]+)" % player_re, re.MULTILINE)
            self.re_Antes            = re.compile(r"^%s antes \$?(?P<ANTE>[.0-9]+)" % player_re, re.MULTILINE)
            self.re_BringIn          = re.compile(r"^%s brings in for \$?(?P<BRINGIN>[.0-9]+)" % player_re, re.MULTILINE)
            self.re_PostBoth         = re.compile(r"^%s posts small \& big blinds \[\$? (?P<SBBB>[.0-9]+)" % player_re, re.MULTILINE)
            self.re_HeroCards        = re.compile(r"^Dealt to %s(?: \[(?P<OLDCARDS>.+?)\])?( \[(?P<NEWCARDS>.+?)\])" % player_re, re.MULTILINE)
            self.re_Action           = re.compile(r"^%s(?P<ATYPE> bets| checks| raises to| completes it to| calls| folds)( \$?(?P<BET>[.,\d]+))?" % player_re, re.MULTILINE)
            self.re_ShowdownAction   = re.compile(r"^%s shows \[(?P<CARDS>.*)\]" % player_re, re.MULTILINE)
            self.re_CollectPot       = re.compile(r"^Seat (?P<SEAT>[0-9]+): %s (\(button\) |\(small blind\) |\(big blind\) )?(collected|showed \[.*\] and won) \(\$?(?P<POT>[.,\d]+)\)(, mucked| with.*)" % player_re, re.MULTILINE)
            self.re_SitsOut          = re.compile(r"^%s sits out" % player_re, re.MULTILINE)
            self.re_ShownCards       = re.compile(r"^Seat (?P<SEAT>[0-9]+): %s \(.*\) showed \[(?P<CARDS>.*)\].*" % player_re, re.MULTILINE)

    def readSupportedGames(self):
        return [["ring", "hold", "nl"], 
                ["ring", "hold", "pl"],
                ["ring", "hold", "fl"],
                ["ring", "hold", "cn"],

                ["ring", "stud", "fl"],

                ["tour", "hold", "nl"],
                ["tour", "hold", "pl"],
                ["tour", "hold", "fl"],

                ["tour", "stud", "fl"],
               ]

    def determineGameType(self, handText):
        # Full Tilt Poker Game #10777181585: Table Deerfly (deep 6) - $0.01/$0.02 - Pot Limit Omaha Hi - 2:24:44 ET - 2009/02/22
        # Full Tilt Poker Game #10773265574: Table Butte (6 max) - $0.01/$0.02 - Pot Limit Hold'em - 21:33:46 ET - 2009/02/21
        # Full Tilt Poker Game #9403951181: Table CR - tay - $0.05/$0.10 - No Limit Hold'em - 9:40:20 ET - 2008/12/09
        # Full Tilt Poker Game #10809877615: Table Danville - $0.50/$1 Ante $0.10 - Limit Razz - 21:47:27 ET - 2009/02/23
        info = {'type':'ring'}
        
        m = self.re_GameInfo.search(handText)
        if not m: 
            return None
        mg = m.groupdict()
        # translations from captured groups to our info strings
        limits = { 'No Limit':'nl', 'Pot Limit':'pl', 'Limit':'fl' }
        games = {              # base, category
                  "Hold'em" : ('hold','holdem'), 
                 'Omaha Hi' : ('hold','omahahi'), 
                'Omaha H/L' : ('hold','omahahilo'),
                     'Razz' : ('stud','razz'), 
                  'Stud Hi' : ('stud','studhi'), 
                 'Stud H/L' : ('stud','studhilo')
               }
        currencies = { u' €':'EUR', '$':'USD', '':'T$' }
        if mg['CAP']:
            info['limitType'] = 'cn'
        else:
            info['limitType'] = limits[mg['LIMIT']]
        info['sb'] = mg['SB']
        info['bb'] = mg['BB']
        if mg['GAME'] is not None:
            (info['base'], info['category']) = games[mg['GAME']]
        if mg['CURRENCY'] is not None:
            info['currency'] = currencies[mg['CURRENCY']]
        if mg['TOURNO'] is None:  info['type'] = "ring"
        else:                     info['type'] = "tour"
        # NB: SB, BB must be interpreted as blinds or bets depending on limit type.
#        if info['type'] == "tour": return None # importer is screwed on tournies, pass on those hands so we don't interrupt other autoimporting
        return info

    def readHandInfo(self, hand):
        m =  self.re_HandInfo.search(hand.handText)
        if m is None:
            logging.info("Didn't match re_HandInfo")
            logging.info(hand.handText)
            return None
        hand.handid = m.group('HID')
        hand.tablename = m.group('TABLE')
        hand.starttime = datetime.datetime.strptime(m.group('DATETIME'), "%H:%M:%S ET - %Y/%m/%d")

        if m.group("CANCELLED") or m.group("PARTIAL"):
            raise FpdbParseError(hid=m.group('HID'))

        if m.group('TABLEATTRIBUTES'):
            m2 = self.re_Max.search(m.group('TABLEATTRIBUTES'))
            if m2: hand.maxseats = int(m2.group('MAX'))

        hand.tourNo = m.group('TOURNO')
        if m.group('PLAY') is not None:
            hand.gametype['currency'] = 'play'
            
        # Done: if there's a way to figure these out, we should.. otherwise we have to stuff it with unknowns
        if m.group('TOURNAMENT') is not None:
            n = self.re_TourneyExtraInfo.search(m.group('TOURNAMENT'))
            if n.group('UNREADABLE_INFO') is not None:
                hand.tourneyComment = n.group('UNREADABLE_INFO') 
            else:
                hand.tourneyComment = n.group('TOURNEY_NAME')   # can be None
                if (n.group('CURRENCY') is not None and n.group('BUYIN') is not None and n.group('FEE') is not None):
                    hand.buyin = "%s%s+%s%s" %(n.group('CURRENCY'), n.group('BUYIN'), n.group('CURRENCY'), n.group('FEE'))
                if n.group('TURBO') is not None :
                    hand.speed = "Turbo"
                if n.group('SPECIAL') is not None :
                    special = n.group('SPECIAL')
                    if special == "Rebuy":
                        hand.isRebuy = True
                    if special == "KO":
                        hand.isKO = True
                    if special == "Head's Up":
                        hand.isHU = True
                    if re.search("Matrix", special):
                        hand.isMatrix = True
                    if special == "Shootout":
                        hand.isShootout = True
                 

        if hand.buyin is None:
            hand.buyin = "$0.00+$0.00"
        if hand.level is None:
            hand.level = "0"            

# These work, but the info is already in the Hand class - should be used for tourneys though.
#       m.group('SB')
#       m.group('BB')
#       m.group('GAMETYPE')

# Stars format (Nov 10 2008): 2008/11/07 12:38:49 CET [2008/11/07 7:38:49 ET]
# or                        : 2008/11/07 12:38:49 ET
# Not getting it in my HH files yet, so using
# 2008/11/10 3:58:52 ET
#TODO: Do conversion from GMT to ET
#TODO: Need some date functions to convert to different timezones (Date::Manip for perl rocked for this)
        #hand.starttime = "%d/%02d/%02d %d:%02d:%02d ET" %(int(m.group('YEAR')), int(m.group('MON')), int(m.group('DAY')),
                            ##int(m.group('HR')), int(m.group('MIN')), int(m.group('SEC')))
#FIXME:        hand.buttonpos = int(m.group('BUTTON'))

    def readPlayerStacks(self, hand):
        if hand.gametype['type'] == "ring" :
            m = self.re_PlayerInfo.finditer(hand.handText)
        else:   #if hand.gametype['type'] == "tour"
            m = self.re_TourneyPlayerInfo.finditer(hand.handText)

        players = []
        for a in m:
            hand.addPlayer(int(a.group('SEAT')), a.group('PNAME'), a.group('CASH'))

    def markStreets(self, hand):
        # PREFLOP = ** Dealing down cards **

        if hand.gametype['base'] == 'hold':
            m =  re.search(r"\*\*\* HOLE CARDS \*\*\*(?P<PREFLOP>.+(?=\*\*\* FLOP \*\*\*)|.+)"
                       r"(\*\*\* FLOP \*\*\*(?P<FLOP> \[\S\S \S\S \S\S\].+(?=\*\*\* TURN \*\*\*)|.+))?"
                       r"(\*\*\* TURN \*\*\* \[\S\S \S\S \S\S] (?P<TURN>\[\S\S\].+(?=\*\*\* RIVER \*\*\*)|.+))?"
                       r"(\*\*\* RIVER \*\*\* \[\S\S \S\S \S\S \S\S] (?P<RIVER>\[\S\S\].+))?", hand.handText,re.DOTALL)
        elif hand.gametype['base'] == "stud": # or should this be gametype['category'] == 'razz'
            m =  re.search(r"(?P<ANTES>.+(?=\*\*\* 3RD STREET \*\*\*)|.+)"
                           r"(\*\*\* 3RD STREET \*\*\*(?P<THIRD>.+(?=\*\*\* 4TH STREET \*\*\*)|.+))?"
                           r"(\*\*\* 4TH STREET \*\*\*(?P<FOURTH>.+(?=\*\*\* 5TH STREET \*\*\*)|.+))?"
                           r"(\*\*\* 5TH STREET \*\*\*(?P<FIFTH>.+(?=\*\*\* 6TH STREET \*\*\*)|.+))?"
                           r"(\*\*\* 6TH STREET \*\*\*(?P<SIXTH>.+(?=\*\*\* 7TH STREET \*\*\*)|.+))?"
                           r"(\*\*\* 7TH STREET \*\*\*(?P<SEVENTH>.+))?", hand.handText,re.DOTALL)
        hand.addStreets(m)

    def readCommunityCards(self, hand, street): # street has been matched by markStreets, so exists in this hand
        if street in ('FLOP','TURN','RIVER'):   # a list of streets which get dealt community cards (i.e. all but PREFLOP)
            #print "DEBUG readCommunityCards:", street, hand.streets.group(street)
            m = self.re_Board.search(hand.streets[street])
            hand.setCommunityCards(street, m.group('CARDS').split(' '))


    def readBlinds(self, hand):
        try:
            m = self.re_PostSB.search(hand.handText)
            hand.addBlind(m.group('PNAME'), 'small blind', m.group('SB'))
        except: # no small blind
            hand.addBlind(None, None, None)
        for a in self.re_PostBB.finditer(hand.handText):
            hand.addBlind(a.group('PNAME'), 'big blind', a.group('BB'))
        for a in self.re_PostBoth.finditer(hand.handText):
            hand.addBlind(a.group('PNAME'), 'small & big blinds', a.group('SBBB'))

    def readAntes(self, hand):
        logging.debug("reading antes")
        m = self.re_Antes.finditer(hand.handText)
        for player in m:
            logging.debug("hand.addAnte(%s,%s)" %(player.group('PNAME'), player.group('ANTE')))
#            if player.group() != 
            hand.addAnte(player.group('PNAME'), player.group('ANTE'))

    def readBringIn(self, hand):
        m = self.re_BringIn.search(hand.handText,re.DOTALL)
        if m:
            logging.debug("Player bringing in: %s for %s" %(m.group('PNAME'),  m.group('BRINGIN')))
            hand.addBringIn(m.group('PNAME'),  m.group('BRINGIN'))
        else:
            logging.warning("No bringin found, handid =%s" % hand.handid)

    def readButton(self, hand):
        hand.buttonpos = int(self.re_Button.search(hand.handText).group('BUTTON'))

    def readHeroCards(self, hand):
#    streets PREFLOP, PREDRAW, and THIRD are special cases beacause
#    we need to grab hero's cards
        for street in ('PREFLOP', 'DEAL'):
            if street in hand.streets.keys():
                m = self.re_HeroCards.finditer(hand.streets[street])
                for found in m:
#                    if m == None:
#                        hand.involved = False
#                    else:
                    hand.hero = found.group('PNAME')
                    newcards = found.group('NEWCARDS').split(' ')
                    hand.addHoleCards(street, hand.hero, closed=newcards, shown=False, mucked=False, dealt=True)

        for street, text in hand.streets.iteritems():
            if not text or street in ('PREFLOP', 'DEAL'): continue  # already done these
            m = self.re_HeroCards.finditer(hand.streets[street])
            for found in m:
                player = found.group('PNAME')
                if found.group('NEWCARDS') is None:
                    newcards = []
                else:
                    newcards = found.group('NEWCARDS').split(' ')
                if found.group('OLDCARDS') is None:
                    oldcards = []
                else:
                    oldcards = found.group('OLDCARDS').split(' ')

                if street == 'THIRD' and len(oldcards) == 2: # hero in stud game
                    hand.hero = player
                    hand.dealt.add(player) # need this for stud??
                    hand.addHoleCards(street, player, closed=oldcards, open=newcards, shown=False, mucked=False, dealt=False)
                else:
                    hand.addHoleCards(street, player, open=newcards, closed=oldcards, shown=False, mucked=False, dealt=False)


    def readAction(self, hand, street):
        m = self.re_Action.finditer(hand.streets[street])
        for action in m:
            if action.group('ATYPE') == ' raises to':
                hand.addRaiseTo( street, action.group('PNAME'), action.group('BET') )
            elif action.group('ATYPE') == ' completes it to':
                hand.addComplete( street, action.group('PNAME'), action.group('BET') )
            elif action.group('ATYPE') == ' calls':
                hand.addCall( street, action.group('PNAME'), action.group('BET') )
            elif action.group('ATYPE') == ' bets':
                hand.addBet( street, action.group('PNAME'), action.group('BET') )
            elif action.group('ATYPE') == ' folds':
                hand.addFold( street, action.group('PNAME'))
            elif action.group('ATYPE') == ' checks':
                hand.addCheck( street, action.group('PNAME'))
            else:
                print "FullTilt: DEBUG: unimplemented readAction: '%s' '%s'" %(action.group('PNAME'),action.group('ATYPE'),)


    def readShowdownActions(self, hand):
        for shows in self.re_ShowdownAction.finditer(hand.handText):
            cards = shows.group('CARDS')
            cards = cards.split(' ')
            hand.addShownCards(cards, shows.group('PNAME'))

    def readCollectPot(self,hand):
        for m in self.re_CollectPot.finditer(hand.handText):
            hand.addCollectPot(player=m.group('PNAME'),pot=re.sub(u',',u'',m.group('POT')))

    def readShownCards(self,hand):
        for m in self.re_ShownCards.finditer(hand.handText):
            if m.group('CARDS') is not None:
                cards = m.group('CARDS')
                cards = cards.split(' ')
                hand.addShownCards(cards=cards, player=m.group('PNAME'))

    def guessMaxSeats(self, hand):
        """Return a guess at max_seats when not specified in HH."""
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
        return 9

    def readOther(self, hand):
        m = self.re_Mixed.search(self.in_path)
        if m is None:
            hand.mixed = None
        else:
            hand.mixed = self.mixes[m.groupdict()['MIXED']]

    def readSummaryInfo(self, summaryInfoList):
        starttime = time.time()
        self.status = True

        m = re.search("Tournament Summary", summaryInfoList[0])
        if m:
            # info list should be 2 lines : Tourney infos & Finsihing postions with winnings
            if (len(summaryInfoList) != 2 ):
                log.info("Too many lines (%d) in file '%s' : '%s'" % (len(summaryInfoList), self.in_path, summaryInfoList) )
                self.status = False
            else:
                self.tourney = Tourney.Tourney(sitename = self.sitename, gametype = None, summaryText = summaryInfoList, builtFrom = "HHC")
                self.status = self.getPlayersPositionsAndWinnings(self.tourney)
                if self.status == True :
                    self.status = self.determineTourneyType(self.tourney)
                    #print self.tourney
                else:
                    log.info("Parsing NOK : rejected")
        else:
            log.info( "This is not a summary file : '%s'" % (self.in_path) )
            self.status = False

        return self.status

    def determineTourneyType(self, tourney):
        info = {'type':'tour'}
        tourneyText = tourney.summaryText[0]
        #print "Examine : '%s'" %(tourneyText)
        
        m = self.re_TourneyInfo.search(tourneyText)
        if not m: 
            log.info( "determineTourneyType : Parsing NOK" )
            return False
        mg = m.groupdict()
        #print mg
        
        # translations from captured groups to our info strings
        limits = { 'No Limit':'nl', 'Pot Limit':'pl', 'Limit':'fl' }
        games = {              # base, category
                  "Hold'em" : ('hold','holdem'), 
                 'Omaha Hi' : ('hold','omahahi'), 
                'Omaha H/L' : ('hold','omahahilo'),
                     'Razz' : ('stud','razz'), 
                  'Stud Hi' : ('stud','studhi'), 
                 'Stud H/L' : ('stud','studhilo')
               }
        currencies = { u' €':'EUR', '$':'USD', '':'T$' }
        info['limitType'] = limits[mg['LIMIT']]
        if mg['GAME'] is not None:
            (info['base'], info['category']) = games[mg['GAME']]
        if mg['CURRENCY'] is not None:
            info['currency'] = currencies[mg['CURRENCY']]
        if mg['TOURNO'] is None:
            info['type'] = "ring"
        else:
            info['type'] = "tour"
        # NB: SB, BB must be interpreted as blinds or bets depending on limit type.

        # Info is now ready to be copied in the tourney object        
        tourney.gametype = info

        # Additional info can be stored in the tourney object
        if mg['BUYIN'] is not None:
            tourney.buyin = 100*Decimal(re.sub(u',', u'', "%s" % mg['BUYIN']))
            tourney.fee = 0 
        if mg['FEE'] is not None:
            tourney.fee = 100*Decimal(re.sub(u',', u'', "%s" % mg['FEE']))
        if mg['TOURNAMENT_NAME'] is not None:
            # Tournament Name can have a trailing space at the end (depending on the tournament description)
            tourney.tourneyName = mg['TOURNAMENT_NAME'].rstrip()
        if mg['SPECIAL'] is not None:
            special = mg['SPECIAL']
            if special == "KO":
                tourney.isKO = True
            if special == "Heads Up":
                tourney.isHU = True
                tourney.maxseats = 2
            if re.search("Matrix", special):
                tourney.isMatrix = True
            if special == "Rebuy":
                tourney.isRebuy = True
            if special == "Madness":
                tourney.tourneyComment = "Madness"
        if mg['SHOOTOUT'] is not None:
            tourney.isShootout = True
        if mg['TURBO1'] is not None or mg['TURBO2'] is not None :
            tourney.speed = "Turbo"
        if mg['TOURNO'] is not None:
            tourney.tourNo = mg['TOURNO']
        else:
            log.info( "Unable to get a valid Tournament ID -- File rejected" )
            return False
        if tourney.isMatrix:
            if mg['MATCHNO'] is not None:
                tourney.matrixMatchId = mg['MATCHNO']
            else:
                tourney.matrixMatchId = 0


        # Get BuyIn/Fee
        # Try and deal with the different cases that can occur :
        # - No buy-in/fee can be on the first line (freerolls, Satellites sometimes ?, ...) but appears in the rest of the description ==> use this one
        # - Buy-In/Fee from the first line differs from the rest of the description : 
        #   * OK in matrix tourneys (global buy-in dispatched between the different matches)
        #   * NOK otherwise ==> issue a warning and store specific data as if were a Matrix Tourney
        # - If no buy-in/fee can be found : assume it's a freeroll
        m = self.re_TourneyBuyInFee.search(tourneyText)
        if m is not None:
            mg = m.groupdict()
            if tourney.isMatrix :
                if mg['BUYIN'] is not None:
                    tourney.subTourneyBuyin = 100*Decimal(re.sub(u',', u'', "%s" % mg['BUYIN']))
                    tourney.subTourneyFee = 0
                if mg['FEE'] is not None:
                    tourney.subTourneyFee = 100*Decimal(re.sub(u',', u'', "%s" % mg['FEE']))
            else :
                if mg['BUYIN'] is not None:
                    if tourney.buyin is None:
                        tourney.buyin = 100*Decimal(re.sub(u',', u'', "%s" % mg['BUYIN']))
                    else :
                        if 100*Decimal(re.sub(u',', u'', "%s" % mg['BUYIN'])) != tourney.buyin:
                            log.error( "Conflict between buyins read in topline (%s) and in BuyIn field (%s)" % (touney.buyin, 100*Decimal(re.sub(u',', u'', "%s" % mg['BUYIN']))) )
                            tourney.subTourneyBuyin = 100*Decimal(re.sub(u',', u'', "%s" % mg['BUYIN']))
                if mg['FEE'] is not None:
                    if tourney.fee is None:
                        tourney.fee = 100*Decimal(re.sub(u',', u'', "%s" % mg['FEE']))
                    else :
                        if 100*Decimal(re.sub(u',', u'', "%s" % mg['FEE'])) != tourney.fee:
                            log.error( "Conflict between fees read in topline (%s) and in BuyIn field (%s)" % (touney.fee, 100*Decimal(re.sub(u',', u'', "%s" % mg['FEE']))) )
                            tourney.subTourneyFee = 100*Decimal(re.sub(u',', u'', "%s" % mg['FEE']))

        if tourney.buyin is None:
            log.info( "Unable to affect a buyin to this tournament : assume it's a freeroll" )
            tourney.buyin = 0
            tourney.fee = 0
        else:
            if tourney.fee is None:
                #print "Couldn't initialize fee, even though buyin went OK : assume there are no fees"
                tourney.fee = 0

        #Get single line infos
        dictRegex = {   "BUYINCHIPS"        : self.re_TourneyBuyInChips,
                        "ENTRIES"           : self.re_TourneyEntries,
                        "PRIZEPOOL"         : self.re_TourneyPrizePool,
                        "REBUY_AMOUNT"      : self.re_TourneyRebuyAmount,
                        "ADDON_AMOUNT"      : self.re_TourneyAddOnAmount,
                        "REBUY_TOTAL"       : self.re_TourneyRebuysTotal,
                        "ADDONS_TOTAL"      : self.re_TourneyAddOnsTotal,
                        "REBUY_CHIPS"       : self.re_TourneyRebuyChips,
                        "ADDON_CHIPS"       : self.re_TourneyAddOnChips,
                        "STARTTIME"         : self.re_TourneyTimeInfo,
                        "KO_BOUNTY_AMOUNT"  : self.re_TourneyKOBounty,
                    }


        dictHolders = { "BUYINCHIPS"        : "buyInChips",
                        "ENTRIES"           : "entries",
                        "PRIZEPOOL"         : "prizepool",
                        "REBUY_AMOUNT"      : "rebuyAmount",
                        "ADDON_AMOUNT"      : "addOnAmount",
                        "REBUY_TOTAL"       : "totalRebuys",
                        "ADDONS_TOTAL"      : "totalAddOns",
                        "REBUY_CHIPS"       : "rebuyChips",
                        "ADDON_CHIPS"       : "addOnChips",
                        "STARTTIME"         : "starttime",
                        "KO_BOUNTY_AMOUNT"  : "koBounty"
                    }

        mg = {}     # After the loop, mg will contain all the matching groups, including the ones that have not been used, like ENDTIME and IN-PROGRESS
        for data in dictRegex:
            m = dictRegex.get(data).search(tourneyText)
            if m is not None:
                mg.update(m.groupdict())
                setattr(tourney, dictHolders[data], mg[data])

        if mg['IN_PROGRESS'] is not None or mg['ENDTIME'] is not None:
            # Assign endtime to tourney (if None, that's ok, it's because the tourney wans't over over when the summary file was produced)
            tourney.endtime = mg['ENDTIME']

        # Deal with hero specific information
        if tourney.hero is not None :
            m = self.re_TourneyRebuyCount.search(tourneyText)
            if m is not None:
                mg = m.groupdict()
                if mg['REBUY_COUNT'] is not None :
                    tourney.countRebuys.update( { tourney.hero : Decimal(mg['REBUY_COUNT']) } )
            m = self.re_TourneyAddOnCount.search(tourneyText)
            if m is not None:
                mg = m.groupdict()
                if mg['ADDON_COUNT'] is not None :
                    tourney.countAddOns.update( { tourney.hero : Decimal(mg['ADDON_COUNT']) } )
            m = self.re_TourneyCountKO.search(tourneyText)
            if m is not None:
                mg = m.groupdict()
                if mg['COUNT_KO'] is not None :
                    tourney.countKO.update( { tourney.hero : Decimal(mg['COUNT_KO']) } )

        # Deal with money amounts
        tourney.koBounty    = 100*Decimal(re.sub(u',', u'', "%s" % tourney.koBounty))
        tourney.prizepool   = 100*Decimal(re.sub(u',', u'', "%s" % tourney.prizepool))
        tourney.rebuyAmount = 100*Decimal(re.sub(u',', u'', "%s" % tourney.rebuyAmount))
        tourney.addOnAmount = 100*Decimal(re.sub(u',', u'', "%s" % tourney.addOnAmount))
        
        # Calculate payin amounts and update winnings -- not possible to take into account nb of rebuys, addons or Knockouts for other players than hero on FTP
        for p in tourney.players :
            tourney.payinAmounts[p] = tourney.buyin + tourney.fee + (tourney.rebuyAmount * tourney.countRebuys[p]) + (tourney.addOnAmount * tourney.countAddOns[p])
            #print " player %s : payinAmount = %d" %( p, tourney.payinAmounts[p])
            if tourney.isKO :
                #tourney.incrementPlayerWinnings(tourney.players[p], Decimal(tourney.koBounty)*Decimal(tourney.countKO[p]))
                tourney.winnings[p] += Decimal(tourney.koBounty)*Decimal(tourney.countKO[p])
                #print "player %s : winnings %d" % (p, tourney.winnings[p])
  
                    

        #print mg
        return True

    def getPlayersPositionsAndWinnings(self, tourney):
        playersText = tourney.summaryText[1]
        #print "Examine : '%s'" %(playersText)
        m = self.re_TourneyPlayersSummary.finditer(playersText)

        for a in m:
            if a.group('PNAME') is not None and a.group('RANK') is not None:
                if a.group('RANK') == "Still Playing":
                    rank = -1
                else:
                    rank = Decimal(a.group('RANK'))

                if a.group('WINNING') is not None:
                    winnings = 100*Decimal(re.sub(u',', u'', "%s" % a.group('WINNING')))
                else:
                    winnings = "0"

                tourney.addPlayer(rank, a.group('PNAME'), winnings, 0, 0, 0, 0)
            else:
                print "FullTilt: Player finishing stats unreadable : %s" % a

        # Find Hero
        n = self.re_TourneyHeroFinishingP.search(playersText)
        if n is not None:
            heroName = n.group('HERO_NAME')
            tourney.hero = heroName
            # Is this really useful ?
            if heroName not in tourney.finishPositions:
                print "FullTilt:", heroName, "not found in tourney.finishPositions ..."
            elif (tourney.finishPositions[heroName] != Decimal(n.group('HERO_FINISHING_POS'))):            
                print "FullTilt: Bad parsing : finish position incoherent : %s / %s" % (tourney.finishPositions[heroName], n.group('HERO_FINISHING_POS'))

        return True

if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-i", "--input", dest="ipath", help="parse input hand history", default="regression-test-files/fulltilt/razz/FT20090223 Danville - $0.50-$1 Ante $0.10 - Limit Razz.txt")
    parser.add_option("-o", "--output", dest="opath", help="output translation to", default="-")
    parser.add_option("-f", "--follow", dest="follow", help="follow (tail -f) the input", action="store_true", default=False)
    parser.add_option("-q", "--quiet",
                  action="store_const", const=logging.CRITICAL, dest="verbosity", default=logging.INFO)
    parser.add_option("-v", "--verbose",
                  action="store_const", const=logging.INFO, dest="verbosity")
    parser.add_option("--vv",
                  action="store_const", const=logging.DEBUG, dest="verbosity")

    (options, args) = parser.parse_args()

    e = Fulltilt(in_path = options.ipath, out_path = options.opath, follow = options.follow)



