#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#    Copyright 2009, Grigorij Indigirkin
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
from collections import defaultdict

from Exceptions import FpdbParseError
from HandHistoryConverter import *

# PartyPoker HH Format

class FpdbParseError(FpdbParseError):
    "Usage: raise FpdbParseError(<msg>[, hh=<hh>][, hid=<hid>])"

    def __init__(self, msg='', hh=None, hid=None):
        return super(FpdbParseError, self).__init__(msg, hid=hid)

    def wrapHh(self, hh):
        return ("%(DELIMETER)s\n%(HH)s\n%(DELIMETER)s") % \
                {'DELIMETER': '#'*50, 'HH': hh}

class PartyPoker(HandHistoryConverter):
    sitename = "PartyPoker"
    codepage = "cp1252"
    siteId = 9 
    filetype = "text" 
    sym = {'USD': "\$", }

    # Static regexes
    # $5 USD NL Texas Hold'em - Saturday, July 25, 07:53:52 EDT 2009
    # NL Texas Hold'em $1 USD Buy-in Trny:45685440 Level:8  Blinds-Antes(600/1 200 -50) - Sunday, May 17, 11:25:07 MSKS 2009
    re_GameInfoRing     = re.compile("""
            (?P<CURRENCY>\$|)\s*(?P<RINGLIMIT>[0-9,]+)\s*(?:USD)?\s*
            (?P<LIMIT>(NL|PL|))\s+
            (?P<GAME>(Texas\ Hold\'em|Omaha))
            \s*\-\s*
            (?P<DATETIME>.+)
            """, re.VERBOSE)
    re_GameInfoTrny     = re.compile("""
            (?P<LIMIT>(NL|PL|))\s+
            (?P<GAME>(Texas\ Hold\'em|Omaha))\s+
            (?P<BUYIN>\$?[.0-9]+)\s*(?P<BUYIN_CURRENCY>USD)?\s*Buy-in\s+
            Trny:\s?(?P<TOURNO>\d+)\s+
            Level:\s*(?P<LEVEL>\d+)\s+
            Blinds(?:-Antes)?\(
                (?P<SB>[.0-9 ]+)\s*
                /(?P<BB>[.0-9 ]+)
                (?:\s*-\s*(?P<ANTE>[.0-9 ]+)\$?)?
            \)
            \s*\-\s*
            (?P<DATETIME>.+)
            """, re.VERBOSE)
    re_Hid          = re.compile("^Game \#(?P<HID>\d+) starts.")

    re_PlayerInfo   = re.compile("""
          Seat\s(?P<SEAT>\d+):\s
          (?P<PNAME>.*)\s
          \(\s*\$?(?P<CASH>[0-9,.]+)\s*(?:USD|)\s*\)
          """ ,
          re.VERBOSE)

    re_HandInfo     = re.compile("""
            ^Table\s+
            (?P<TABLE_TYPE>[^#()]+)\s+          # Regular, Speed, etc
            (?P<TABLE_ID_WRAPPER>\(|\#| )        # \# means sng, ( - mtt, nothing - cash game
            (?P<TABLE_ID>\d+)  \)?   \s+        # it's global unique id for this table
            (?:Table\s+\#(?P<TABLE_NUM>\d+).+)? # table num for mtt tournaments
            \((?P<PLAY>Real|Play)\s+Money\)\s*  
            """,
          re.VERBOSE|re.MULTILINE)

    re_CountedSeats = re.compile("^Total\s+number\s+of\s+players\s*:\s*(?P<COUNTED_SEATS>\d+)", re.MULTILINE)
    re_SplitHands   = re.compile('\x00+')
    re_TailSplitHands   = re.compile('(\x00+)')
    lineSplitter    = '\n'
    re_Button       = re.compile('Seat (?P<BUTTON>\d+) is the button', re.MULTILINE)
    re_Board        = re.compile(r"\[(?P<CARDS>.+)\]")
    re_NoSmallBlind = re.compile(
                    '^There is no Small Blind in this hand as the Big Blind '
                    'of the previous hand left the table', re.MULTILINE)


    def allHandsAsList(self):
        list = HandHistoryConverter.allHandsAsList(self)
        if list is None:
            return []
        return filter(lambda text: len(text.strip()), list)

    def guessMaxSeats(self, hand):
        """Return a guess at max_seats when not specified in HH."""
        mo = self.maxOccSeat(hand)

        if mo == 10: return mo
        if mo == 2: return 2
        if mo <= 6: return 6
        # there are 9-max tables for cash and 10-max for tournaments
        return 9 if hand.gametype['type']=='ring' else 10

    def compilePlayerRegexs(self,  hand):
        players = set([player[1] for player in hand.players])
        if not players <= self.compiledPlayers: # x <= y means 'x is subset of y'

            self.compiledPlayers = players
            player_re = "(?P<PNAME>" + "|".join(map(re.escape, players)) + ")"
            subst = {'PLYR': player_re, 'CUR_SYM': hand.SYMBOL[hand.gametype['currency']],
                'CUR': hand.gametype['currency'] if hand.gametype['currency']!='T$' else ''}
            for key in ('CUR_SYM', 'CUR'):
                subst[key] = re.escape(subst[key])
            self.re_PostSB = re.compile(
                r"^%(PLYR)s posts small blind \[%(CUR_SYM)s(?P<SB>[,.0-9]+) ?%(CUR)s\]\." %  subst,
                re.MULTILINE)
            self.re_PostBB = re.compile(
                r"^%(PLYR)s posts big blind \[%(CUR_SYM)s(?P<BB>[.,0-9]+) ?%(CUR)s\]\." %  subst,
                re.MULTILINE)
            self.re_PostDead = re.compile(
                r"^%(PLYR)s posts big blind \+ dead \[(?P<BBNDEAD>[.,0-9]+) ?%(CUR_SYM)s\]\." %  subst,
                re.MULTILINE)
            self.re_Antes = re.compile(
                r"^%(PLYR)s posts ante \[%(CUR_SYM)s(?P<ANTE>[.0-9]+) ?%(CUR)s\]" %  subst,
                re.MULTILINE)
            self.re_HeroCards = re.compile(
                r"^Dealt to %(PLYR)s \[\s*(?P<NEWCARDS>.+)\s*\]" % subst,
                re.MULTILINE)
            self.re_Action = re.compile(r"""
                ^%(PLYR)s\s+(?P<ATYPE>bets|checks|raises|calls|folds|is\sall-In)
                (?:\s+\[%(CUR_SYM)s(?P<BET>[.,\d]+)\s*%(CUR)s\])?
                """ %  subst,
                re.MULTILINE|re.VERBOSE)
            self.re_ShownCards = re.compile(
                r"^%s (?P<SHOWED>(?:doesn\'t )?shows?) "  %  player_re +
                r"\[ *(?P<CARDS>.+) *\](?P<COMBINATION>.+)\.",
                re.MULTILINE)
            self.re_CollectPot = re.compile(
                r"""^%(PLYR)s \s+ wins \s+
                %(CUR_SYM)s(?P<POT>[.,\d]+)\s*%(CUR)s""" %  subst,
                re.MULTILINE|re.VERBOSE)

    def readSupportedGames(self):
        return [["ring", "hold", "nl"],
                ["ring", "hold", "pl"],
                ["ring", "hold", "fl"],

                ["tour", "hold", "nl"],
                ["tour", "hold", "pl"],
                ["tour", "hold", "fl"],
               ]

    def _getGameType(self, handText):
        if not hasattr(self, '_gameType'):
            self._gameType = None
        if self._gameType is None:
            # let's determine whether hand is trny
            # and whether 5-th line contains head line
            headLine = handText.split(self.lineSplitter)[4]
            for headLineContainer in headLine, handText:
                for regexp in self.re_GameInfoTrny, self.re_GameInfoRing:
                    m = regexp.search(headLineContainer)
                    if m is not None:
                        self._gameType = m
                        return self._gameType
        return self._gameType

    def determineGameType(self, handText):
        """inspect the handText and return the gametype dict

        gametype dict is:
        {'limitType': xxx, 'base': xxx, 'category': xxx}"""

        info = {}
        m = self._getGameType(handText)
        if m is None:
            return None

        mg = m.groupdict()
        # translations from captured groups to fpdb info strings
        limits = { 'NL':'nl', 'PL':'pl', '':'fl' }
        games = {                          # base, category
                         "Texas Hold'em" : ('hold','holdem'),
                                'Omaha' : ('hold','omahahi'),
               }
        currencies = { '$':'USD', '':'T$' }

        for expectedField in ['LIMIT', 'GAME']:
            if mg[expectedField] is None:
                raise FpdbParseError( "Cannot fetch field '%s'" % expectedField)
        try:
            info['limitType'] = limits[mg['LIMIT'].strip()]
        except:
            raise FpdbParseError("Unknown limit '%s'" % mg['LIMIT'])

        try:
            (info['base'], info['category']) = games[mg['GAME']]
        except:
            raise FpdbParseError("Unknown game type '%s'" % mg['GAME'])

        if 'TOURNO' in mg:
            info['type'] = 'tour'
        else:
            info['type'] = 'ring'

        if info['type'] == 'ring':
            info['sb'], info['bb'] = ringBlinds(mg['RINGLIMIT'])
            info['currency'] = currencies[mg['CURRENCY']]
        else:
            info['sb'] = clearMoneyString(mg['SB'])
            info['bb'] = clearMoneyString(mg['BB'])
            info['currency'] = 'T$'

        return info


    def readHandInfo(self, hand):
        info = {}
        try:
            info.update(self.re_Hid.search(hand.handText).groupdict())
        except:
            raise FpdbParseError("Cannot read HID for current hand")

        try:
            info.update(self.re_HandInfo.search(hand.handText,re.DOTALL).groupdict())
        except:
            raise FpdbParseError("Cannot read Handinfo for current hand", hid = info['HID'])

        try:
            info.update(self._getGameType(hand.handText).groupdict())
        except:
            raise FpdbParseError("Cannot read GameType for current hand", hid = info['HID'])


        m = self.re_CountedSeats.search(hand.handText)
        if m: info.update(m.groupdict())


        # FIXME: it's dirty hack
        # party doesnt subtract uncalled money from commited money
        # so hand.totalPot calculation has to be redefined
        from Hand import Pot, HoldemOmahaHand
        def getNewTotalPot(origTotalPot):
            def totalPot(self):
                if self.totalpot is None:
                    self.pot.end()
                    self.totalpot = self.pot.total
                for i,v in enumerate(self.collected):
                    if v[0] in self.pot.returned:
                        self.collected[i][1] = Decimal(v[1]) - self.pot.returned[v[0]]
                return origTotalPot()
            return totalPot
        instancemethod = type(hand.totalPot)
        hand.totalPot = instancemethod(getNewTotalPot(hand.totalPot), hand, HoldemOmahaHand)



        log.debug("readHandInfo: %s" % info)
        for key in info:
            if key == 'DATETIME':
                #Saturday, July 25, 07:53:52 EDT 2009
                #Thursday, July 30, 21:40:41 MSKS 2009
                #Sunday, October 25, 13:39:07 MSK 2009
                m2 = re.search("\w+, (?P<M>\w+) (?P<D>\d+), (?P<H>\d+):(?P<MIN>\d+):(?P<S>\d+) (?P<TZ>[A-Z]+) (?P<Y>\d+)", info[key])
                # we cant use '%B' due to locale problems
                months = ['January', 'February', 'March', 'April','May', 'June',
                    'July','August','September','October','November','December']
                month = months.index(m2.group('M')) + 1
                datetimestr = "%s/%s/%s %s:%s:%s" % (m2.group('Y'), month,m2.group('D'),m2.group('H'),m2.group('MIN'),m2.group('S'))
                hand.starttime = datetime.datetime.strptime(datetimestr, "%Y/%m/%d %H:%M:%S")
                # FIXME: some timezone correction required
                #tzShift = defaultdict(lambda:0, {'EDT': -5, 'EST': -6, 'MSKS': 3})
                #hand.starttime -= datetime.timedelta(hours=tzShift[m2.group('TZ')])

            if key == 'HID':
                hand.handid = info[key]
            if key == 'TOURNO':
                hand.tourNo = info[key]
            if key == 'TABLE_ID_WRAPPER':
                if info[key] == '#':
                    # FIXME: there is no such property in Hand class
                    self.isSNG = True
            if key == 'BUYIN':
                # FIXME: it's dirty hack T_T
                # code below assumes that tournament rake is equal to zero
                cur = info[key][0] if info[key][0] not in '0123456789' else ''
                hand.buyin = info[key] + '+%s0' % cur
            if key == 'TABLE_ID':
                hand.tablename = info[key]
            if key == 'TABLE_NUM':
                # FIXME: there is no such property in Hand class
                hand.table_num = info[key]
            if key == 'COUNTED_SEATS':
                hand.counted_seats  = info[key]
            if key == 'LEVEL':
                hand.level = info[key]
            if key == 'PLAY' and info['PLAY'] != 'Real':
                # if realy party doesn's save play money hh
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
            hand.addPlayer(int(a.group('SEAT')), a.group('PNAME'),
                           clearMoneyString(a.group('CASH')))

    def markStreets(self, hand):
        m =  re.search(
            r"\*{2} Dealing down cards \*{2}"
            r"(?P<PREFLOP>.+?)"
            r"(?:\*{2} Dealing Flop \*{2} (?P<FLOP>\[ \S\S, \S\S, \S\S \].+?))?"
            r"(?:\*{2} Dealing Turn \*{2} (?P<TURN>\[ \S\S \].+?))?"
            r"(?:\*{2} Dealing River \*{2} (?P<RIVER>\[ \S\S \].+?))?$"
            , hand.handText,re.DOTALL)
        hand.addStreets(m)

    def readCommunityCards(self, hand, street):
        if street in ('FLOP','TURN','RIVER'):
            m = self.re_Board.search(hand.streets[street])
            hand.setCommunityCards(street, renderCards(m.group('CARDS')))

    def readAntes(self, hand):
        log.debug("reading antes")
        m = self.re_Antes.finditer(hand.handText)
        for player in m:
            hand.addAnte(player.group('PNAME'), player.group('ANTE'))

    def readBlinds(self, hand):
        noSmallBlind = bool(self.re_NoSmallBlind.search(hand.handText))
        if hand.gametype['type'] == 'ring':
            try:
                assert noSmallBlind==False
                m = self.re_PostSB.search(hand.handText)
                hand.addBlind(m.group('PNAME'), 'small blind', m.group('SB'))
            except: # no small blind
                hand.addBlind(None, None, None)

            for a in self.re_PostBB.finditer(hand.handText):
                hand.addBlind(a.group('PNAME'), 'big blind', a.group('BB'))

            deadFilter = lambda s: s.replace(',', '.')
            for a in self.re_PostDead.finditer(hand.handText):
                hand.addBlind(a.group('PNAME'), 'both', deadFilter(a.group('BBNDEAD')))
        else:
            # party doesn't track blinds for tournaments
            # so there're some cra^Wcaclulations
            if hand.buttonpos == 0:
                self.readButton(hand)
            # NOTE: code below depends on Hand's implementation
            # playersMap - dict {seat: (pname,stack)}
            playersMap = dict([(f[0], f[1:3]) for f in hand.players])
            maxSeat = max(playersMap)

            def findFirstNonEmptySeat(startSeat):
                while startSeat not in playersMap:
                    if startSeat >= maxSeat:
                        startSeat = 0
                    startSeat += 1
                return startSeat
            smartMin = lambda A,B: A if float(A) <= float(B) else B

            if noSmallBlind:
                hand.addBlind(None, None, None)
                smallBlindSeat = int(hand.buttonpos)
            else:
                smallBlindSeat = findFirstNonEmptySeat(int(hand.buttonpos) + 1)
                blind = smartMin(hand.sb, playersMap[smallBlindSeat][1])
                hand.addBlind(playersMap[smallBlindSeat][0], 'small blind', blind)

            bigBlindSeat = findFirstNonEmptySeat(smallBlindSeat + 1)
            blind = smartMin(hand.bb, playersMap[bigBlindSeat][1])
            hand.addBlind(playersMap[bigBlindSeat][0], 'big blind', blind)

    def readHeroCards(self, hand):
        # we need to grab hero's cards
        for street in ('PREFLOP',):
            if street in hand.streets.keys():
                m = self.re_HeroCards.finditer(hand.streets[street])
                for found in m:
                    hand.hero = found.group('PNAME')
                    newcards = renderCards(found.group('NEWCARDS'))
                    hand.addHoleCards(street, hand.hero, closed=newcards, shown=False, mucked=False, dealt=True)

    def readAction(self, hand, street):
        m = self.re_Action.finditer(hand.streets[street])
        for action in m:
            acts = action.groupdict()
            playerName = action.group('PNAME')
            amount = clearMoneyString(action.group('BET')) if action.group('BET') else None
            actionType = action.group('ATYPE')

            if actionType == 'is all-In':
                # party's allin can mean either raise or bet or call
                Bp = hand.lastBet[street]
                if Bp == 0:
                    actionType = 'bets'
                elif Bp < Decimal(amount):
                    actionType = 'raises'
                else:
                    actionType = 'calls'

            if actionType == 'raises':
                if street == 'PREFLOP' and \
                    playerName in [item[0] for item in hand.actions['BLINDSANTES'] if item[2]!='ante']:
                    # preflop raise from blind
                    hand.addRaiseBy( street, playerName, amount )
                else:
                    hand.addCallandRaise( street, playerName, amount )
            elif actionType == 'calls':
                hand.addCall( street, playerName, amount )
            elif actionType == 'bets':
                hand.addBet( street, playerName, amount )
            elif actionType == 'folds':
                hand.addFold( street, playerName )
            elif actionType == 'checks':
                hand.addCheck( street, playerName )
            else:
                raise FpdbParseError(
                    "Unimplemented readAction: '%s' '%s'" % (playerName,actionType,),
                    hid = hand.hid, )

    def readShowdownActions(self, hand):
        # all action in readShownCards
        pass

    def readCollectPot(self,hand):
        for m in self.re_CollectPot.finditer(hand.handText):
            hand.addCollectPot(player=m.group('PNAME'),pot=clearMoneyString(m.group('POT')))

    def readShownCards(self,hand):
        for m in self.re_ShownCards.finditer(hand.handText):
            if m.group('CARDS') is not None:
                cards = renderCards(m.group('CARDS'))

                mucked = m.group('SHOWED') != "show"

                hand.addShownCards(cards=cards, player=m.group('PNAME'), shown=True, mucked=mucked)

    @staticmethod
    def getTableTitleRe(type, table_name=None, tournament = None, table_number=None):
        "Returns string to search in windows titles"
        if type=="tour":
            print 'party', 'getTableTitleRe', "%s.+Table\s#%s" % (table_name, table_number)
            return "%s.+Table\s#%s" % (table_name, table_number)
        else:
            print 'party', 'getTableTitleRe', table_number
            return table_name


