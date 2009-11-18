# -*- coding: utf-8 -*-
"""@package AlchemyMappings
This package contains all classes to be mapped and mappers themselves
"""

import logging
from sqlalchemy.orm import mapper, relation
from decimal import Decimal
from collections import defaultdict

from AlchemyTables import *
from AlchemyFacilities import get_or_create, MappedBase


class Site(object):
    """Class reflecting Players db table"""
    pass


class Player(MappedBase):
    """Class reflecting Players db table"""

    @staticmethod
    def get_or_create(session, siteId, name):
        print '#'*30, 'Player.get_or_create' 
        return get_or_create(Player, session, siteId=siteId, name=name)[0]

    def __str__(self):
        return '<Player "%s" on %s>' % (self.name, self.site and self.site.name)


class Gametype(MappedBase):
    """Class reflecting Gametypes db table"""

    @staticmethod
    def get_or_create(session, siteId, gametype):
        map = zip(
            ['type', 'base', 'category', 'limitType', 'smallBlind', 'bigBlind', 'smallBet', 'bigBet'],
            ['type', 'base', 'category', 'limitType', 'sb', 'bb', 'dummy', 'dummy', ])
        gametype = dict([(new, gametype.get(old)) for new, old in map  ])

        hilo = "h"
        if gametype['category'] in ('studhilo', 'omahahilo'):
            hilo = "s"
        elif gametype['category'] in ('razz','27_3draw','badugi'):
            hilo = "l"
        gametype['hiLo'] = hilo

        for f in ['smallBlind', 'bigBlind', 'smallBet', 'bigBet']:
            if gametype[f] is None: 
                gametype[f] = 0
            gametype[f] = int(Decimal(gametype[f])*100)

        gametype['siteId'] = siteId
        return get_or_create(Gametype, session, **gametype)[0]


