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

# TODO: straighten out discards for draw games

import sys
from HandHistoryConverter import *

# PokerStars HH Format

class PokerStars(HandHistoryConverter):

    # Class Variables

    sitename = "PokerStars"
    filetype = "text"
    codepage = ("utf8", "cp1252")
    siteId   = 2 # Needs to match id entry in Sites database

    mixes = { 'HORSE': 'horse', '8-Game': '8game', 'HOSE': 'hose'} # Legal mixed games
    sym = {'USD': "\$", 'CAD': "\$", 'T$': "", "EUR": "\xe2\x82\xac", "GBP": "\xa3"}         # ADD Euro, Sterling, etc HERE
    substitutions = {
                     'LEGAL_ISO' : "USD|EUR|GBP|CAD|FPP",    # legal ISO currency codes
                            'LS' : "\$|\xe2\x82\xac|"        # legal currency symbols - Euro(cp1252, utf-8)
                    }

    # Static regexes
    re_GameInfo     = re.compile(u"""
          PokerStars\sGame\s\#(?P<HID>[0-9]+):\s+
          (Tournament\s\#                # open paren of tournament info
          (?P<TOURNO>\d+),\s
          (?P<BUYIN>[%(LS)s\+\d\.]+      # here's how I plan to use LS
          \s?(?P<TOUR_ISO>%(LEGAL_ISO)s)?
          )\s)?                          # close paren of tournament info
          (?P<MIXED>HORSE|8\-Game|HOSE)?\s?\(?
          (?P<GAME>Hold\'em|Razz|7\sCard\sStud|7\sCard\sStud\sHi/Lo|Omaha|Omaha\sHi/Lo|Badugi|Triple\sDraw\s2\-7\sLowball|5\sCard\sDraw)\s
          (?P<LIMIT>No\sLimit|Limit|Pot\sLimit)\)?,?\s
          (-\sLevel\s(?P<LEVEL>[IVXLC]+)\s)?
          \(?                            # open paren of the stakes
          (?P<CURRENCY>%(LS)s|)?
          (?P<SB>[.0-9]+)/(%(LS)s)?
          (?P<BB>[.0-9]+)
          \s?(?P<ISO>%(LEGAL_ISO)s)?
          \)\s-\s                        # close paren of the stakes
          (?P<DATETIME>.*$)""" % substitutions,
          re.MULTILINE|re.VERBOSE)

    re_PlayerInfo   = re.compile(u"""
          ^Seat\s(?P<SEAT>[0-9]+):\s
          (?P<PNAME>.*)\s
          \((%(LS)s)?(?P<CASH>[.0-9]+)\sin\schips\)""" % substitutions, 
          re.MULTILINE|re.VERBOSE)

    re_HandInfo     = re.compile("""
          ^Table\s\'(?P<TABLE>[-\ a-zA-Z\d]+)\'\s
          ((?P<MAX>\d+)-max\s)?
          (?P<PLAY>\(Play\sMoney\)\s)?
          (Seat\s\#(?P<BUTTON>\d+)\sis\sthe\sbutton)?""", 
          re.MULTILINE|re.VERBOSE)

    re_SplitHands   = re.compile('\n\n+')
    re_TailSplitHands   = re.compile('(\n\n\n+)')
    re_Button       = re.compile('Seat #(?P<BUTTON>\d+) is the button', re.MULTILINE)
    re_Board        = re.compile(r"\[(?P<CARDS>.+)\]")
#        self.re_setHandInfoRegex('.*#(?P<HID>[0-9]+): Table (?P<TABLE>[ a-zA-Z]+) - \$?(?P<SB>[.0-9]+)/\$?(?P<BB>[.0-9]+) - (?P<GAMETYPE>.*) - (?P<HR>[0-9]+):(?P<MIN>[0-9]+) ET - (?P<YEAR>[0-9]+)/(?P<MON>[0-9]+)/(?P<DAY>[0-9]+)Table (?P<TABLE>[ a-zA-Z]+)\nSeat (?P<BUTTON>[0-9]+)')    


    def compilePlayerRegexs(self,  hand):
        players = set([player[1] for player in hand.players])
        if not players <= self.compiledPlayers: # x <= y means 'x is subset of y'
            # we need to recompile the player regexs.