def ringBlinds(ringLimit):
    "Returns blinds for current limit in cash games"
    ringLimit = float(clearMoneyString(ringLimit))
    if ringLimit == 5.: ringLimit = 4.
    return ('%.2f' % (ringLimit/200.), '%.2f' % (ringLimit/100.)  )

def clearMoneyString(money):
    "Renders 'numbers' like '1 200' and '2,000'"
    return money.replace(' ', '').replace(',', '')

def renderCards(string):
    "Splits strings like ' Js, 4d '"
    cards = string.strip().split(' ')
    return filter(len, map(lambda x: x.strip(' ,'), cards))


if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-i", "--input", dest="ipath", help="parse input hand history")
    parser.add_option("-o", "--output", dest="opath", help="output translation to", default="-")
    parser.add_option("-f", "--follow", dest="follow", help="follow (tail -f) the input", action="store_true", default=False)
    parser.add_option("-q", "--quiet",
                  action="store_const", const=logging.CRITICAL, dest="verbosity", default=logging.INFO)
    parser.add_option("-v", "--verbose",
                  action="store_const", const=logging.INFO, dest="verbosity")
    parser.add_option("--vv",
                  action="store_const", const=logging.DEBUG, dest="verbosity")

    (options, args) = parser.parse_args()

    e = PartyPoker(in_path = options.ipath, out_path = options.opath, follow = options.follow)
