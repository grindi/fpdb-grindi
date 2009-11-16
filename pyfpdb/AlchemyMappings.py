# -*- coding: utf-8 -*-
"""@package AlchemyMappings
This package contains all classes to be mapped and mappers themselves
"""

import logging
from sqlalchemy.orm import mapper, relation
from decimal import Decimal
from collections import defaultdict

from AlchemyTables import *


class Site(object):
    """Class reflecting Players db table"""
    pass


class Player(object):
    """Class reflecting Players db table"""

    def __init__(self, name, siteId):
        self.name = name
        self.siteId = siteId

    @staticmethod
    def get_or_create(session, siteId, name):
        p = session.query(Player).filter_by(name=name, siteId=siteId).first()
        if p is None:
            p = Player(name, siteId)
            session.add(p)
        return p

    def __str__(self):
        return '<Player "%s" on %s>' % (self.name, self.site and self.site.name)


class Gametype(object):
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
        g = session.query(Gametype).filter_by(**gametype).first()
        if g is None:
            g = Gametype()
            for k, v in gametype.iteritems():
                setattr(g, k, v)
            session.add(g)
        return g


class HandInternal(object):
    """Class reflecting Hands db table"""

    def parseImportedHandStep1(self, hand):
        """Extracts values to insert into from hand returned by HHC. No db is needed he"""
        from itertools import chain
        from datetime import datetime

        hand.players = hand.getAlivePlayers() # FIXME: do we really want to do it? //grindi

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
        self.attachActions(hand)

        sorted_actions = [ (street, hand.actions[street]) for street in hand.actionStreets ]
        HandPlayer.applyImportedActions(self.handplayers_name_cache, sorted_actions, hand.collectees )

    def parseImportedHandStep2(self, session):
        """Fetching ids for gametypes and players. No flush """
        self.gametype = Gametype.get_or_create(session, self.siteId, self.gametype_dict)
        for hp in self.handPlayers:
            hp.player = Player.get_or_create(session, self.siteId, hp.name)
            for action in hp.actions:
                session.add(action)
        session.add(self)

    def parseImportedHandStep3(self, session):
        """Flushes the session"""
        session.flush()

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
#       # def generateHudCacheData(player_ids, base, category, action_types, allIns, actionTypeByNo
#       #                 ,winnings, totalWinnings, positions, actionTypes, actionAmounts, antes):
#       #"""calculates data for the HUD during import. IMPORTANT: if you change this method make
#       #   sure to also change the following storage method and table_viewer.prepare_data if necessary
#       #"""
#            #print "generateHudCacheData, len(player_ids)=", len(player_ids)
#            #setup subarrays of the result dictionary.
#            street0VPI=[]
#            street0Aggr=[]
#            street0_3BChance=[]
#            street0_3BDone=[]
#            street1Seen=[]
#            street2Seen=[]
#            street3Seen=[]
#            street4Seen=[]
#            sawShowdown=[]
#            street1Aggr=[]
#            street2Aggr=[]
#            street3Aggr=[]
#            street4Aggr=[]
#            otherRaisedStreet1=[]
#            otherRaisedStreet2=[]
#            otherRaisedStreet3=[]
#            otherRaisedStreet4=[]
#            foldToOtherRaisedStreet1=[]
#            foldToOtherRaisedStreet2=[]
#            foldToOtherRaisedStreet3=[]
#            foldToOtherRaisedStreet4=[]
#            wonWhenSeenStreet1=[]
#
#            wonAtSD=[]
#            stealAttemptChance=[]
#            stealAttempted=[]
#            hudDataPositions=[]
#
#            street0Calls=[]
#            street1Calls=[]
#            street2Calls=[]
#            street3Calls=[]
#            street4Calls=[]
#            street0Bets=[]
#            street1Bets=[]
#            street2Bets=[]
#            street3Bets=[]
#            street4Bets=[]
#            #street0Raises=[]
#            #street1Raises=[]
#            #street2Raises=[]
#            #street3Raises=[]
#            #street4Raises=[]
#
#            # Summary figures for hand table:
#            result={}
#            result['playersVpi']=0
#            result['playersAtStreet1']=0
#            result['playersAtStreet2']=0
#            result['playersAtStreet3']=0
#            result['playersAtStreet4']=0
#            result['playersAtShowdown']=0
#            result['street0Raises']=0
#            result['street1Raises']=0
#            result['street2Raises']=0
#            result['street3Raises']=0
#            result['street4Raises']=0
#            result['street1Pot']=0
#            result['street2Pot']=0
#            result['street3Pot']=0
#            result['street4Pot']=0
#            result['showdownPot']=0
#
#            firstPfRaiseByNo=-1
#            firstPfRaiserId=-1
#            firstPfRaiserNo=-1
#            firstPfCallByNo=-1
#            firstPfCallerId=-1
#
#            for i, action in enumerate(actionTypeByNo[0]):
#                if action[1] == "bet":
#                    firstPfRaiseByNo = i
#                    firstPfRaiserId = action[0]
#                    for j, pid in enumerate(player_ids):
#                        if pid == firstPfRaiserId:
#                            firstPfRaiserNo = j
#                            break
#                    break
#            for i, action in enumerate(actionTypeByNo[0]):
#                if action[1] == "call":
#                    firstPfCallByNo = i
#                    firstPfCallerId = action[0]
#                    break
#            firstPlayId = firstPfCallerId
#            if firstPfRaiseByNo <> -1:
#                if firstPfRaiseByNo < firstPfCallByNo or firstPfCallByNo == -1:
#                    firstPlayId = firstPfRaiserId
#
#
#            cutoffId=-1
#            buttonId=-1
#            sbId=-1
#            bbId=-1
#            if base=="hold":
#                for player, pos in enumerate(positions):
#                    if pos == 1:
#                        cutoffId = player_ids[player]
#                    if pos == 0:
#                        buttonId = player_ids[player]
#                    if pos == 'S':
#                        sbId = player_ids[player]
#                    if pos == 'B':
#                        bbId = player_ids[player]
#
#            someoneStole=False
#
#            #run a loop for each player preparing the actual values that will be commited to SQL
#            for player in xrange(len(player_ids)):
#                #set default values
#                myStreet0VPI=False
#                myStreet0Aggr=False
#                myStreet0_3BChance=False
#                myStreet0_3BDone=False
#                myStreet1Seen=False
#                myStreet2Seen=False
#                myStreet3Seen=False
#                myStreet4Seen=False
#                mySawShowdown=False
#                myStreet1Aggr=False
#                myStreet2Aggr=False
#                myStreet3Aggr=False
#                myStreet4Aggr=False
#                myOtherRaisedStreet1=False
#                myOtherRaisedStreet2=False
#                myOtherRaisedStreet3=False
#                myOtherRaisedStreet4=False
#                myFoldToOtherRaisedStreet1=False
#                myFoldToOtherRaisedStreet2=False
#                myFoldToOtherRaisedStreet3=False
#                myFoldToOtherRaisedStreet4=False
#                myWonWhenSeenStreet1=0.0
#                myWonAtSD=0.0
#                myStealAttemptChance=False
#                myStealAttempted=False
#                myStreet0Calls=0
#                myStreet1Calls=0
#                myStreet2Calls=0
#                myStreet3Calls=0
#                myStreet4Calls=0
#                myStreet0Bets=0
#                myStreet1Bets=0
#                myStreet2Bets=0
#                myStreet3Bets=0
#                myStreet4Bets=0
#                #myStreet0Raises=0
#                #myStreet1Raises=0
#                #myStreet2Raises=0
#                #myStreet3Raises=0
#                #myStreet4Raises=0
#
#                #calculate VPIP and PFR
#                street=0
#                heroPfRaiseCount=0
#                for currentAction in action_types[street][player]: # finally individual actions
#                    if currentAction == "bet":
#                        myStreet0Aggr = True
#                    if currentAction == "bet" or currentAction == "call":
#                        myStreet0VPI = True
#
#                if myStreet0VPI:
#                    result['playersVpi'] += 1
#                myStreet0Calls = action_types[street][player].count('call')
#                myStreet0Bets = action_types[street][player].count('bet')
#                # street0Raises = action_types[street][player].count('raise')  bet count includes raises for now
#                result['street0Raises'] += myStreet0Bets
#
#                #PF3BChance and PF3B
#                pfFold=-1
#                pfRaise=-1
#                if firstPfRaiseByNo != -1:
#                    for i, actionType in enumerate(actionTypeByNo[0]):
#                        if actionType[0] == player_ids[player]:
#                            if actionType[1] == "bet" and pfRaise == -1 and i > firstPfRaiseByNo:
#                                pfRaise = i
#                            if actionType[1] == "fold" and pfFold == -1:
#                                pfFold = i
#                    if pfFold == -1 or pfFold > firstPfRaiseByNo:
#                        myStreet0_3BChance = True
#                        if pfRaise > firstPfRaiseByNo:
#                            myStreet0_3BDone = True
#
#                #steal calculations
#                if base=="hold":
#                    if len(player_ids)>=3: # no point otherwise  # was 5, use 3 to match pokertracker definition
#                        if positions[player]==1:
#                            if      firstPfRaiserId==player_ids[player] \
#                               and (firstPfCallByNo==-1 or firstPfCallByNo>firstPfRaiseByNo):
#                                myStealAttempted=True
#                                myStealAttemptChance=True
#                            if firstPlayId==cutoffId or firstPlayId==buttonId or firstPlayId==sbId or firstPlayId==bbId or firstPlayId==-1:
#                                myStealAttemptChance=True
#                        if positions[player]==0:
#                            if      firstPfRaiserId==player_ids[player] \
#                               and (firstPfCallByNo==-1 or firstPfCallByNo>firstPfRaiseByNo):
#                                myStealAttempted=True
#                                myStealAttemptChance=True
#                            if firstPlayId==buttonId or firstPlayId==sbId or firstPlayId==bbId or firstPlayId==-1:
#                                myStealAttemptChance=True
#                        if positions[player]=='S':
#                            if      firstPfRaiserId==player_ids[player] \
#                               and (firstPfCallByNo==-1 or firstPfCallByNo>firstPfRaiseByNo):
#                                myStealAttempted=True
#                                myStealAttemptChance=True
#                            if firstPlayId==sbId or firstPlayId==bbId or firstPlayId==-1:
#                                myStealAttemptChance=True
#                        if positions[player]=='B':
#                            pass
#
#                        if myStealAttempted:
#                            someoneStole=True
#
#
#                #calculate saw* values
#                isAllIn = False
#                if any(i for i in allIns[0][player]):
#                    isAllIn = True
#                if (len(action_types[1][player])>0 or isAllIn):
#                    myStreet1Seen = True
#
#                    if any(i for i in allIns[1][player]):
#                        isAllIn = True
#                    if (len(action_types[2][player])>0 or isAllIn):
#                        myStreet2Seen = True
#
#                        if any(i for i in allIns[2][player]):
#                            isAllIn = True
#                        if (len(action_types[3][player])>0 or isAllIn):
#                            myStreet3Seen = True
#
#                            #print "base:", base
#                            if base=="hold":
#                                mySawShowdown = True
#                                if any(actiontype == "fold" for actiontype in action_types[3][player]):
#                                    mySawShowdown = False
#                            else:
#                                #print "in else"
#                                if any(i for i in allIns[3][player]):
#                                    isAllIn = True
#                                if (len(action_types[4][player])>0 or isAllIn):
#                                    #print "in if"
#                                    myStreet4Seen = True
#
#                                    mySawShowdown = True
#                                    if any(actiontype == "fold" for actiontype in action_types[4][player]):
#                                        mySawShowdown = False
#
#                if myStreet1Seen:
#                    result['playersAtStreet1'] += 1
#                if myStreet2Seen:
#                    result['playersAtStreet2'] += 1
#                if myStreet3Seen:
#                    result['playersAtStreet3'] += 1
#                if myStreet4Seen:
#                    result['playersAtStreet4'] += 1
#                if mySawShowdown:
#                    result['playersAtShowdown'] += 1
#
#                #flop stuff
#                street=1
#                if myStreet1Seen:
#                    if any(actiontype == "bet" for actiontype in action_types[street][player]):
#                        myStreet1Aggr = True
#
#                    myStreet1Calls = action_types[street][player].count('call')
#                    myStreet1Bets = action_types[street][player].count('bet')
#                    # street1Raises = action_types[street][player].count('raise')  bet count includes raises for now
#                    result['street1Raises'] += myStreet1Bets
#
#                    for otherPlayer in xrange(len(player_ids)):
#                        if player==otherPlayer:
#                            pass
#                        else:
#                            for countOther in xrange(len(action_types[street][otherPlayer])):
#                                if action_types[street][otherPlayer][countOther]=="bet":
#                                    myOtherRaisedStreet1=True
#                                    for countOtherFold in xrange(len(action_types[street][player])):
#                                        if action_types[street][player][countOtherFold]=="fold":
#                                            myFoldToOtherRaisedStreet1=True
#
#                #turn stuff - copy of flop with different vars
#                street=2
#                if myStreet2Seen:
#                    if any(actiontype == "bet" for actiontype in action_types[street][player]):
#                        myStreet2Aggr = True
#
#                    myStreet2Calls = action_types[street][player].count('call')
#                    myStreet2Bets = action_types[street][player].count('bet')
#                    # street2Raises = action_types[street][player].count('raise')  bet count includes raises for now
#                    result['street2Raises'] += myStreet2Bets
#
#                    for otherPlayer in xrange(len(player_ids)):
#                        if player==otherPlayer:
#                            pass
#                        else:
#                            for countOther in xrange(len(action_types[street][otherPlayer])):
#                                if action_types[street][otherPlayer][countOther]=="bet":
#                                    myOtherRaisedStreet2=True
#                                    for countOtherFold in xrange(len(action_types[street][player])):
#                                        if action_types[street][player][countOtherFold]=="fold":
#                                            myFoldToOtherRaisedStreet2=True
#
#                #river stuff - copy of flop with different vars
#                street=3
#                if myStreet3Seen:
#                    if any(actiontype == "bet" for actiontype in action_types[street][player]):
#                            myStreet3Aggr = True
#
#                    myStreet3Calls = action_types[street][player].count('call')
#                    myStreet3Bets = action_types[street][player].count('bet')
#                    # street3Raises = action_types[street][player].count('raise')  bet count includes raises for now
#                    result['street3Raises'] += myStreet3Bets
#
#                    for otherPlayer in xrange(len(player_ids)):
#                        if player==otherPlayer:
#                            pass
#                        else:
#                            for countOther in xrange(len(action_types[street][otherPlayer])):
#                                if action_types[street][otherPlayer][countOther]=="bet":
#                                    myOtherRaisedStreet3=True
#                                    for countOtherFold in xrange(len(action_types[street][player])):
#                                        if action_types[street][player][countOtherFold]=="fold":
#                                            myFoldToOtherRaisedStreet3=True
#
#                #stud river stuff - copy of flop with different vars
#                street=4
#                if myStreet4Seen:
#                    if any(actiontype == "bet" for actiontype in action_types[street][player]):
#                        myStreet4Aggr=True
#
#                    myStreet4Calls = action_types[street][player].count('call')
#                    myStreet4Bets = action_types[street][player].count('bet')
#                    # street4Raises = action_types[street][player].count('raise')  bet count includes raises for now
#                    result['street4Raises'] += myStreet4Bets
#
#                    for otherPlayer in xrange(len(player_ids)):
#                        if player==otherPlayer:
#                            pass
#                        else:
#                            for countOther in xrange(len(action_types[street][otherPlayer])):
#                                if action_types[street][otherPlayer][countOther]=="bet":
#                                    myOtherRaisedStreet4=True
#                                    for countOtherFold in xrange(len(action_types[street][player])):
#                                        if action_types[street][player][countOtherFold]=="fold":
#                                            myFoldToOtherRaisedStreet4=True
#
#                if winnings[player] != 0:
#                    if myStreet1Seen:
#                        myWonWhenSeenStreet1 = winnings[player] / float(totalWinnings)
#                        if mySawShowdown:
#                            myWonAtSD=myWonWhenSeenStreet1
#
#                #add each value to the appropriate array
#                street0VPI.append(myStreet0VPI)
#                street0Aggr.append(myStreet0Aggr)
#                street0_3BChance.append(myStreet0_3BChance)
#                street0_3BDone.append(myStreet0_3BDone)
#                street1Seen.append(myStreet1Seen)
#                street2Seen.append(myStreet2Seen)
#                street3Seen.append(myStreet3Seen)
#                street4Seen.append(myStreet4Seen)
#                sawShowdown.append(mySawShowdown)
#                street1Aggr.append(myStreet1Aggr)
#                street2Aggr.append(myStreet2Aggr)
#                street3Aggr.append(myStreet3Aggr)
#                street4Aggr.append(myStreet4Aggr)
#                otherRaisedStreet1.append(myOtherRaisedStreet1)
#                otherRaisedStreet2.append(myOtherRaisedStreet2)
#                otherRaisedStreet3.append(myOtherRaisedStreet3)
#                otherRaisedStreet4.append(myOtherRaisedStreet4)
#                foldToOtherRaisedStreet1.append(myFoldToOtherRaisedStreet1)
#                foldToOtherRaisedStreet2.append(myFoldToOtherRaisedStreet2)
#                foldToOtherRaisedStreet3.append(myFoldToOtherRaisedStreet3)
#                foldToOtherRaisedStreet4.append(myFoldToOtherRaisedStreet4)
#                wonWhenSeenStreet1.append(myWonWhenSeenStreet1)
#                wonAtSD.append(myWonAtSD)
#                stealAttemptChance.append(myStealAttemptChance)
#                stealAttempted.append(myStealAttempted)
#                if base=="hold":
#                    pos=positions[player]
#                    if pos=='B':
#                        hudDataPositions.append('B')
#                    elif pos=='S':
#                        hudDataPositions.append('S')
#                    elif pos==0:
#                        hudDataPositions.append('D')
#                    elif pos==1:
#                        hudDataPositions.append('C')
#                    elif pos>=2 and pos<=4:
#                        hudDataPositions.append('M')
#                    elif pos>=5 and pos<=8:
#                        hudDataPositions.append('E')
#                    ### RHH Added this elif to handle being a dead hand before the BB (pos==9)
#                    elif pos==9:
#                        hudDataPositions.append('X')
#                    else:
#                        raise FpdbError("invalid position")
#                elif base=="stud":
#                    #todo: stud positions and steals
#                    pass
#
#                street0Calls.append(myStreet0Calls)
#                street1Calls.append(myStreet1Calls)
#                street2Calls.append(myStreet2Calls)
#                street3Calls.append(myStreet3Calls)
#                street4Calls.append(myStreet4Calls)
#                street0Bets.append(myStreet0Bets)
#                street1Bets.append(myStreet1Bets)
#                street2Bets.append(myStreet2Bets)
#                street3Bets.append(myStreet3Bets)
#                street4Bets.append(myStreet4Bets)
#                #street0Raises.append(myStreet0Raises)
#                #street1Raises.append(myStreet1Raises)
#                #street2Raises.append(myStreet2Raises)
#                #street3Raises.append(myStreet3Raises)
#                #street4Raises.append(myStreet4Raises)
#
#            #add each array to the to-be-returned dictionary
#            result['street0VPI']=street0VPI
#            result['street0Aggr']=street0Aggr
#            result['street0_3BChance']=street0_3BChance
#            result['street0_3BDone']=street0_3BDone
#            result['street1Seen']=street1Seen
#            result['street2Seen']=street2Seen
#            result['street3Seen']=street3Seen
#            result['street4Seen']=street4Seen
#            result['sawShowdown']=sawShowdown
#
#            result['street1Aggr']=street1Aggr
#            result['otherRaisedStreet1']=otherRaisedStreet1
#            result['foldToOtherRaisedStreet1']=foldToOtherRaisedStreet1
#            result['street2Aggr']=street2Aggr
#            result['otherRaisedStreet2']=otherRaisedStreet2
#            result['foldToOtherRaisedStreet2']=foldToOtherRaisedStreet2
#            result['street3Aggr']=street3Aggr
#            result['otherRaisedStreet3']=otherRaisedStreet3
#            result['foldToOtherRaisedStreet3']=foldToOtherRaisedStreet3
#            result['street4Aggr']=street4Aggr
#            result['otherRaisedStreet4']=otherRaisedStreet4
#            result['foldToOtherRaisedStreet4']=foldToOtherRaisedStreet4
#            result['wonWhenSeenStreet1']=wonWhenSeenStreet1
#            result['wonAtSD']=wonAtSD
#            result['stealAttemptChance']=stealAttemptChance
#            result['stealAttempted']=stealAttempted
#            result['street0Calls']=street0Calls
#            result['street1Calls']=street1Calls
#            result['street2Calls']=street2Calls
#            result['street3Calls']=street3Calls
#            result['street4Calls']=street4Calls
#            result['street0Bets']=street0Bets
#            result['street1Bets']=street1Bets
#            result['street2Bets']=street2Bets
#            result['street3Bets']=street3Bets
#            result['street4Bets']=street4Bets
#            #result['street0Raises']=street0Raises
#            #result['street1Raises']=street1Raises
#            #result['street2Raises']=street2Raises
#            #result['street3Raises']=street3Raises
#            #result['street4Raises']=street4Raises
#
#            #now the various steal values
#            foldBbToStealChance=[]
#            foldedBbToSteal=[]
#            foldSbToStealChance=[]
#            foldedSbToSteal=[]
#            for player in xrange(len(player_ids)):
#                myFoldBbToStealChance=False
#                myFoldedBbToSteal=False
#                myFoldSbToStealChance=False
#                myFoldedSbToSteal=False
#
#                if base=="hold":
#                    if someoneStole and (positions[player]=='B' or positions[player]=='S') and firstPfRaiserId!=player_ids[player]:
#                        street=0
#                        for count in xrange(len(action_types[street][player])):#individual actions
#                            if positions[player]=='B':
#                                myFoldBbToStealChance=True
#                                if action_types[street][player][count]=="fold":
#                                    myFoldedBbToSteal=True
#                            if positions[player]=='S':
#                                myFoldSbToStealChance=True
#                                if action_types[street][player][count]=="fold":
#                                    myFoldedSbToSteal=True
#
#
#                foldBbToStealChance.append(myFoldBbToStealChance)
#                foldedBbToSteal.append(myFoldedBbToSteal)
#                foldSbToStealChance.append(myFoldSbToStealChance)
#                foldedSbToSteal.append(myFoldedSbToSteal)
#            result['foldBbToStealChance']=foldBbToStealChance
#            result['foldedBbToSteal']=foldedBbToSteal
#            result['foldSbToStealChance']=foldSbToStealChance
#            result['foldedSbToSteal']=foldedSbToSteal
#
#            #now CB
#            street1CBChance=[]
#            street1CBDone=[]
#            didStreet1CB=[]
#            for player in xrange(len(player_ids)):
#                myStreet1CBChance=False
#                myStreet1CBDone=False
#
#                if street0VPI[player]:
#                    myStreet1CBChance=True
#                    if street1Aggr[player]:
#                        myStreet1CBDone=True
#                        didStreet1CB.append(player_ids[player])
#
#                street1CBChance.append(myStreet1CBChance)
#                street1CBDone.append(myStreet1CBDone)
#            result['street1CBChance']=street1CBChance
#            result['street1CBDone']=street1CBDone
#
#            #now 2B
#            street2CBChance=[]
#            street2CBDone=[]
#            didStreet2CB=[]
#            for player in xrange(len(player_ids)):
#                myStreet2CBChance=False
#                myStreet2CBDone=False
#
#                if street1CBDone[player]:
#                    myStreet2CBChance=True
#                    if street2Aggr[player]:
#                        myStreet2CBDone=True
#                        didStreet2CB.append(player_ids[player])
#
#                street2CBChance.append(myStreet2CBChance)
#                street2CBDone.append(myStreet2CBDone)
#            result['street2CBChance']=street2CBChance
#            result['street2CBDone']=street2CBDone
#
#            #now 3B
#            street3CBChance=[]
#            street3CBDone=[]
#            didStreet3CB=[]
#            for player in xrange(len(player_ids)):
#                myStreet3CBChance=False
#                myStreet3CBDone=False
#
#                if street2CBDone[player]:
#                    myStreet3CBChance=True
#                    if street3Aggr[player]:
#                        myStreet3CBDone=True
#                        didStreet3CB.append(player_ids[player])
#
#                street3CBChance.append(myStreet3CBChance)
#                street3CBDone.append(myStreet3CBDone)
#            result['street3CBChance']=street3CBChance
#            result['street3CBDone']=street3CBDone
#
#            #and 4B
#            street4CBChance=[]
#            street4CBDone=[]
#            didStreet4CB=[]
#            for player in xrange(len(player_ids)):
#                myStreet4CBChance=False
#                myStreet4CBDone=False
#
#                if street3CBDone[player]:
#                    myStreet4CBChance=True
#                    if street4Aggr[player]:
#                        myStreet4CBDone=True
#                        didStreet4CB.append(player_ids[player])
#
#                street4CBChance.append(myStreet4CBChance)
#                street4CBDone.append(myStreet4CBDone)
#            result['street4CBChance']=street4CBChance
#            result['street4CBDone']=street4CBDone
#
#
#            result['position']=hudDataPositions
#
#            foldToStreet1CBChance=[]
#            foldToStreet1CBDone=[]
#            foldToStreet2CBChance=[]
#            foldToStreet2CBDone=[]
#            foldToStreet3CBChance=[]
#            foldToStreet3CBDone=[]
#            foldToStreet4CBChance=[]
#            foldToStreet4CBDone=[]
#
#            for player in xrange(len(player_ids)):
#                myFoldToStreet1CBChance=False
#                myFoldToStreet1CBDone=False
#                foldToStreet1CBChance.append(myFoldToStreet1CBChance)
#                foldToStreet1CBDone.append(myFoldToStreet1CBDone)
#
#                myFoldToStreet2CBChance=False
#                myFoldToStreet2CBDone=False
#                foldToStreet2CBChance.append(myFoldToStreet2CBChance)
#                foldToStreet2CBDone.append(myFoldToStreet2CBDone)
#
#                myFoldToStreet3CBChance=False
#                myFoldToStreet3CBDone=False
#                foldToStreet3CBChance.append(myFoldToStreet3CBChance)
#                foldToStreet3CBDone.append(myFoldToStreet3CBDone)
#
#                myFoldToStreet4CBChance=False
#                myFoldToStreet4CBDone=False
#                foldToStreet4CBChance.append(myFoldToStreet4CBChance)
#                foldToStreet4CBDone.append(myFoldToStreet4CBDone)
#
#            if len(didStreet1CB)>=1:
#                generateFoldToCB(1, player_ids, didStreet1CB, street1CBDone, foldToStreet1CBChance, foldToStreet1CBDone, actionTypeByNo)
#
#                if len(didStreet2CB)>=1:
#                    generateFoldToCB(2, player_ids, didStreet2CB, street2CBDone, foldToStreet2CBChance, foldToStreet2CBDone, actionTypeByNo)
#
#                    if len(didStreet3CB)>=1:
#                        generateFoldToCB(3, player_ids, didStreet3CB, street3CBDone, foldToStreet3CBChance, foldToStreet3CBDone, actionTypeByNo)
#
#                        if len(didStreet4CB)>=1:
#                            generateFoldToCB(4, player_ids, didStreet4CB, street4CBDone, foldToStreet4CBChance, foldToStreet4CBDone, actionTypeByNo)
#
#            result['foldToStreet1CBChance']=foldToStreet1CBChance
#            result['foldToStreet1CBDone']=foldToStreet1CBDone
#            result['foldToStreet2CBChance']=foldToStreet2CBChance
#            result['foldToStreet2CBDone']=foldToStreet2CBDone
#            result['foldToStreet3CBChance']=foldToStreet3CBChance
#            result['foldToStreet3CBDone']=foldToStreet3CBDone
#            result['foldToStreet4CBChance']=foldToStreet4CBChance
#            result['foldToStreet4CBDone']=foldToStreet4CBDone
#
#
#            totalProfit=[]
#
#            street1CheckCallRaiseChance=[]
#            street1CheckCallRaiseDone=[]
#            street2CheckCallRaiseChance=[]
#            street2CheckCallRaiseDone=[]
#            street3CheckCallRaiseChance=[]
#            street3CheckCallRaiseDone=[]
#            street4CheckCallRaiseChance=[]
#            street4CheckCallRaiseDone=[]
#            #print "b4 totprof calc, len(playerIds)=", len(player_ids)
#            for pl in xrange(len(player_ids)):
#                #print "pl=", pl
#                myTotalProfit=winnings[pl]  # still need to deduct other costs
#                if antes:
#                    myTotalProfit=winnings[pl] - antes[pl]
#                for i in xrange(len(actionTypes)): #iterate through streets
#                    #for j in xrange(len(actionTypes[i])): #iterate through names (using pl loop above)
#                        for k in xrange(len(actionTypes[i][pl])): #iterate through individual actions of that player on that street
#                            myTotalProfit -= actionAmounts[i][pl][k]
#
#                myStreet1CheckCallRaiseChance=False
#                myStreet1CheckCallRaiseDone=False
#                myStreet2CheckCallRaiseChance=False
#                myStreet2CheckCallRaiseDone=False
#                myStreet3CheckCallRaiseChance=False
#                myStreet3CheckCallRaiseDone=False
#                myStreet4CheckCallRaiseChance=False
#                myStreet4CheckCallRaiseDone=False
#
#                #print "myTotalProfit=", myTotalProfit
#                totalProfit.append(myTotalProfit)
#                #print "totalProfit[]=", totalProfit
#
#                street1CheckCallRaiseChance.append(myStreet1CheckCallRaiseChance)
#                street1CheckCallRaiseDone.append(myStreet1CheckCallRaiseDone)
#                street2CheckCallRaiseChance.append(myStreet2CheckCallRaiseChance)
#                street2CheckCallRaiseDone.append(myStreet2CheckCallRaiseDone)
#                street3CheckCallRaiseChance.append(myStreet3CheckCallRaiseChance)
#                street3CheckCallRaiseDone.append(myStreet3CheckCallRaiseDone)
#                street4CheckCallRaiseChance.append(myStreet4CheckCallRaiseChance)
#                street4CheckCallRaiseDone.append(myStreet4CheckCallRaiseDone)
#
#            result['totalProfit']=totalProfit
#            #print "res[totalProfit]=", result['totalProfit']
#
#            result['street1CheckCallRaiseChance']=street1CheckCallRaiseChance
#            result['street1CheckCallRaiseDone']=street1CheckCallRaiseDone
#            result['street2CheckCallRaiseChance']=street2CheckCallRaiseChance
#            result['street2CheckCallRaiseDone']=street2CheckCallRaiseDone
#            result['street3CheckCallRaiseChance']=street3CheckCallRaiseChance
#            result['street3CheckCallRaiseDone']=street3CheckCallRaiseDone
#            result['street4CheckCallRaiseChance']=street4CheckCallRaiseChance
#            result['street4CheckCallRaiseDone']=street4CheckCallRaiseDone
#            return result
#        #end def generateHudCacheData
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
        winners = collectees .keys()         
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
    'actions': relation(HandAction, backref='handPlayer', cascade='all, delete-orphan'),
})
mapper (HandInternal, hands_table, properties={
    'handPlayers': relation(HandPlayer, backref='hand', cascade='all, delete-orphan'),
})
mapper (Player, players_table, properties={
    'playerHands': relation(HandPlayer, backref='player', cascade='all'),
})
mapper (Gametype, gametypes_table, properties={
    'hands': relation(HandInternal, backref='gametype', cascade='all'),
})
mapper (Site, sites_table, properties={
    'players': relation(Player, backref = 'site', cascade = 'all'),
    'gametypes': relation(Gametype, backref = 'site', cascade = 'all'),
})