class HandInternal(object):
    """Class reflecting Hands db table"""

    def parseImportedHandStep1(self, hand):
        """Extracts values to insert into from hand returned by HHC. No db is needed he"""
        from itertools import chain
        from datetime import datetime

        hand.players = hand.getAlivePlayers() # FIXME: do we really want to do it? //grindi
                                                  #  Yes! - in tourneys, they get dealt cards. 
                                                  # In ring they do not, but are often listed still in the hh
                                                  # Carl G

        self.tableName  = hand.tablename
        self.siteHandNo = hand.handid
        self.gametypeId = None # Leave None, handled later after checking db
        self.handStart  = hand.starttime           
        self.importTime = datetime.now()
        self.seats      = hand.counted_seats or len(hand.players) 
        self.maxSeats   = hand.maxseats
        self.texture    = None                     # No calculation done for this yet.

        # also save some data for step2. Those fields aren't in Hand table
        self.siteId = hand.siteId 
        self.gametype_dict = hand.gametype 

        # This (i think...) is correct for both stud and flop games, as hand.board['street'] disappears, and
        # those values remain default in stud.
        for i, card in enumerate(chain(*[hand.board[s] for s in hand.communityStreets])):
            setattr(self, 'boardcard%d' % (i+1), card)

        #print "DEBUG: self.getStreetTotals = (%s, %s, %s, %s, %s)" %  hand.getStreetTotals()
        self.calcStreetPotTotals(hand)

        self.calcVpip(hand) # Gives playersVpi (num of players vpip)
        self.calcPlayersAtStreetX(hand) # Gives playersAtStreet1..4 and Showdown
        self.calcStreetXRaises(hand) # Empty function currently

        self.attachHandPlayers(hand)
        #FIXME: write actions and uncomment line below
        #self.attachActions(hand)

        sorted_actions = [ (street, hand.actions[street]) for street in hand.actionStreets ]
        HandPlayer.applyImportedActions(self.handplayers_name_cache, sorted_actions, hand.collectees )

    def parseImportedHandStep2(self, session):
        """Fetching ids for gametypes and players"""
        self.gametypeId = Gametype.get_or_create(session, self.siteId, self.gametype_dict).id
        for hp in self.handPlayers:
            hp.playerId = Player.get_or_create(session, self.siteId, hp.name).id

    def getPlayerByName(self, name):
        for hp in self.handPlayers:
            pname = (hp.player and hp.player.name) or hp.name
            if pname == name:
                return hp

    def attachHandPlayers(self, hand):
        """Fills HandInternal.handPlayers list"""
        self.handplayers_name_cache = {}
        for seat, name, chips in hand.players:
            p = HandPlayer(self, hand, seat, name, chips)         

            self.handplayers_name_cache[name] = p
            #self.handPlayers.append(p) # p already here. see comment in HandPlayer.__init__

            p.name = name     # HandsPlayers table doesn't have this field
            p.playerId = None # Leave None, handled later during step 2
        
    def attachActions(self, hand):
        """Fills HandPlayers.actions list for each attached player"""
        for street, actions in hand.actions.iteritems():
            for i, action in enumerate(actions):
                p = self.handplayers_name_cache[action[0]]
                a = HandAction()
                a.initFromImportedHand(action, actionNo=i, street=street, handPlayer=p)
                p.actions.append(a)

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

    def calcVpip(self, hand):
        vpipers = self.pfba(hand.actions[hand.actionStreets[1]], l=('calls','bets', 'raises'))
        self.playersVpi = len(vpipers)

    def calcPlayersAtStreetX(self, hand):
        """ playersAtStreet1 SMALLINT NOT NULL,   /* num of players seeing flop/street4/draw1 */"""
        # self.actions[street] is a list of all actions in a tuple, contining the player name first
        # [ (player, action, ....), (player2, action, ...) ]
        # The number of unique players in the list per street gives the value for playersAtStreetXXX

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
        self.playersAtShowdown = len(set.union(self.pfba(actions) - self.pfba(actions, l=('folds',)),  alliners))

    def calcStreetPotTotals(self, hand):
        for i in range(4): setattr(self, 'street%dPot' % (i+1), 0)

        for (i, street) in enumerate(hand.actionStreets[2:]):
            setattr(self, 'street%dPot' % (i+1), hand.pot.getTotalAtStreet(street))

        # FIXME: it's not showdown pot. it's pot for last street minus returned bets //grindi
        self.showdownPot = hand.pot.total

    def calcStreetXRaises(self, hand):
        # self.actions[street] is a list of all actions in a tuple, contining the action as the second element
        # [ (player, action, ....), (player2, action, ...) ]
        for i in range(5): setattr(self, 'street%dRaises' % i, 0)

        for (i, street) in enumerate(hand.actionStreets[1:]): 
            setattr(self, 'street%dRaises' % i, 
                    len(filter( lambda action: action[1] in ('raises','bets'), hand.actions[street])))

    def aggr(self, hand, i):
        aggrers = set()
        for act in hand.actions[hand.actionStreets[i]]:
            if act[1] in ('completes', 'raises'):
                aggrers.add(act[0])

        for player in hand.players:
            if player[1] in aggrers:
                self.handsplayers[player[1]]['street%sAggr' % i] = True
            else:
                self.handsplayers[player[1]]['street%sAggr' % i] = False

    def __str__(self):
        s = list()
        for i in self._sa_class_manager.mapper.c:
            s.append('%25s     %s' % (i, getattr(self, i.name)))

        s+=['', '']
        for i,p in enumerate(self.handPlayers):
            s.append('%d. %s' % (i, p.player.name or '???'))
        return '\n'.join(s)

    def assembleHudCache(self, hand):
        pass


class HandAction(object):
    """Class reflecting HandsActions db table"""
    def initFromImportedHand(self, action_tuple, actionNo=None, street=None, handPlayer=None):
        if actionNo is not None: self.actionNo = actionNo
        if handPlayer is not None: self.handPlayer = handPlayer
        if street is not None: self.street = street
        #import pdb; pdb.set_trace()
        action, extra = action_tuple[1], action_tuple[2:] # we don't need player name 
        self.action = action
        # FIXME: add support for 'discards'. I have no idea \
        # how to put discarded cards here \\grindi
            # The schema for draw games hasn't been decided - ignoring it is correct \\ Carl G
        if action in ('folds', 'checks', 'stands pat'):
            pass
        elif action in ('bets', 'calls', 'bringin'):
            self.amount, self.allIn = extra
        elif action == 'raises':
            Rb, Rt, C, self.allIn = extra
            self.amount = Rt 
        elif action == 'posts':
            blindtype, self.amount, self.allIn = extra
            self.action = '%s %s' % (action, blindtype)
        elif action == 'ante':
             self.amount, self.allIn = extra


