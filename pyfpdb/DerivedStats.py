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

import Card

DEBUG = False

if DEBUG:
    import pprint
    pp = pprint.PrettyPrinter(indent=4)


class DerivedStats(object):
    def getStats(self, hand):
        for player in hand.players:
            for i in range(1,5):
                self.handsplayers[player[1]]['street%dCBChance' %i] = False
                self.handsplayers[player[1]]['street%dCBDone' %i] = False

        self.assembleHands(self.hand)
        self.assembleHandsPlayers(self.hand)

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
        for i, card in enumerate(boardcards, start=1):
            setattr(self, 'boardcard%d' % i, card)

        totals = hand.getStreetTotals()
        for i in range(4):
            setattr(self, 'street%dPot' % (i+1), totals[i])
        self.showdownPot = totals[4]

        self.vpip(hand) # Gives playersVpi (num of players vpip)
        self.playersAtStreetX(hand) # Gives playersAtStreet1..4 and Showdown
        self.streetXRaises(hand) # Empty function currently

    def assembleHandsPlayers(self, hand):
        #street0VPI/vpip already called in Hand
        # sawShowdown is calculated in playersAtStreetX, as that calculation gives us a convenient list of names

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
            if hp.street1Seen == True:
                hp.wonWhenSeenStreet1 = True
            if hp.sawShowdown == True:
                hp.wonAtSD = True

            hp.totalProfit = hp.winnings - hand.pot.committed[pname]

        self.calcCBets(hand)

        #default_holecards = ["Xx", "Xx", "Xx", "Xx"]
        #if hand.gametype['base'] == "hold":
        #    pass
        #elif hand.gametype['base'] == "stud":
        #    pass
        #else:
        #    # Flop hopefully...
        #    pass

        for pname, hp in self.handplayers_by_name.iteritems():
            for i, card in enumerate(chain(*[i.get(pname, []) for i in hand.holecards.itervalues()])):
                setattr(self, 'card%d' % i, card)


    def assembleHudCache(self, hand):
        pass

    def vpip(self, hand):
        vpipers = self.pfba(hand.actions[hand.actionStreets[1]], l=('calls','bets', 'raises'))
        self.playersVpi = len(vpipers)

        for pname, hp in self.handplayers_by_name.iteritems():
            hp.street0VPI = pname in vpipers

    def playersAtStreetX(self, hand):
        """ playersAtStreet1 SMALLINT NOT NULL,   /* num of players seeing flop/street4/draw1 */"""
        # self.actions[street] is a list of all actions in a tuple, contining the player name first
        # [ (player, action, ....), (player2, action, ...) ]
        # The number of unique players in the list per street gives the value for playersAtStreetXXX

        # FIXME?? - This isn't couting people that are all in - at least showdown needs to reflect this

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

        for pname in pas:
            self.handplayers_by_name[pname].sawShowdown = True

    def streetXRaises(self, hand):
        """FILLME"""
        for i in range(5): setattr(self, 'street%dRaises' % i, 0)

        for (i, street) in enumerate(hand.actionStreets[1:]): 
            setattr(self, 'street%dRaises' % i, 
                    len(filter( lambda action: action[1] in ('raises','bets'), hand.actions[street])))

    def calcCBets(self, hand):
        """Continuation Bet chance, action:

        Had the last bet (initiative) on previous street, got called, close street action
        Then no bets before the player with initiatives first action on current street
        ie. if player on street-1 had initiative and no donkbets occurred
        """
        for i, street in enumerate(hand.actionStreets[2:], start=1):
            prev_actions = hand.actions[hand.actionStreets[i]]
            current_actions = hand.actions[hand.actionStreets[i+1]]

            name = self.lastBetOrRaiser(prev_actions)
            if name and current_actions:
                hp = self.handplayers_by_name[name]
                chance = self.noBetsBefore(current_actions, name) # FIXME: seems this line have to be moved down //grindi
                setattr(hp, 'street%dCBChance' % i, True)
                if chance == True:
                    setattr(hp, 'street%dCBDone' % i, self.betStreet(current_actions, name))

    def seen(self, hand, i):
        pas = set()
        for act in hand.actions[hand.actionStreets[i+1]]:
            pas.add(act[0])

        for pname, hp in self.handplayers_by_name.iteritems():
            setattr(hp, 'street%sSeen' % i, pname in pas)

    def aggr(self, hand, i):
        aggrers = set()
        for act in hand.actions[hand.actionStreets[i]]:
            if act[1] in ('completes', 'raises'):
                aggrers.add(act[0])

        for pname, hp in self.handplayers_by_name.iteritems():
            setattr(hp, 'street%sAggr' % i, pname in aggrers)

    def calls(self, hand, i):
        callers = self.countActionOcuurences(hand.actions[hand.actionStreets[i+1]], 'calls')
        for pname, hp in self.handplayers_by_name.iteritems():
            setattr(hp, 'street%sCalls' % i, callers[pname])

    # CG - I'm sure this stat is wrong
    # Best guess is that raise = 2 bets
    def bets(self, hand, i):
        betters = self.countActionOcuurences(hand.actions[hand.actionStreets[i+1]], 'bets') 
        for pname, hp in self.handplayers_by_name.iteritems():
            setattr(hp, 'street%sBets' % i, betters[pname])

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