# TODO: should probably rename re_HeroCards and corresponding method,
#    since they are used to find all cards on lines starting with "Dealt to:"
#    They still identify the hero.
            self.compiledPlayers = players
            player_re = "(?P<PNAME>" + "|".join(map(re.escape, players)) + ")"
            subst = {'PLYR': player_re, 'CUR': self.sym[hand.gametype['currency']]}
            log.debug("player_re: " + player_re)
            self.re_PostSB           = re.compile(r"^%(PLYR)s: posts small blind %(CUR)s(?P<SB>[.0-9]+)" %  subst, re.MULTILINE)
            self.re_PostBB           = re.compile(r"^%(PLYR)s: posts big blind %(CUR)s(?P<BB>[.0-9]+)" %  subst, re.MULTILINE)
            self.re_Antes            = re.compile(r"^%(PLYR)s: posts the ante %(CUR)s(?P<ANTE>[.0-9]+)" % subst, re.MULTILINE)
            self.re_BringIn          = re.compile(r"^%(PLYR)s: brings[- ]in( low|) for %(CUR)s(?P<BRINGIN>[.0-9]+)" % subst, re.MULTILINE)
            self.re_PostBoth         = re.compile(r"^%(PLYR)s: posts small \& big blinds \[%(CUR)s (?P<SBBB>[.0-9]+)" %  subst, re.MULTILINE)
            self.re_HeroCards        = re.compile(r"^Dealt to %(PLYR)s(?: \[(?P<OLDCARDS>.+?)\])?( \[(?P<NEWCARDS>.+?)\])" % subst, re.MULTILINE)
            self.re_Action           = re.compile(r"""
                        ^%(PLYR)s:(?P<ATYPE>\sbets|\schecks|\sraises|\scalls|\sfolds|\sdiscards|\sstands\spat)
                        (\s(%(CUR)s)?(?P<BET>[.\d]+))?(\sto\s%(CUR)s(?P<BETTO>[.\d]+))?  # the number discarded goes in <BET>
                        (\scards?(\s\[(?P<DISCARDED>.+?)\])?)?"""
                         %  subst, re.MULTILINE|re.VERBOSE)
            self.re_ShowdownAction   = re.compile(r"^%s: shows \[(?P<CARDS>.*)\]" %  player_re, re.MULTILINE)
            self.re_CollectPot       = re.compile(r"Seat (?P<SEAT>[0-9]+): %(PLYR)s (\(button\) |\(small blind\) |\(big blind\) )?(collected|showed \[.*\] and won) \(%(CUR)s(?P<POT>[.\d]+)\)(, mucked| with.*|)" %  subst, re.MULTILINE)
            self.re_sitsOut          = re.compile("^%s sits out" %  player_re, re.MULTILINE)
            self.re_ShownCards       = re.compile("^Seat (?P<SEAT>[0-9]+): %s (\(.*\) )?(?P<SHOWED>showed|mucked) \[(?P<CARDS>.*)\].*" %  player_re, re.MULTILINE)

    def readSupportedGames(self):
        return [["ring", "hold", "nl"],
                ["ring", "hold", "pl"],
                ["ring", "hold", "fl"],

                ["ring", "stud", "fl"],

                ["ring", "draw", "fl"],

                ["tour", "hold", "nl"],
                ["tour", "hold", "pl"],
                ["tour", "hold", "fl"],

                ["tour", "stud", "fl"],
               ]

    def determineGameType(self, handText):