class HandPlayer(object):
    """Class reflecting HandsPlayers db table"""
    def __init__(self, hand, importedHand, seat, name, chips):
        self.hand = hand # this string automagically appends self to hand.handPlayers
        self.seatNo = seat
        self.startCash = chips
        # db tbl doesn't have this field. But we need it to fetch Player later
        self.name = name 
        self.position = self.getPosition(importedHand, seat)
    
    @staticmethod
    def getPosition(hand, seat):
        """Returns position value like 'B', 'S', 0, 1, ...

        >>> class A(object): pass
        ... 
        >>> A.maxseats = 6
        >>> A.buttonpos = 2
        >>> A.gametype = {'base': 'hold'}
        >>> HandInternal.getPosition(A, 2)
        '0'
        >>> HandInternal.getPosition(A, 1)
        'B'
        >>> HandInternal.getPosition(A, 6)
        'S'
        """
        from itertools import chain
        if hand.gametype['base'] == 'stud':
            # FIXME: i've never played stud so plz check & del comment \\grindi
            bringin = None
            for action in chain(*[self.actions[street] for street in hand.allStreets]):
                if action[1]=='bringin':
                    bringin = action[0]
                    break
            if bringin is None:
                raise Exception, "Cannot find bringin"
            # name -> seat
            bringin = int(filter(lambda p: p[1]==bringin, bringin)[0])
            seat = (int(seat) - int(bringin))%int(hand.maxseats)
            return str(seat)
        else:
            seat = (int(seat) - int(hand.buttonpos) + 2)%int(hand.maxseats) - 2
            if seat == -2:
                return 'S'
            elif seat == -1:
                return 'B'
            else:
                return str(seat)

    @staticmethod
    def getActionMap(actions):
        """Helper fucntion. Returns dict: <pname: set of actions>"""
        amap = defaultdict(lambda: set(), {})
        for action in actions:
            amap[action[0]].add(action[1])
        return amap

    @staticmethod
    def applyImportedActions(handplayers, sorted_actions, collectees):
        """Applies actions from imported hand to HandPlayer object
        
        handplayers - dict(<player_name>: <HandPlayer object>
        actions     - list tuples (street, actions)
            like Hand.actions (Hand - is the imported hand, not internal)
            but sorted by street according to Hand.actionStreets
        collectees  - dict : (players (names) collected money, amount)
            """

        # FIXME: vvvvv REMOVE CODE BELOW. IT'S NEEDED JUST TO AVOID NOT NULL DB ERRORS
        for k in handplayers.iterkeys():
            hp = handplayers[k]
            hp.card1 = 0
            hp.card2 = 0
            hp.winnings = 0
            hp.rake = 0
            hp.tourneysPlayersId = 0
            hp.tourneyTypeId = 0
        # ^^^^^^^^

        winners = collectees.keys()         
        for i, t in enumerate(sorted_actions):
            street, actions = t
            ss = defaultdict(lambda: {}, {}) # street stats: dict of stats for each player
            amap = HandPlayer.getActionMap(actions)

            # lets calculate stats
            for name, hp in handplayers.iteritems(): # hp stands for hand player
                # FIXME: wonWhenSeenStreet%s is float so may be ammount won should be stored //grindi
                ss[name]['wonWhenSeenStreet%s'] =  len( amap[name] ) > 0 and name in winners 

            # FIXME: add other stats here //grindi

            # writing stats
            for p, stats in ss.iteritems():
                for k, v in stats.iteritems():
                    setattr(handplayers[p], k % i, v)

    def fetchIds(self, session):
        pass


mapper (HandAction, hands_actions_table, properties={})
mapper (HandPlayer, hands_players_table, properties={
    'actions': relation(HandAction, backref='handPlayer'),
})
mapper (HandInternal, hands_table, properties={
    'handPlayers': relation(HandPlayer, backref='hand'),
})
mapper (Player, players_table, properties={
    'playerHands': relation(HandPlayer, backref='player'),
})
mapper (Gametype, gametypes_table, properties={
    'hands': relation(HandInternal, backref='gametype'),
})
mapper (Site, sites_table, properties={
    'players': relation(Player, backref = 'site'),
    'gametypes': relation(Gametype, backref = 'site'),
})



