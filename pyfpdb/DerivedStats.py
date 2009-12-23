"""@package DerivedStats
FILLME
"""

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

from itertools import chain
from collections import defaultdict
import sys

import Card
from decimal import Decimal


if sys.version[0:3] == '2.5':
    # adding start keyword arg for enumerate
    def enumerate(iterable, start=0):
        for i,o in __builtins__.enumerate(iterable):
            yield i+start,o


DEBUG = False

if DEBUG:
    import pprint
    pp = pprint.PrettyPrinter(indent=4)


class DerivedStats(object):
    def getStats(self, hand):
        for player in hand.players:
            self.handsplayers[player[1]] = {}
            #Init vars that may not be used, but still need to be inserted.
            # All stud street4 need this when importing holdem
            self.handsplayers[player[1]]['winnings']    = 0
            self.handsplayers[player[1]]['rake']        = 0
            self.handsplayers[player[1]]['totalProfit'] = 0
            self.handsplayers[player[1]]['street4Seen'] = False
            self.handsplayers[player[1]]['street4Aggr'] = False
            self.handsplayers[player[1]]['wonWhenSeenStreet1'] = 0.0
            self.handsplayers[player[1]]['sawShowdown'] = False
            self.handsplayers[player[1]]['wonAtSD']     = 0.0
            for i in range(5): 
                self.handsplayers[player[1]]['street%dCalls' % i] = 0
                self.handsplayers[player[1]]['street%dBets' % i] = 0
            for i in range(1,5):
                self.handsplayers[player[1]]['street%dCBChance' %i] = False
                self.handsplayers[player[1]]['street%dCBDone' %i] = False

            #FIXME - Everything below this point is incomplete.
            self.handsplayers[player[1]]['position']            = 2
            self.handsplayers[player[1]]['tourneyTypeId']       = 1
            self.handsplayers[player[1]]['startCards']          = 0
            self.handsplayers[player[1]]['street0_3BChance']    = False
            self.handsplayers[player[1]]['street0_3BDone']      = False
            self.handsplayers[player[1]]['stealAttemptChance']  = False
            self.handsplayers[player[1]]['stealAttempted']      = False
            self.handsplayers[player[1]]['foldBbToStealChance'] = False
            self.handsplayers[player[1]]['foldBbToStealChance'] = False
            self.handsplayers[player[1]]['foldSbToStealChance'] = False
            self.handsplayers[player[1]]['foldedSbToSteal']     = False
            self.handsplayers[player[1]]['foldedBbToSteal']     = False
            for i in range(1,5):
                self.handsplayers[player[1]]['otherRaisedStreet%d' %i]          = False
                self.handsplayers[player[1]]['foldToOtherRaisedStreet%d' %i]    = False
                self.handsplayers[player[1]]['foldToStreet%dCBChance' %i]       = False
                self.handsplayers[player[1]]['foldToStreet%dCBDone' %i]         = False
                self.handsplayers[player[1]]['street%dCheckCallRaiseChance' %i] = False
                self.handsplayers[player[1]]['street%dCheckCallRaiseDone' %i]   = False

        self.assembleHands(self.hand)
        self.assembleHandsPlayers(self.hand)


        if DEBUG:
            print "Hands:"
            pp.pprint(self.hands)
            print "HandsPlayers:"
            pp.pprint(self.handsplayers)

    def getHands(self):
        return self.hands

    def getHandsPlayers(self):
        return self.handsplayers

    def assembleHands(self, hand):
        from datetime import datetime

        self.tableName  = hand.tablename
        self.siteHandNo = hand.handid
        self.handStart  = hand.starttime           
        self.importTime = datetime.now()
        self.seats      = self.countPlayers(hand) 
        self.maxSeats   = hand.maxseats
        self.texture    = None                     # No calculation done for this yet.

        # This (i think...) is correct for both stud and flop games, as hand.board['street'] disappears, and
        # those values remain default in stud.
        boardcards = chain(*[hand.board[s] for s in hand.communityStreets])
        #for i, card in enumerate(boardcards, start=1):
        for i, card in enumerate(boardcards):
            setattr(self, 'boardcard%d' % (i+1), card)

        totals = hand.getStreetTotals()
        for i in range(4):
            setattr(self, 'street%dPot' % (i+1), totals[i])
        self.showdownPot = totals[4]

        self.vpip(hand) # Gives playersVpi (num of players vpip)
        self.playersAtStreetX(hand) # Gives playersAtStreet1..4 and Showdown
        self.streetXRaises(hand) # Empty function currently

    def assembleHandsPlayers(self, hand):
        """Fills HandPlayers classes

        Note, that street0VPI is already filled by vpip in assembleHands
        wonWhenSeenStreetX, wonAtSD, totalProfit, winnings, rake, cardX 
          will be setted here directly
        """

        for i, street in enumerate(hand.actionStreets[2:]):
            self.seen(hand, i+1)

        for i, street in enumerate(hand.actionStreets[1:]):
            self.aggr(hand, i)
            self.calls(hand, i)
            self.bets(hand, i)

        # Winnings is a non-negative value of money collected from the pot, which already includes the
        # rake taken out. hand.collectees is Decimal, database requires cents
        for pname, collected in hand.collectees.iteritems():
            hp = self.handplayers_by_name[pname] # hp stands for hand player
            hp.winnings = collected
            #FIXME: This is pretty dodgy, rake = hand.rake/#collectees
            # You can really only pay rake when you collect money, but
            # different sites calculate rake differently.
            # Should be fine for split-pots, but won't be accurate for multi-way pots
            hp.rake = int(hand.rake)/len(hand.collectees)
            for i in range(1, 5):
                if hp.street1Seen == True:
                    setattr(hp, 'wonWhenSeenStreet%d' % i, getattr(hp, 'street%dSeen' %i))
            if hp.sawShowdown == True:
                hp.wonAtSD = True

            hp.totalProfit = hp.winnings - hand.pot.committed[pname]

        self.calc34BetStreet0(hand)
        self.calcSteals(hand)
        self.calcCBets(hand)
        self.calcCheckCallRaise(hand)

        for pname, hp in self.handplayers_by_name.iteritems():
            for i, card in enumerate(chain(*[chain(*i.get(pname, [])) for i in hand.holecards.itervalues()])):
                setattr(hp, 'card%d' % i, card)