#    inspect the handText and return the gametype dict
#    gametype dict is:
#    {'limitType': xxx, 'base': xxx, 'category': xxx}
        
        info = {}
        m = self.re_GameInfo.search(handText)
        if not m:
            print "DEBUG: determineGameType(): did not match"
            return None

        mg = m.groupdict()
        # translations from captured groups to fpdb info strings
        limits = { 'No Limit':'nl', 'Pot Limit':'pl', 'Limit':'fl' }
        games = {                          # base, category
                              "Hold'em" : ('hold','holdem'), 
                                'Omaha' : ('hold','omahahi'),
                          'Omaha Hi/Lo' : ('hold','omahahilo'),
                                 'Razz' : ('stud','razz'), 
                          '7 Card Stud' : ('stud','studhi'),
                    '7 Card Stud Hi/Lo' : ('stud','studhilo'),
                               'Badugi' : ('draw','badugi'),
              'Triple Draw 2-7 Lowball' : ('draw','27_3draw'),
                          '5 Card Draw' : ('draw','fivedraw')
               }
        currencies = { u'€':'EUR', '$':'USD', '':'T$' }
#    I don't think this is doing what we think. mg will always have all 
#    the expected keys, but the ones that didn't match in the regex will
#    have a value of None. It is OK if it throws an exception when it 
#    runs across an unknown game or limit or whatever.
        if 'LIMIT' in mg:
            info['limitType'] = limits[mg['LIMIT']]
        if 'GAME' in mg:
            (info['base'], info['category']) = games[mg['GAME']]
        if 'SB' in mg:
            info['sb'] = mg['SB']
        if 'BB' in mg:
            info['bb'] = mg['BB']
        if 'CURRENCY' in mg:
            info['currency'] = currencies[mg['CURRENCY']]

        if 'TOURNO' in mg and mg['TOURNO'] is None:
            info['type'] = 'ring'
        else:
            info['type'] = 'tour'

        # NB: SB, BB must be interpreted as blinds or bets depending on limit type.
        return info

    def readHandInfo(self, hand):
        info = {}
        m = self.re_HandInfo.search(hand.handText,re.DOTALL)
        if m:
            info.update(m.groupdict())
#                hand.maxseats = int(m2.group(1))
        else:
            pass  # throw an exception here, eh?
        m = self.re_GameInfo.search(hand.handText)
        if m:
            info.update(m.groupdict())
#        m = self.re_Button.search(hand.handText)
#        if m: info.update(m.groupdict()) 
        # TODO : I rather like the idea of just having this dict as hand.info
        log.debug("readHandInfo: %s" % info)
        for key in info:
            if key == 'DATETIME':
                #2008/11/12 10:00:48 CET [2008/11/12 4:00:48 ET]
                #2008/08/17 - 01:14:43 (ET)
                #2008/09/07 06:23:14 ET
                m2 = re.search("(?P<Y>[0-9]{4})\/(?P<M>[0-9]{2})\/(?P<D>[0-9]{2})[\- ]+(?P<H>[0-9]+):(?P<MIN>[0-9]+):(?P<S>[0-9]+)", info[key])
                datetimestr = "%s/%s/%s %s:%s:%s" % (m2.group('Y'), m2.group('M'),m2.group('D'),m2.group('H'),m2.group('MIN'),m2.group('S'))
                hand.starttime = datetime.datetime.strptime(datetimestr, "%Y/%m/%d %H:%M:%S")
            if key == 'HID':
                hand.handid = info[key]

            if key == 'TOURNO':
                hand.tourNo = info[key]
            if key == 'BUYIN':
                #FIXME: The key looks like: '€0.82+€0.18 EUR'
                #       This should be parsed properly and used
                hand.buyin = info[key]
            if key == 'LEVEL':
                hand.level = info[key]

            if key == 'TABLE':
                if hand.tourNo != None:
                    hand.tablename = re.split(" ", info[key])[1]
                else:
                    hand.tablename = info[key]
            if key == 'BUTTON':
                hand.buttonpos = info[key]
            if key == 'MAX':
                hand.maxseats = int(info[key])

            if key == 'MIXED':
                hand.mixed = self.mixes[info[key]] if info[key] is not None else None
            if key == 'PLAY' and info['PLAY'] is not None:
#                hand.currency = 'play' # overrides previously set value
                hand.gametype['currency'] = 'play'

    def readButton(self, hand):
        m = self.re_Button.search(hand.handText)
        if m:
            hand.buttonpos = int(m.group('BUTTON'))
        else:
            log.info('readButton: not found')

    def readPlayerStacks(self, hand):
        log.debug("readPlayerStacks")
        m = self.re_PlayerInfo.finditer(hand.handText)
        players = []
        for a in m:
            hand.addPlayer(int(a.group('SEAT')), a.group('PNAME'), a.group('CASH'))

    def markStreets(self, hand):
        # PREFLOP = ** Dealing down cards **
        # This re fails if,  say, river is missing; then we don't get the ** that starts the river.
        if hand.gametype['base'] in ("hold"):
            m =  re.search(r"\*\*\* HOLE CARDS \*\*\*(?P<PREFLOP>.+(?=\*\*\* FLOP \*\*\*)|.+)"
                       r"(\*\*\* FLOP \*\*\*(?P<FLOP> \[\S\S \S\S \S\S\].+(?=\*\*\* TURN \*\*\*)|.+))?"
                       r"(\*\*\* TURN \*\*\* \[\S\S \S\S \S\S] (?P<TURN>\[\S\S\].+(?=\*\*\* RIVER \*\*\*)|.+))?"
                       r"(\*\*\* RIVER \*\*\* \[\S\S \S\S \S\S \S\S] (?P<RIVER>\[\S\S\].+))?", hand.handText,re.DOTALL)
        elif hand.gametype['base'] in ("stud"):
            m =  re.search(r"(?P<ANTES>.+(?=\*\*\* 3rd STREET \*\*\*)|.+)"
                           r"(\*\*\* 3rd STREET \*\*\*(?P<THIRD>.+(?=\*\*\* 4th STREET \*\*\*)|.+))?"
                           r"(\*\*\* 4th STREET \*\*\*(?P<FOURTH>.+(?=\*\*\* 5th STREET \*\*\*)|.+))?"
                           r"(\*\*\* 5th STREET \*\*\*(?P<FIFTH>.+(?=\*\*\* 6th STREET \*\*\*)|.+))?"
                           r"(\*\*\* 6th STREET \*\*\*(?P<SIXTH>.+(?=\*\*\* RIVER \*\*\*)|.+))?"
                           r"(\*\*\* RIVER \*\*\*(?P<SEVENTH>.+))?", hand.handText,re.DOTALL)
        elif hand.gametype['base'] in ("draw"):
            m =  re.search(r"(?P<PREDEAL>.+(?=\*\*\* DEALING HANDS \*\*\*)|.+)"
                           r"(\*\*\* DEALING HANDS \*\*\*(?P<DEAL>.+(?=\*\*\* FIRST DRAW \*\*\*)|.+))?"
                           r"(\*\*\* FIRST DRAW \*\*\*(?P<DRAWONE>.+(?=\*\*\* SECOND DRAW \*\*\*)|.+))?"
                           r"(\*\*\* SECOND DRAW \*\*\*(?P<DRAWTWO>.+(?=\*\*\* THIRD DRAW \*\*\*)|.+))?"
                           r"(\*\*\* THIRD DRAW \*\*\*(?P<DRAWTHREE>.+))?", hand.handText,re.DOTALL)
        hand.addStreets(m)

    def readCommunityCards(self, hand, street): # street has been matched by markStreets, so exists in this hand
        if street in ('FLOP','TURN','RIVER'):   # a list of streets which get dealt community cards (i.e. all but PREFLOP)
            #print "DEBUG readCommunityCards:", street, hand.streets.group(street)
            m = self.re_Board.search(hand.streets[street])
            hand.setCommunityCards(street, m.group('CARDS').split(' '))

    def readAntes(self, hand):
        log.debug("reading antes")
        m = self.re_Antes.finditer(hand.handText)
        for player in m:
            #~ logging.debug("hand.addAnte(%s,%s)" %(player.group('PNAME'), player.group('ANTE')))
            hand.addAnte(player.group('PNAME'), player.group('ANTE'))
    
    def readBringIn(self, hand):
        m = self.re_BringIn.search(hand.handText,re.DOTALL)
        if m:
            #~ logging.debug("readBringIn: %s for %s" %(m.group('PNAME'),  m.group('BRINGIN')))
            hand.addBringIn(m.group('PNAME'),  m.group('BRINGIN'))
        
    def readBlinds(self, hand):
        try:
            m = self.re_PostSB.search(hand.handText)
            hand.addBlind(m.group('PNAME'), 'small blind', m.group('SB'))
        except: # no small blind
            hand.addBlind(None, None, None)
        for a in self.re_PostBB.finditer(hand.handText):
            hand.addBlind(a.group('PNAME'), 'big blind', a.group('BB'))
        for a in self.re_PostBoth.finditer(hand.handText):
            hand.addBlind(a.group('PNAME'), 'both', a.group('SBBB'))

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

                if street == 'THIRD' and len(newcards) == 3: # hero in stud game
                    hand.hero = player
                    hand.dealt.add(player) # need this for stud??
                    hand.addHoleCards(street, player, closed=newcards[0:2], open=[newcards[2]], shown=False, mucked=False, dealt=False)
                else:
                    hand.addHoleCards(street, player, open=newcards, closed=oldcards, shown=False, mucked=False, dealt=False)


    def readAction(self, hand, street):
        m = self.re_Action.finditer(hand.streets[street])
        for action in m:
            acts = action.groupdict()
            if action.group('ATYPE') == ' raises':
                hand.addRaiseBy( street, action.group('PNAME'), action.group('BET') )
            elif action.group('ATYPE') == ' calls':
                hand.addCall( street, action.group('PNAME'), action.group('BET') )
            elif action.group('ATYPE') == ' bets':
                hand.addBet( street, action.group('PNAME'), action.group('BET') )
            elif action.group('ATYPE') == ' folds':
                hand.addFold( street, action.group('PNAME'))
            elif action.group('ATYPE') == ' checks':
                hand.addCheck( street, action.group('PNAME'))
            elif action.group('ATYPE') == ' discards':
                hand.addDiscard(street, action.group('PNAME'), action.group('BET'), action.group('DISCARDED'))
            elif action.group('ATYPE') == ' stands pat':
                hand.addStandsPat( street, action.group('PNAME'))
            else:
                print "DEBUG: unimplemented readAction: '%s' '%s'" %(action.group('PNAME'),action.group('ATYPE'),)


    def readShowdownActions(self, hand):
# TODO: pick up mucks also??
        for shows in self.re_ShowdownAction.finditer(hand.handText):            
            cards = shows.group('CARDS').split(' ')
            hand.addShownCards(cards, shows.group('PNAME'))

    def readCollectPot(self,hand):
        for m in self.re_CollectPot.finditer(hand.handText):
            hand.addCollectPot(player=m.group('PNAME'),pot=m.group('POT'))

    def readShownCards(self,hand):
        for m in self.re_ShownCards.finditer(hand.handText):
            if m.group('CARDS') is not None:
                cards = m.group('CARDS')
                cards = cards.split(' ') # needs to be a list, not a set--stud needs the order

                (shown, mucked) = (False, False)
                if m.group('SHOWED') == "showed": shown = True
                elif m.group('SHOWED') == "mucked": mucked = True

                hand.addShownCards(cards=cards, player=m.group('PNAME'), shown=shown, mucked=mucked)

if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-i", "--input", dest="ipath", help="parse input hand history", default="regression-test-files/stars/horse/HH20090226 Natalie V - $0.10-$0.20 - HORSE.txt")
    parser.add_option("-o", "--output", dest="opath", help="output translation to", default="-")
    parser.add_option("-f", "--follow", dest="follow", help="follow (tail -f) the input", action="store_true", default=False)
    #parser.add_option("-q", "--quiet", action="store_const", const=logging.CRITICAL, dest="verbosity", default=logging.INFO)
    #parser.add_option("-v", "--verbose", action="store_const", const=logging.INFO, dest="verbosity")
    #parser.add_option("--vv", action="store_const", const=logging.DEBUG, dest="verbosity")

    (options, args) = parser.parse_args()

    e = PokerStars(in_path = options.ipath, out_path = options.opath, follow = options.follow)