>>>>>>> 29f8658c728d50b1f7ed557bb6e39e3fa205e365:pyfpdb/DerivedStats.py

        for player in hand.players:
            hcs = hand.join_holecards(player[1], asList=True)
            hcs = hcs + [u'0x', u'0x', u'0x', u'0x', u'0x']
            #for i, card in enumerate(hcs[:7], 1): #Python 2.6 syntax
            #    self.handsplayers[player[1]]['card%s' % i] = Card.encodeCard(card)
            for i, card in enumerate(hcs[:7]):
                self.handsplayers[player[1]]['card%s' % (i+1)] = Card.encodeCard(card)


        # position,
            #Stud 3rd street card test
            # denny501: brings in for $0.02
            # s0rrow: calls $0.02
            # TomSludge: folds
            # Soroka69: calls $0.02
            # rdiezchang: calls $0.02           (Seat 8)
            # u.pressure: folds                 (Seat 1)
            # 123smoothie: calls $0.02
            # gashpor: calls $0.02

        # Additional stats
        # 3betSB, 3betBB
        # Squeeze, Ratchet?


    def getPosition(hand, seat):
        """Returns position value like 'B', 'S', 0, 1, ..."""
        # Flop/Draw games with blinds
        # Need a better system???
        # -2 BB - B (all)
        # -1 SB - S (all)
        #  0 Button 
        #  1 Cutoff
        #  2 Hijack

    def assembleHudCache(self, hand):
        pass

    def vpip(self, hand):
        """Fill Hands.playersVpi and HandPlayers.street0VPI
        
        Hands.playersVpi - ammount of players who doesnt't fold preflop
        HandPlayers.street0VPI - flag, setted if player doesnt't fold preflop
        """
        vpipers = self.pfba(hand.actions[hand.actionStreets[1]], l=('calls','bets', 'raises'))
        self.playersVpi = len(vpipers)

        for pname, hp in self.handplayers_by_name.iteritems():
            hp.street0VPI = pname in vpipers

    def playersAtStreetX(self, hand):
        """Fill playersAtStreet1 - num of players seeing flop/street4/draw1 """
        for i in range(4): setattr(self, 'playersAtStreet%d' % (i+1), 0)

        alliners = set()
        for (i, street) in enumerate(hand.actionStreets[2:]):
            actors = set()
            for action in hand.actions[street]:
                if len(action) > 2 and action[-1]: # allin
                    alliners.add(action[0])
                actors.add(action[0])
            if len(actors)==0 and len(alliners)<2:
                alliners = set()
            setattr(self, 'playersAtStreet%d' % (i+1), len(set.union(alliners, actors)))

        actions = hand.actions[hand.actionStreets[-1]]
        pas = set.union(self.pfba(actions) - self.pfba(actions, l=('folds',)),  alliners)
        self.playersAtShowdown = len(pas)

        if self.playersAtShowdown > 1:
            for pname in pas:
                self.handplayers_by_name[pname].sawShowdown = True

    def streetXRaises(self, hand):
        """Fill streetXRaises - amount of player's bets and raises"""
        for i in range(5): setattr(self, 'street%dRaises' % i, 0)

        for (i, street) in enumerate(hand.actionStreets[1:]): 
            setattr(self, 'street%dRaises' % i, 
                    len(filter( lambda action: action[1] in ('raises','bets'), hand.actions[street])))

    def calcSteals(self, hand):
        """Fills stealAttempt(Chance|ed, fold(Bb|Sb)ToSteal(Chance|)
        
        Steal attemp - open raise on positions 2 1 0 S - i.e. MP3, CO, BU, SB
        Fold to steal - folding blind after steal attemp wo any other callers or raisers
        """
        if self.gametype_dict['base'] != 'hold':
            # FIXME: add support for other games //grindi
            return
        steal_attemp = False
        for action in hand.actions[hand.actionStreets[1]]:
            hp, act = self.handplayers_by_name[action[0]], action[1]
            #print action[0], hp.position, steal_attemp, act
            if hp.position == 'B':
                hp.foldBbToStealChance = steal_attemp
                hp.foldBbToSteal = hp.foldBbToStealChance and act == 'folds'
                break
            elif hp.position == 'S':
                hp.foldSbToStealChance = steal_attemp
                hp.foldSbToSteal = hp.foldSbToStealChance and act == 'folds'
            
            if steal_attemp and act != 'folds':
                break

            if hp.position in ('2', '1', '0', 'S') and not steal_attemp:
                hp.stealAttemptChance = True
                if act in ('bets', 'raises'):
                    hp.stealAttempted = True
                    steal_attemp = True

    def calc34BetStreet0(self, hand):
        """Fills street0_(3|4)B(Chance|Done), other(3|4)BStreet0"""
        bet_level = 1 # bet_level after 3-bet is equal to 3
        for action in hand.actions[hand.actionStreets[1]]:
            # FIXME: fill other(3|4)BStreet0 - i have no idea what does it mean
            hp, aggr = self.handplayers_by_name[action[0]], action[1] in ('raises', 'bets')
            hp.street0_3BChance = bet_level == 2
            hp.street0_4BChance = bet_level == 3
            hp.street0_3BDone =  aggr and (hp.street0_3BChance)
            hp.street0_4BDone =  aggr and (hp.street0_4BChance)
            if aggr:
                bet_level += 1

    def calcCBets(self, hand):
        """Fill streetXCBChance, streetXCBDone, foldToStreetXCBDone, foldToStreetXCBChance 
        
        Continuation Bet chance, action:
        Had the last bet (initiative) on previous street, got called, close street action
        Then no bets before the player with initiatives first action on current street
        ie. if player on street-1 had initiative and no donkbets occurred
        """
        for i, street in enumerate(hand.actionStreets[2:], start=1):
            prev_actions = hand.actions[hand.actionStreets[i]]
            current_actions = hand.actions[hand.actionStreets[i+1]]
            name = self.lastBetOrRaiser(prev_actions)

            if name is None or not current_actions:
                # no chances or cbets here
                continue

            chance = self.noBetsBefore(current_actions, name) 
            cb_done = chance and self.betStreet(current_actions, name)

            hp_cb = self.handplayers_by_name[name]
            setattr(hp_cb, 'street%dCBChance' % i, chance)
            setattr(hp_cb, 'street%dCBDone' % i, cb_done)

            if cb_done:
                # lets calculate foldToStreetXCBDone, foldToStreetXCBChance
                # chance flag is set if there isn't any raises after CB and before player folds
                cb_passed = False
                for action in current_actions:
                    pname, act = action[0], action[1]
                    if pname == name:
                        cb_passed = True
                    elif cb_passed:
                        hp = self.handplayers_by_name[pname]
                        setattr(hp, 'foldToStreet%dCBChance' % i, True)
                        setattr(hp, 'foldToStreet%dCBDone' % i, act=='folds')
                        if act in ('bets', 'raises'):
                            break

    def calcCheckCallRaise(self, hand):
        """Fill streetXCheckCallRaiseChance, streetXCheckCallRaiseDone 
        
        streetXCheckCallRaiseChance = got raise/bet after check
        streetXCheckCallRaiseDone = checked. got raise/bet. didn't fold
        """
        for i, street in enumerate(hand.actionStreets[2:], start=1):
            actions = hand.actions[hand.actionStreets[i]]
            checkers = set()
            initial_raiser = None
            for action in actions:
                pname, act = action[0], action[1]
                if act in ('bets', 'raises') and initial_raiser is None:
                    initial_raiser = pname
                elif act == 'check' and initial_raiser is None:
                    checkers.add(pname)
                elif initial_raiser is not None and pname in checkers:
                    hp = self.handplayers_by_name[pname]
                    setattr(hp, 'street%dCheckCallRaiseChance' % i, True)
                    setattr(hp, 'street%dCheckCallRaiseDone' % i, act!='folds')

    def seen(self, hand, i):
        """Fill streetXSeen - were player acting during X street"""
        pas = set()
        for act in hand.actions[hand.actionStreets[i+1]]:
            pas.add(act[0])

        for pname, hp in self.handplayers_by_name.iteritems():
            setattr(hp, 'street%sSeen' % i, pname in pas)

    def aggr(self, hand, i):
        """Fill streetXAggr
        
        Player is aggresor if he raises or completes
        """
        aggrers = set()
        for act in hand.actions[hand.actionStreets[i]]:
            if act[1] in ('completes', 'raises'):
                aggrers.add(act[0])

        for pname, hp in self.handplayers_by_name.iteritems():
            setattr(hp, 'street%sAggr' % i, pname in aggrers)

    def calls(self, hand, i):
        """Fill streetXCalls - amount of player's calls on current street"""
        callers = self.countActionOcuurences(hand.actions[hand.actionStreets[i+1]], 'calls')
        for pname, hp in self.handplayers_by_name.iteritems():
            setattr(hp, 'street%sCalls' % i, callers[pname])

    def bets(self, hand, i):
        """Fill streetXBets - amount of player's bets on current street"""
        betters = self.countActionOcuurences(hand.actions[hand.actionStreets[i+1]], 'bets') 
        for pname, hp in self.handplayers_by_name.iteritems():
            setattr(hp, 'street%sBets' % i, betters[pname])

    def calls(self, hand, i):
        callers = []
        for act in hand.actions[hand.actionStreets[i+1]]:
            if act[1] in ('calls'):
                self.handsplayers[act[0]]['street%sCalls' % i] = 1 + self.handsplayers[act[0]]['street%sCalls' % i]

    # CG - I'm sure this stat is wrong
    # Best guess is that raise = 2 bets
    def bets(self, hand, i):
        betters = []
        for act in hand.actions[hand.actionStreets[i+1]]:
            if act[1] in ('bets'):
                self.handsplayers[act[0]]['street%sBets' % i] = 1 + self.handsplayers[act[0]]['street%sBets' % i]

    def countPlayers(self, hand):
        return hand.counted_seats or len(hand.players)

    @staticmethod
    def countActionOcuurences(actions, action):
        occurences = defaultdict(lambda: 0, {})
        for act in actions:
            if act[1] == action:
                occurences[act[0]] += 1
        return occurences

    @staticmethod
    def pfba(actions, f=None, l=None):
        """Helper method. Returns set of PlayersFilteredByActions

        f - forbidden actions
        l - limited to actions
        """
        players = set()
        for action in actions:
            if l is not None and action[1] not in l: continue
            if f is not None and action[1] in f: continue
            players.add(action[0])
        return players

    @staticmethod
    def firstsBetOrRaiser(actions):
        """Returns player name that placed the first bet or raise.
            
        None if there were no bets or raises on that street
        """
        for act in actions:
            if act[1] in ('bets', 'raises'):
                return act[0]
        return None

    @staticmethod
    def lastBetOrRaiser(actions):
        """Returns player name that placed the last bet or raise.
            
        None if there were no bets or raises on that street
        """
        for act in reversed(actions):
            if act[1] in ('bets', 'raises'):
                return act[0]
        return None

    @staticmethod
    def noBetsBefore(actions, pname):
        """Returns true if there were no bets before the specified players turn, false otherwise"""
        for act in actions:
            #Must test for player first in case UTG
            if act[0] == pname:
                return True
            elif act[1] in ('bets', 'raises'):
                return False
        raise Exception("Cannot find player '%s' actions at all" % pname)

    @staticmethod
    def betStreet(actions, player):
        """Returns true if player bet/raised the street as their first action"""
        betOrRaise = False
        for act in actions:
            if act[0] == player and act[1] in ('bets', 'raises'):
                betOrRaise = True
            else:
                break
        return betOrRaise

