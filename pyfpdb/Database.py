#!/usr/bin/env python
"""Database.py

Create and manage the database objects.
"""
#    Copyright 2008, Ray E. Barker
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

# ToDo:  - rebuild indexes / vacuum option
#        - check speed of get_stats_from_hand() - add log info
#        - check size of db, seems big? (mysql)
#        - investigate size of mysql db (200K for just 7K hands? 2GB for 140K hands?)

# postmaster -D /var/lib/pgsql/data

#    Standard Library modules
import os
import sys
import traceback
from datetime import datetime, date, time, timedelta
from time import time, strftime, sleep
from decimal import Decimal
import string
import re
import Queue

#    pyGTK modules

#    FreePokerTools modules
import fpdb_db
import Configuration
import SQL
import Card
import Tourney
from Exceptions import *

log = Configuration.get_logger("logging.conf")

class Database:

    MYSQL_INNODB = 2
    PGSQL = 3
    SQLITE = 4

    hero_hudstart_def = '1999-12-31'      # default for length of Hero's stats in HUD
    villain_hudstart_def = '1999-12-31'   # default for length of Villain's stats in HUD

    # Data Structures for index and foreign key creation
    # drop_code is an int with possible values:  0 - don't drop for bulk import
    #                                            1 - drop during bulk import
    # db differences: 
    # - note that mysql automatically creates indexes on constrained columns when
    #   foreign keys are created, while postgres does not. Hence the much longer list
    #   of indexes is required for postgres.
    # all primary keys are left on all the time
    #
    #             table     column           drop_code

    indexes = [
                [ ] # no db with index 0
              , [ ] # no db with index 1
              , [ # indexes for mysql (list index 2) (foreign keys not here, in next data structure)
                #  {'tab':'Players',         'col':'name',              'drop':0}  unique indexes not dropped
                #  {'tab':'Hands',           'col':'siteHandNo',        'drop':0}  unique indexes not dropped
                #, {'tab':'Tourneys',        'col':'siteTourneyNo',     'drop':0}  unique indexes not dropped
                ]
              , [ # indexes for postgres (list index 3)
                  {'tab':'Gametypes',       'col':'siteId',            'drop':0}
                , {'tab':'Hands',           'col':'gametypeId',        'drop':0} # mct 22/3/09
                #, {'tab':'Hands',           'col':'siteHandNo',        'drop':0}  unique indexes not dropped
                , {'tab':'HandsActions',    'col':'handsPlayerId',     'drop':0}
                , {'tab':'HandsPlayers',    'col':'handId',            'drop':1}
                , {'tab':'HandsPlayers',    'col':'playerId',          'drop':1}
                , {'tab':'HandsPlayers',    'col':'tourneysPlayersId', 'drop':0}
                , {'tab':'HudCache',        'col':'gametypeId',        'drop':1}
                , {'tab':'HudCache',        'col':'playerId',          'drop':0}
                , {'tab':'HudCache',        'col':'tourneyTypeId',     'drop':0}
                , {'tab':'Players',         'col':'siteId',            'drop':1}
                #, {'tab':'Players',         'col':'name',              'drop':0}  unique indexes not dropped
                , {'tab':'Tourneys',        'col':'tourneyTypeId',     'drop':1}
                #, {'tab':'Tourneys',        'col':'siteTourneyNo',     'drop':0}  unique indexes not dropped
                , {'tab':'TourneysPlayers', 'col':'playerId',          'drop':0}
                #, {'tab':'TourneysPlayers', 'col':'tourneyId',         'drop':0}  unique indexes not dropped
                , {'tab':'TourneyTypes',    'col':'siteId',            'drop':0}
                ]
              , [ # indexes for sqlite (list index 4)
                #  {'tab':'Players',         'col':'name',              'drop':0}  unique indexes not dropped
                #  {'tab':'Hands',           'col':'siteHandNo',        'drop':0}  unique indexes not dropped
                  {'tab':'Hands',           'col':'gametypeId',        'drop':0}
                , {'tab':'HandsPlayers',    'col':'handId',            'drop':0} 
                , {'tab':'HandsPlayers',    'col':'playerId',          'drop':0}
                , {'tab':'HandsPlayers',    'col':'tourneyTypeId',     'drop':0}
                , {'tab':'HandsPlayers',    'col':'tourneysPlayersId', 'drop':0}
                #, {'tab':'Tourneys',        'col':'siteTourneyNo',     'drop':0}  unique indexes not dropped
                ]
              ]

    foreignKeys = [
                    [ ] # no db with index 0
                  , [ ] # no db with index 1
                  , [ # foreign keys for mysql (index 2)
                      {'fktab':'Hands',        'fkcol':'gametypeId',    'rtab':'Gametypes',     'rcol':'id', 'drop':1}
                    , {'fktab':'HandsPlayers', 'fkcol':'handId',        'rtab':'Hands',         'rcol':'id', 'drop':1}
                    , {'fktab':'HandsPlayers', 'fkcol':'playerId',      'rtab':'Players',       'rcol':'id', 'drop':1}
                    , {'fktab':'HandsPlayers', 'fkcol':'tourneyTypeId', 'rtab':'TourneyTypes',  'rcol':'id', 'drop':1}
                    , {'fktab':'HandsPlayers', 'fkcol':'tourneysPlayersId','rtab':'TourneysPlayers','rcol':'id', 'drop':1}
                    , {'fktab':'HandsActions', 'fkcol':'handsPlayerId', 'rtab':'HandsPlayers',  'rcol':'id', 'drop':1}
                    , {'fktab':'HudCache',     'fkcol':'gametypeId',    'rtab':'Gametypes',     'rcol':'id', 'drop':1}
                    , {'fktab':'HudCache',     'fkcol':'playerId',      'rtab':'Players',       'rcol':'id', 'drop':0}
                    , {'fktab':'HudCache',     'fkcol':'tourneyTypeId', 'rtab':'TourneyTypes',  'rcol':'id', 'drop':1}
                    ]
                  , [ # foreign keys for postgres (index 3)
                      {'fktab':'Hands',        'fkcol':'gametypeId',    'rtab':'Gametypes',     'rcol':'id', 'drop':1}
                    , {'fktab':'HandsPlayers', 'fkcol':'handId',        'rtab':'Hands',         'rcol':'id', 'drop':1}
                    , {'fktab':'HandsPlayers', 'fkcol':'playerId',      'rtab':'Players',       'rcol':'id', 'drop':1}
                    , {'fktab':'HandsActions', 'fkcol':'handsPlayerId', 'rtab':'HandsPlayers',  'rcol':'id', 'drop':1}
                    , {'fktab':'HudCache',     'fkcol':'gametypeId',    'rtab':'Gametypes',     'rcol':'id', 'drop':1}
                    , {'fktab':'HudCache',     'fkcol':'playerId',      'rtab':'Players',       'rcol':'id', 'drop':0}
                    , {'fktab':'HudCache',     'fkcol':'tourneyTypeId', 'rtab':'TourneyTypes',  'rcol':'id', 'drop':1}
                    ]
                  , [ # no foreign keys in sqlite (index 4)
                    ]
                  ]


    # MySQL Notes:
    #    "FOREIGN KEY (handId) REFERENCES Hands(id)" - requires index on Hands.id
    #                                                - creates index handId on <thistable>.handId
    # alter table t drop foreign key fk
    # alter table t add foreign key (fkcol) references tab(rcol)
    # alter table t add constraint c foreign key (fkcol) references tab(rcol)
    # (fkcol is used for foreigh key name)

    # mysql to list indexes:
    #   SELECT table_name, index_name, non_unique, column_name 
    #   FROM INFORMATION_SCHEMA.STATISTICS
    #     WHERE table_name = 'tbl_name'
    #     AND table_schema = 'db_name'
    #   ORDER BY table_name, index_name, seq_in_index
    #
    # ALTER TABLE Tourneys ADD INDEX siteTourneyNo(siteTourneyNo)
    # ALTER TABLE tab DROP INDEX idx

    # mysql to list fks:
    #   SELECT constraint_name, table_name, column_name, referenced_table_name, referenced_column_name
    #   FROM information_schema.KEY_COLUMN_USAGE
    #   WHERE REFERENCED_TABLE_SCHEMA = (your schema name here)
    #   AND REFERENCED_TABLE_NAME is not null
    #   ORDER BY TABLE_NAME, COLUMN_NAME;

    # this may indicate missing object
    # _mysql_exceptions.OperationalError: (1025, "Error on rename of '.\\fpdb\\hands' to '.\\fpdb\\#sql2-7f0-1b' (errno: 152)")


    # PG notes:

    #  To add a foreign key constraint to a table:
    #  ALTER TABLE tab ADD CONSTRAINT c FOREIGN KEY (col) REFERENCES t2(col2) MATCH FULL;
    #  ALTER TABLE tab DROP CONSTRAINT zipchk
    #
    #  Note: index names must be unique across a schema
    #  CREATE INDEX idx ON tab(col)
    #  DROP INDEX idx

    # SQLite notes:

    # To add an index:
    # create index indexname on tablename (col);


    def __init__(self, c, sql = None): 
        log.info("Creating Database instance, sql = %s" % sql)
        self.config = c
        self.__connected = False
        self.fdb = fpdb_db.fpdb_db()   # sets self.fdb.db self.fdb.cursor and self.fdb.sql
        self.do_connect(c)
        
        if self.backend == self.PGSQL:
            from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT, ISOLATION_LEVEL_READ_COMMITTED, ISOLATION_LEVEL_SERIALIZABLE
            #ISOLATION_LEVEL_AUTOCOMMIT     = 0
            #ISOLATION_LEVEL_READ_COMMITTED = 1 
            #ISOLATION_LEVEL_SERIALIZABLE   = 2


        # where possible avoid creating new SQL instance by using the global one passed in
        if sql is None:
            self.sql = SQL.Sql(db_server = self.db_server)
        else:
            self.sql = sql

        if self.backend == self.SQLITE and self.database == ':memory:' and self.wrongDbVersion:
            log.info("sqlite/:memory: - creating")
            self.recreate_tables()
            self.wrongDbVersion = False

        self.pcache      = None     # PlayerId cache
        self.cachemiss   = 0        # Delete me later - using to count player cache misses
        self.cachehit    = 0        # Delete me later - using to count player cache hits

        # config while trying out new hudcache mechanism
        self.use_date_in_hudcache = True

        #self.hud_hero_style = 'T'  # Duplicate set of vars just for hero - not used yet.
        #self.hud_hero_hands = 2000 # Idea is that you might want all-time stats for others
        #self.hud_hero_days  = 30   # but last T days or last H hands for yourself

        # vars for hand ids or dates fetched according to above config:
        self.hand_1day_ago = 0             # max hand id more than 24 hrs earlier than now
        self.date_ndays_ago = 'd000000'    # date N days ago ('d' + YYMMDD)
        self.h_date_ndays_ago = 'd000000'  # date N days ago ('d' + YYMMDD) for hero
        self.date_nhands_ago = {}          # dates N hands ago per player - not used yet

        self.cursor = self.fdb.cursor

        self.saveActions = False if self.import_options['saveActions'] == False else True

        self.connection.rollback()  # make sure any locks taken so far are released
    #end def __init__

    # could be used by hud to change hud style
    def set_hud_style(self, style):
        self.hud_style = style

    def do_connect(self, c):
        try:
            self.fdb.do_connect(c)
        except:
            # error during connect
            self.__connected = False
            raise
        self.connection = self.fdb.db
        self.session = self.fdb.session
        self.wrongDbVersion = self.fdb.wrongDbVersion

        db_params = c.get_db_parameters()
        self.import_options = c.get_import_parameters()
        self.backend = db_params['db-backend']
        self.db_server = db_params['db-server']
        self.database = db_params['db-databaseName']
        self.host = db_params['db-host']
        self.__connected = True

    def get_session(self, **kwargs):
        """Creates binded alchemy session. Takes Session kwargs
        
        Most important of them:
    
        autocommit
            Defaults to False. When True, the Session does not keep a persistent 
            transaction running, and will acquire connections from the engine on 
            an as-needed basis, returning them immediately after their use. 
            Flushes will begin and commit (or possibly rollback) their own 
            transaction if no transaction is present. When using this mode, the 
            session.begin() method may be used to begin a transaction explicitly.

            Leaving it on its default value of False means that the Session will 
            acquire a connection and begin a transaction the first time it is 
            used, which it will maintain persistently until rollback(), commit(), 
            or close() is called. When the transaction is released by any of 
            these methods, the Session is ready for the next usage, which will 
            again acquire and maintain a new connection/transaction.

        autoflush
            When True, all query operations will issue a flush() call to this 
            Session before proceeding. This is a convenience feature so that 
            flush() need not be called repeatedly in order for database queries 
            to retrieve results. It's typical that autoflush is used in 
            conjunction with autocommit=False. In this scenario, explicit calls 
            to flush() are rarely needed; you usually only need to call commit() 
            (which flushes) to finalize changes.

        expire_on_commit
            Defaults to True. When True, all instances will be fully expired 
            after each commit(), so that all attribute/object access subsequent 
            to a completed transaction will load from the most recent database state.
        """
        return self.fdb.Session(**kwargs)

    def commit(self):
        self.fdb.db.commit()

    def rollback(self):
        self.fdb.db.rollback()

    def connected(self):
        return self.__connected

    def get_cursor(self):
        return self.connection.cursor()

    def close_connection(self):
        self.connection.close()

    def disconnect(self, due_to_error=False):
        """Disconnects the DB (rolls back if param is true, otherwise commits"""
        self.fdb.disconnect(due_to_error)
    
    def reconnect(self, due_to_error=False):
        """Reconnects the DB"""
        self.fdb.reconnect(due_to_error=False)
    
    def get_backend_name(self):
        """Returns the name of the currently used backend"""
        if self.backend==2:
            return "MySQL InnoDB"
        elif self.backend==3:
            return "PostgreSQL"
        elif self.backend==4:
            return "SQLite"
        else:
            raise FpdbError("invalid backend")

    def get_table_name(self, hand_id):
        c = self.connection.cursor()
        c.execute(self.sql.query['get_table_name'], (hand_id, ))
        row = c.fetchone()
        return row
    
    def get_table_info(self, hand_id):
        c = self.connection.cursor()
        c.execute(self.sql.query['get_table_name'], (hand_id, ))
        row = c.fetchone()
        l = list(row)
        if row[3] == "ring":   # cash game
            l.append(None)
            l.append(None)
            return l
        else:    # tournament
            tour_no, tab_no = re.split(" ", row[0])
            l.append(tour_no)
            l.append(tab_no)
            return l

    def get_last_hand(self):
        c = self.connection.cursor()
        c.execute(self.sql.query['get_last_hand'])
        row = c.fetchone()
        return row[0]
    
    def get_xml(self, hand_id):
        c = self.connection.cursor()
        c.execute(self.sql.query['get_xml'], (hand_id))
        row = c.fetchone()
        return row[0]
    
    def get_recent_hands(self, last_hand):
        c = self.connection.cursor()
        c.execute(self.sql.query['get_recent_hands'], {'last_hand': last_hand})
        return c.fetchall()
    
    def get_hand_info(self, new_hand_id):
        c = self.connection.cursor()
        c.execute(self.sql.query['get_hand_info'], new_hand_id)
        return c.fetchall()

    def get_actual_seat(self, hand_id, name):
        c = self.connection.cursor()
        c.execute(self.sql.query['get_actual_seat'], (hand_id, name))
        row = c.fetchone()
        return row[0]

    def get_cards(self, hand):
        """Get and return the cards for each player in the hand."""
        cards = {} # dict of cards, the key is the seat number,
                   # the value is a tuple of the players cards
                   # example: {1: (0, 0, 20, 21, 22, 0 , 0)}
        c = self.connection.cursor()
        c.execute(self.sql.query['get_cards'], [hand])
        for row in c.fetchall():
            cards[row[0]] = row[1:]
        return cards

    def get_common_cards(self, hand):
        """Get and return the community cards for the specified hand."""
        cards = {}
        c = self.connection.cursor()
        c.execute(self.sql.query['get_common_cards'], [hand])
#        row = c.fetchone()
        cards['common'] = c.fetchone()
        return cards

    def convert_cards(self, d):
        ranks = ('', '', '2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A')
        cards = ""
        for i in xrange(1, 8):
#            key = 'card' + str(i) + 'Value'
#            if not d.has_key(key): continue
#            if d[key] == None:
#                break
#            elif d[key] == 0:
#                cards += "xx"
#            else:
#                cards += ranks[d['card' + str(i) + 'Value']] + d['card' +str(i) + 'Suit']
            cv = "card%dvalue" % i
            if cv not in d or d[cv] is None:
                break
            elif d[cv] == 0:
                cards += "xx"
            else:
                cs = "card%dsuit" % i
                cards = "%s%s%s" % (cards, ranks[d[cv]], d[cs])
        return cards

    def get_action_from_hand(self, hand_no):
        action = [ [], [], [], [], [] ]
        c = self.connection.cursor()
        c.execute(self.sql.query['get_action_from_hand'], (hand_no,))
        for row in c.fetchall():
            street = row[0]
            act = row[1:]
            action[street].append(act)
        return action

    def get_winners_from_hand(self, hand):
        """Returns a hash of winners:amount won, given a hand number."""
        winners = {}
        c = self.connection.cursor()
        c.execute(self.sql.query['get_winners_from_hand'], (hand,))
        for row in c.fetchall():
            winners[row[0]] = row[1]
        return winners

    def init_hud_stat_vars(self, hud_days, h_hud_days):
        """Initialise variables used by Hud to fetch stats:
           self.hand_1day_ago     handId of latest hand played more than a day ago
           self.date_ndays_ago    date n days ago
           self.h_date_ndays_ago  date n days ago for hero (different n)
        """

        self.hand_1day_ago = 1
        try:
            c = self.get_cursor()
            c.execute(self.sql.query['get_hand_1day_ago'])
            row = c.fetchone()
        except: # TODO: what error is a database error?!
            err = traceback.extract_tb(sys.exc_info()[2])[-1]
            print "*** Database Error: " + err[2] + "(" + str(err[1]) + "): " + str(sys.exc_info()[1])
        else:
            if row and row[0]:
                self.hand_1day_ago = int(row[0])

        d = timedelta(days=hud_days)
        now = datetime.utcnow() - d
        self.date_ndays_ago = "d%02d%02d%02d" % (now.year - 2000, now.month, now.day)

        d = timedelta(days=h_hud_days)
        now = datetime.utcnow() - d
        self.h_date_ndays_ago = "d%02d%02d%02d" % (now.year - 2000, now.month, now.day)

    def init_player_hud_stat_vars(self, playerid):
        # not sure if this is workable, to be continued ...
        try:
            # self.date_nhands_ago is used for fetching stats for last n hands (hud_style = 'H')
            # This option not used yet - needs to be called for each player :-(
            self.date_nhands_ago[str(playerid)] = 'd000000'

            # should use aggregated version of query if appropriate
            c.execute(self.sql.query['get_date_nhands_ago'], (self.hud_hands, playerid))
            row = c.fetchone()
            if row and row[0]:
                self.date_nhands_ago[str(playerid)] = row[0]
            c.close()
            print "Database: date n hands ago = " + self.date_nhands_ago[str(playerid)] + "(playerid "+str(playerid)+")"
        except:
            err = traceback.extract_tb(sys.exc_info()[2])[-1]
            print "*** Database Error: "+err[2]+"("+str(err[1])+"): "+str(sys.exc_info()[1])

    # is get_stats_from_hand slow?
    def get_stats_from_hand( self, hand, type   # type is "ring" or "tour"
                           , hud_params = {'hud_style':'A', 'agg_bb_mult':1000
                                          ,'seats_style':'A', 'seats_cust_nums':['n/a', 'n/a', (2,2), (3,4), (3,5), (4,6), (5,7), (6,8), (7,9), (8,10), (8,10)]
                                          ,'h_hud_style':'S', 'h_agg_bb_mult':1000
                                          ,'h_seats_style':'A', 'h_seats_cust_nums':['n/a', 'n/a', (2,2), (3,4), (3,5), (4,6), (5,7), (6,8), (7,9), (8,10), (8,10)]
                                          }
                           , hero_id = -1
                           , num_seats = 6
                           ):
        hud_style   = hud_params['hud_style']
        agg_bb_mult = hud_params['agg_bb_mult']
        seats_style = hud_params['seats_style']
        seats_cust_nums = hud_params['seats_cust_nums']
        h_hud_style   = hud_params['h_hud_style']
        h_agg_bb_mult = hud_params['h_agg_bb_mult']
        h_seats_style = hud_params['h_seats_style']
        h_seats_cust_nums = hud_params['h_seats_cust_nums']

        stat_dict = {}

        if seats_style == 'A':
            seats_min, seats_max = 0, 10
        elif seats_style == 'C':
            seats_min, seats_max = seats_cust_nums[num_seats][0], seats_cust_nums[num_seats][1]
        elif seats_style == 'E':
            seats_min, seats_max = num_seats, num_seats
        else:
            seats_min, seats_max = 0, 10
            print "bad seats_style value:", seats_style

        if h_seats_style == 'A':
            h_seats_min, h_seats_max = 0, 10
        elif h_seats_style == 'C':
            h_seats_min, h_seats_max = h_seats_cust_nums[num_seats][0], h_seats_cust_nums[num_seats][1]
        elif h_seats_style == 'E':
            h_seats_min, h_seats_max = num_seats, num_seats
        else:
            h_seats_min, h_seats_max = 0, 10
            print "bad h_seats_style value:", h_seats_style
        log.info("opp seats style %s %d %d hero seats style %s %d %d"
                 % (seats_style, seats_min, seats_max
                   ,h_seats_style, h_seats_min, h_seats_max) )

        if hud_style == 'S' or h_hud_style == 'S':
            self.get_stats_from_hand_session(hand, stat_dict, hero_id
                                            ,hud_style, seats_min, seats_max
                                            ,h_hud_style, h_seats_min, h_seats_max)

            if hud_style == 'S' and h_hud_style == 'S':
                return stat_dict

        if hud_style == 'T':
            stylekey = self.date_ndays_ago
        elif hud_style == 'A':
            stylekey = '0000000'  # all stylekey values should be higher than this
        elif hud_style == 'S':
            stylekey = 'zzzzzzz'  # all stylekey values should be lower than this
        else:
            stylekey = '0000000'
            log.info('hud_style: %s' % hud_style)

        #elif hud_style == 'H':
        #    stylekey = date_nhands_ago  needs array by player here ...

        if h_hud_style == 'T':
            h_stylekey = self.h_date_ndays_ago
        elif h_hud_style == 'A':
            h_stylekey = '0000000'  # all stylekey values should be higher than this
        elif h_hud_style == 'S':
            h_stylekey = 'zzzzzzz'  # all stylekey values should be lower than this
        else:
            h_stylekey = '000000'
            log.info('h_hud_style: %s' % h_hud_style)

        #elif h_hud_style == 'H':
        #    h_stylekey = date_nhands_ago  needs array by player here ...

        query = 'get_stats_from_hand_aggregated'
        subs = (hand
               ,hero_id, stylekey, agg_bb_mult, agg_bb_mult, seats_min, seats_max  # hero params
               ,hero_id, h_stylekey, h_agg_bb_mult, h_agg_bb_mult, h_seats_min, h_seats_max)    # villain params

        #print "get stats: hud style =", hud_style, "query =", query, "subs =", subs
        c = self.connection.cursor()

#       now get the stats
        c.execute(self.sql.query[query], subs)
        colnames = [desc[0] for desc in c.description]
        for row in c.fetchall():
            playerid = row[0]
            if (playerid == hero_id and h_hud_style != 'S') or (playerid != hero_id and hud_style != 'S'):
                t_dict = {}
                for name, val in zip(colnames, row):
                    t_dict[name.lower()] = val
#                    print t_dict
                stat_dict[t_dict['player_id']] = t_dict

        return stat_dict

    # uses query on handsplayers instead of hudcache to get stats on just this session
    def get_stats_from_hand_session(self, hand, stat_dict, hero_id
                                   ,hud_style, seats_min, seats_max
                                   ,h_hud_style, h_seats_min, h_seats_max):
        """Get stats for just this session (currently defined as any play in the last 24 hours - to
           be improved at some point ...)
           h_hud_style and hud_style params indicate whether to get stats for hero and/or others
           - only fetch heros stats if h_hud_style == 'S',
             and only fetch others stats if hud_style == 'S'
           seats_min/max params give seats limits, only include stats if between these values
        """

        query = self.sql.query['get_stats_from_hand_session']
        if self.db_server == 'mysql':
            query = query.replace("<signed>", 'signed ')
        else:
            query = query.replace("<signed>", '')
        
        subs = (self.hand_1day_ago, hand, hero_id, seats_min, seats_max
                                        , hero_id, h_seats_min, h_seats_max)
        c = self.get_cursor()

        # now get the stats
        #print "sess_stats: subs =", subs, "subs[0] =", subs[0]
        c.execute(query, subs)
        colnames = [desc[0] for desc in c.description]
        n = 0

        row = c.fetchone()
        if colnames[0].lower() == 'player_id':

            # Loop through stats adding them to appropriate stat_dict:
            while row:
                playerid = row[0]
                seats = row[1]
                if (playerid == hero_id and h_hud_style == 'S') or (playerid != hero_id and hud_style == 'S'):
                    for name, val in zip(colnames, row):
                        if not playerid in stat_dict:
                            stat_dict[playerid] = {}
                            stat_dict[playerid][name.lower()] = val
                        elif not name.lower() in stat_dict[playerid]:
                            stat_dict[playerid][name.lower()] = val
                        elif name.lower() not in ('hand_id', 'player_id', 'seat', 'screen_name', 'seats'):
                            #print "DEBUG: stat_dict[%s][%s]: %s" %(playerid, name.lower(), val)
                            stat_dict[playerid][name.lower()] += val
                    n += 1
                    if n >= 10000: break  # todo: don't think this is needed so set nice and high 
                                          # prevents infinite loop so leave for now - comment out or remove?
                row = c.fetchone()
        else:
            log.error("ERROR: query %s result does not have player_id as first column" % (query,))

        #print "   %d rows fetched, len(stat_dict) = %d" % (n, len(stat_dict))

        #print "session stat_dict =", stat_dict
        #return stat_dict
            
    def get_player_id(self, config, site, player_name):
        c = self.connection.cursor()
        c.execute(self.sql.query['get_player_id'], (player_name, site))
        row = c.fetchone()
        if row:
            return row[0]
        else:
            return None
            
    def get_player_names(self, config, site_id=None, like_player_name="%"):
        """Fetch player names from players. Use site_id and like_player_name if provided"""

        if site_id is None:
            site_id = -1
        c = self.get_cursor()
        c.execute(self.sql.query['get_player_names'], (like_player_name, site_id, site_id))
        rows = c.fetchall()
        return rows
            
    #returns the SQL ids of the names given in an array
    # TODO: if someone gets industrious, they should make the parts that use the output of this function deal with a dict
    # { playername: id } instead of depending on it's relation to the positions list
    # then this can be reduced in complexity a bit

    #def recognisePlayerIDs(cursor, names, site_id):
    #    result = []
    #    for i in xrange(len(names)):
    #        cursor.execute ("SELECT id FROM Players WHERE name=%s", (names[i],))
    #        tmp=cursor.fetchall()
    #        if (len(tmp)==0): #new player
    #            cursor.execute ("INSERT INTO Players (name, siteId) VALUES (%s, %s)", (names[i], site_id))
    #            #print "Number of players rows inserted: %d" % cursor.rowcount
    #            cursor.execute ("SELECT id FROM Players WHERE name=%s", (names[i],))
    #            tmp=cursor.fetchall()
    #        #print "recognisePlayerIDs, names[i]:",names[i],"tmp:",tmp
    #        result.append(tmp[0][0])
    #    return result

    def recognisePlayerIDs(self, names, site_id):
        c = self.get_cursor()
        q = "SELECT name,id FROM Players WHERE siteid=%d and (name=%s)" %(site_id, " OR name=".join([self.sql.query['placeholder'] for n in names]))
        c.execute(q, names) # get all playerids by the names passed in
        ids = dict(c.fetchall()) # convert to dict
        if len(ids) != len(names):
            notfound = [n for n in names if n not in ids] # make list of names not in database
            if notfound: # insert them into database
                q_ins = "INSERT INTO Players (name, siteId) VALUES (%s, "+str(site_id)+")"
                q_ins = q_ins.replace('%s', self.sql.query['placeholder'])
                c.executemany(q_ins, [(n,) for n in notfound])
                q2 = "SELECT name,id FROM Players WHERE siteid=%d and (name=%s)" % (site_id, " OR name=".join(["%s" for n in notfound]))
                q2 = q2.replace('%s', self.sql.query['placeholder'])
                c.execute(q2, notfound) # get their new ids
                tmp = c.fetchall()
                for n,id in tmp: # put them all into the same dict
                    ids[n] = id
        # return them in the SAME ORDER that they came in in the names argument, rather than the order they came out of the DB
        return [ids[n] for n in names]
    #end def recognisePlayerIDs

    # Here's a version that would work if it wasn't for the fact that it needs to have the output in the same order as input
    # this version could also be improved upon using list comprehensions, etc

    #def recognisePlayerIDs(cursor, names, site_id):
    #    result = []
    #    notfound = []
    #    cursor.execute("SELECT name,id FROM Players WHERE name='%s'" % "' OR name='".join(names))
    #    tmp = dict(cursor.fetchall())
    #    for n in names:
    #        if n not in tmp:
    #            notfound.append(n)
    #        else:
    #            result.append(tmp[n])
    #    if notfound:
    #        cursor.executemany("INSERT INTO Players (name, siteId) VALUES (%s, "+str(site_id)+")", (notfound))
    #        cursor.execute("SELECT id FROM Players WHERE name='%s'" % "' OR name='".join(notfound))
    #        tmp = cursor.fetchall()
    #        for n in tmp:
    #            result.append(n[0])
    #        
    #    return result


    def get_site_id(self, site):
        c = self.get_cursor()
        c.execute(self.sql.query['getSiteId'], (site,))
        result = c.fetchall()
        return result

    def get_last_insert_id(self, cursor=None):
        ret = None
        try:
            if self.backend == self.MYSQL_INNODB:
                ret = self.connection.insert_id()
                if ret < 1 or ret > 999999999:
                    log.warning("getLastInsertId(): problem fetching insert_id? ret=%d" % ret)
                    ret = -1
            elif self.backend == self.PGSQL:
                # some options:
                # currval(hands_id_seq) - use name of implicit seq here
                # lastval() - still needs sequences set up?
                # insert ... returning  is useful syntax (but postgres specific?)
                # see rules (fancy trigger type things)
                c = self.get_cursor()
                ret = c.execute ("SELECT lastval()")
                row = c.fetchone()
                if not row:
                    log.warning("getLastInsertId(%s): problem fetching lastval? row=%d" % (seq, row))
                    ret = -1
                else:
                    ret = row[0]
            elif self.backend == self.SQLITE:
                ret = cursor.lastrowid
            else:
                log.error("getLastInsertId(): unknown backend: %d" % self.backend)
                ret = -1
        except:
            ret = -1
            err = traceback.extract_tb(sys.exc_info()[2])
            print "*** Database get_last_insert_id error: " + str(sys.exc_info()[1])
            print "\n".join( [e[0]+':'+str(e[1])+" "+e[2] for e in err] )
            raise
        return ret


    def prepareBulkImport(self):
        """Drop some indexes/foreign keys to prepare for bulk import. 
           Currently keeping the standalone indexes as needed to import quickly"""
        stime = time()
        c = self.get_cursor()
        # sc: don't think autocommit=0 is needed, should already be in that mode
        if self.backend == self.MYSQL_INNODB:
            c.execute("SET foreign_key_checks=0")
            c.execute("SET autocommit=0")
            return
        if self.backend == self.PGSQL:
            self.connection.set_isolation_level(0)   # allow table/index operations to work
        for fk in self.foreignKeys[self.backend]:
            if fk['drop'] == 1:
                if self.backend == self.MYSQL_INNODB:
                    c.execute("SELECT constraint_name " +
                              "FROM information_schema.KEY_COLUMN_USAGE " +
                              #"WHERE REFERENCED_TABLE_SCHEMA = 'fpdb'
                              "WHERE 1=1 " +
                              "AND table_name = %s AND column_name = %s " + 
                              "AND referenced_table_name = %s " +
                              "AND referenced_column_name = %s ",
                              (fk['fktab'], fk['fkcol'], fk['rtab'], fk['rcol']) )
                    cons = c.fetchone()
                    #print "preparebulk find fk: cons=", cons
                    if cons:
                        print "dropping mysql fk", cons[0], fk['fktab'], fk['fkcol']
                        try:
                            c.execute("alter table " + fk['fktab'] + " drop foreign key " + cons[0])
                        except:
                            print "    drop failed: " + str(sys.exc_info())
                elif self.backend == self.PGSQL:
    #    DON'T FORGET TO RECREATE THEM!!
                    print "dropping pg fk", fk['fktab'], fk['fkcol']
                    try:
                        # try to lock table to see if index drop will work:
                        # hmmm, tested by commenting out rollback in grapher. lock seems to work but 
                        # then drop still hangs :-(  does work in some tests though??
                        # will leave code here for now pending further tests/enhancement ...
                        c.execute( "lock table %s in exclusive mode nowait" % (fk['fktab'],) )
                        #print "after lock, status:", c.statusmessage
                        #print "alter table %s drop constraint %s_%s_fkey" % (fk['fktab'], fk['fktab'], fk['fkcol'])
                        try:
                            c.execute("alter table %s drop constraint %s_%s_fkey" % (fk['fktab'], fk['fktab'], fk['fkcol']))
                            print "dropped pg fk pg fk %s_%s_fkey, continuing ..." % (fk['fktab'], fk['fkcol'])
                        except:
                            if "does not exist" not in str(sys.exc_value):
                                print "warning: drop pg fk %s_%s_fkey failed: %s, continuing ..." \
                                      % (fk['fktab'], fk['fkcol'], str(sys.exc_value).rstrip('\n') )
                    except:
                        print "warning: constraint %s_%s_fkey not dropped: %s, continuing ..." \
                              % (fk['fktab'],fk['fkcol'], str(sys.exc_value).rstrip('\n'))
                else:
                    print "Only MySQL and Postgres supported so far"
                    return -1
        
        for idx in self.indexes[self.backend]:
            if idx['drop'] == 1:
                if self.backend == self.MYSQL_INNODB:
                    print "dropping mysql index ", idx['tab'], idx['col']
                    try:
                        # apparently nowait is not implemented in mysql so this just hangs if there are locks 
                        # preventing the index drop :-(
                        c.execute( "alter table %s drop index %s;", (idx['tab'],idx['col']) )
                    except:
                        print "    drop index failed: " + str(sys.exc_info())
                            # ALTER TABLE `fpdb`.`handsplayers` DROP INDEX `playerId`;
                            # using: 'HandsPlayers' drop index 'playerId'
                elif self.backend == self.PGSQL:
    #    DON'T FORGET TO RECREATE THEM!!
                    print "dropping pg index ", idx['tab'], idx['col']
                    try:
                        # try to lock table to see if index drop will work:
                        c.execute( "lock table %s in exclusive mode nowait" % (idx['tab'],) )
                        #print "after lock, status:", c.statusmessage
                        try:
                            # table locked ok so index drop should work:
                            #print "drop index %s_%s_idx" % (idx['tab'],idx['col']) 
                            c.execute( "drop index if exists %s_%s_idx" % (idx['tab'],idx['col']) )
                            #print "dropped  pg index ", idx['tab'], idx['col']
                        except:
                            if "does not exist" not in str(sys.exc_value):
                                print "warning: drop index %s_%s_idx failed: %s, continuing ..." \
                                      % (idx['tab'],idx['col'], str(sys.exc_value).rstrip('\n')) 
                    except:
                        print "warning: index %s_%s_idx not dropped %s, continuing ..." \
                              % (idx['tab'],idx['col'], str(sys.exc_value).rstrip('\n'))
                else:
                    print "Error: Only MySQL and Postgres supported so far"
                    return -1

        if self.backend == self.PGSQL:
            self.connection.set_isolation_level(1)   # go back to normal isolation level
        self.commit() # seems to clear up errors if there were any in postgres
        ptime = time() - stime
        print "prepare import took", ptime, "seconds"
    #end def prepareBulkImport

    def afterBulkImport(self):
        """Re-create any dropped indexes/foreign keys after bulk import"""
        stime = time()
        
        c = self.get_cursor()
        if self.backend == self.MYSQL_INNODB:
            c.execute("SET foreign_key_checks=1")
            c.execute("SET autocommit=1")
            return

        if self.backend == self.PGSQL:
            self.connection.set_isolation_level(0)   # allow table/index operations to work
        for fk in self.foreignKeys[self.backend]:
            if fk['drop'] == 1:
                if self.backend == self.MYSQL_INNODB:
                    c.execute("SELECT constraint_name " +
                              "FROM information_schema.KEY_COLUMN_USAGE " +
                              #"WHERE REFERENCED_TABLE_SCHEMA = 'fpdb'
                              "WHERE 1=1 " +
                              "AND table_name = %s AND column_name = %s " + 
                              "AND referenced_table_name = %s " +
                              "AND referenced_column_name = %s ",
                              (fk['fktab'], fk['fkcol'], fk['rtab'], fk['rcol']) )
                    cons = c.fetchone()
                    #print "afterbulk: cons=", cons
                    if cons:
                        pass
                    else:
                        print "creating fk ", fk['fktab'], fk['fkcol'], "->", fk['rtab'], fk['rcol']
                        try:
                            c.execute("alter table " + fk['fktab'] + " add foreign key (" 
                                      + fk['fkcol'] + ") references " + fk['rtab'] + "(" 
                                      + fk['rcol'] + ")")
                        except:
                            print "    create fk failed: " + str(sys.exc_info())
                elif self.backend == self.PGSQL:
                    print "creating fk ", fk['fktab'], fk['fkcol'], "->", fk['rtab'], fk['rcol']
                    try:
                        c.execute("alter table " + fk['fktab'] + " add constraint "
                                  + fk['fktab'] + '_' + fk['fkcol'] + '_fkey'
                                  + " foreign key (" + fk['fkcol']
                                  + ") references " + fk['rtab'] + "(" + fk['rcol'] + ")")
                    except:
                        print "   create fk failed: " + str(sys.exc_info())
                else:
                    print "Only MySQL and Postgres supported so far"
                    return -1
        
        for idx in self.indexes[self.backend]:
            if idx['drop'] == 1:
                if self.backend == self.MYSQL_INNODB:
                    print "creating mysql index ", idx['tab'], idx['col']
                    try:
                        s = "alter table %s add index %s(%s)" % (idx['tab'],idx['col'],idx['col'])
                        c.execute(s)
                    except:
                        print "    create fk failed: " + str(sys.exc_info())
                elif self.backend == self.PGSQL:
    #                pass
                    # mod to use tab_col for index name?
                    print "creating pg index ", idx['tab'], idx['col']
                    try:
                        s = "create index %s_%s_idx on %s(%s)" % (idx['tab'], idx['col'], idx['tab'], idx['col'])
                        c.execute(s)
                    except:
                        print "   create index failed: " + str(sys.exc_info())
                else:
                    print "Only MySQL and Postgres supported so far"
                    return -1

        if self.backend == self.PGSQL:
            self.connection.set_isolation_level(1)   # go back to normal isolation level
        self.commit()   # seems to clear up errors if there were any in postgres
        atime = time() - stime
        print "After import took", atime, "seconds"
    #end def afterBulkImport

    def drop_referential_integrity(self):
        """Update all tables to remove foreign keys"""

        c = self.get_cursor()
        c.execute(self.sql.query['list_tables'])
        result = c.fetchall()

        for i in range(len(result)):
            c.execute("SHOW CREATE TABLE " + result[i][0])
            inner = c.fetchall()

            for j in range(len(inner)):
            # result[i][0] - Table name
            # result[i][1] - CREATE TABLE parameters
            #Searching for CONSTRAINT `tablename_ibfk_1`
                for m in re.finditer('(ibfk_[0-9]+)', inner[j][1]):
                    key = "`" + inner[j][0] + "_" + m.group() + "`"
                    c.execute("ALTER TABLE " + inner[j][0] + " DROP FOREIGN KEY " + key)
                self.commit()
        #end drop_referential_inegrity
    
    def recreate_tables(self):
        """(Re-)creates the tables of the current DB"""

        if self.fdb.version == 118:
            self.fdb.engine.execute("DROP TABLE HandsActions")
        
        self.drop_tables()
        self.create_tables_and_indexes()
        self.commit()
        log.info("Finished recreating tables")
    #end def recreate_tables

    def create_tables_and_indexes(self):
        from AlchemyTables import metadata
        try:
            metadata.create_all(self.fdb.engine)
            self.fillDefaultData()
            self.commit()
        except:
            err = traceback.extract_tb(sys.exc_info()[2])[-1]
            print "***Error creating tables: "+err[2]+"("+str(err[1])+"): "+str(sys.exc_info()[1])
            self.rollback()
            raise
#end def disconnect
    
    def drop_tables(self):
        """Drops the fpdb tables from the current db"""
        from AlchemyTables import metadata
        try:
            metadata.drop_all(self.fdb.engine)
        except:
            print "*** Error in committing table drop"
            err = traceback.extract_tb(sys.exc_info()[2])[-1]
            print "***Error dropping tables: "+err[2]+"("+str(err[1])+"): "+str(sys.exc_info()[1])
            self.rollback()
    #end def drop_tables

    def createAllIndexes(self):
        """Create new indexes"""

        try:
            if self.backend == self.PGSQL:
                self.connection.set_isolation_level(0)   # allow table/index operations to work
            for idx in self.indexes[self.backend]:
                if self.backend == self.MYSQL_INNODB:
                    print "creating mysql index ", idx['tab'], idx['col']
                    try:
                        s = "create index %s on %s(%s)" % (idx['col'],idx['tab'],idx['col'])
                        self.get_cursor().execute(s)
                    except:
                        print "    create idx failed: " + str(sys.exc_info())
                elif self.backend == self.PGSQL:
                    # mod to use tab_col for index name?
                    print "creating pg index ", idx['tab'], idx['col']
                    try:
                        s = "create index %s_%s_idx on %s(%s)" % (idx['tab'], idx['col'], idx['tab'], idx['col'])
                        self.get_cursor().execute(s)
                    except:
                        print "    create idx failed: " + str(sys.exc_info())
                elif self.backend == self.SQLITE:
                    log.debug("Creating sqlite index %s %s" % (idx['tab'], idx['col']))
                    try:
                        s = "create index %s_%s_idx on %s(%s)" % (idx['tab'], idx['col'], idx['tab'], idx['col'])
                        self.get_cursor().execute(s)
                    except:
                        log.debug("Create idx failed: " + str(sys.exc_info()))
                else:
                    print "Only MySQL, Postgres and SQLite supported so far"
                    return -1
            if self.backend == self.PGSQL:
                self.connection.set_isolation_level(1)   # go back to normal isolation level
        except:
            print "Error creating indexes: " + str(sys.exc_value)
            raise FpdbError( "Error creating indexes " + str(sys.exc_value) )
    #end def createAllIndexes

    def dropAllIndexes(self):
        """Drop all standalone indexes (i.e. not including primary keys or foreign keys)
           using list of indexes in indexes data structure"""
        # maybe upgrade to use data dictionary?? (but take care to exclude PK and FK)
        if self.backend == self.PGSQL:
            self.connection.set_isolation_level(0)   # allow table/index operations to work
        for idx in self.indexes[self.backend]:
            if self.backend == self.MYSQL_INNODB:
                print "dropping mysql index ", idx['tab'], idx['col']
                try:
                    self.get_cursor().execute( "alter table %s drop index %s"
                                             , (idx['tab'], idx['col']) )
                except:
                    print "    drop idx failed: " + str(sys.exc_info())
            elif self.backend == self.PGSQL:
                print "dropping pg index ", idx['tab'], idx['col']
                # mod to use tab_col for index name?
                try:
                    self.get_cursor().execute( "drop index %s_%s_idx"
                                               % (idx['tab'],idx['col']) )
                except:
                    print "    drop idx failed: " + str(sys.exc_info())
            else:
                print "Only MySQL and Postgres supported so far"
                return -1
        if self.backend == self.PGSQL:
            self.connection.set_isolation_level(1)   # go back to normal isolation level
    #end def dropAllIndexes

    def createAllForeignKeys(self):
        """Create foreign keys"""

        try:
            if self.backend == self.PGSQL:
                self.connection.set_isolation_level(0)   # allow table/index operations to work
            c = self.get_cursor()
        except:
            print "    set_isolation_level failed: " + str(sys.exc_info())

        for fk in self.foreignKeys[self.backend]:
            if self.backend == self.MYSQL_INNODB:
                c.execute("SELECT constraint_name " +
                          "FROM information_schema.KEY_COLUMN_USAGE " +
                          #"WHERE REFERENCED_TABLE_SCHEMA = 'fpdb'
                          "WHERE 1=1 " +
                          "AND table_name = %s AND column_name = %s " + 
                          "AND referenced_table_name = %s " +
                          "AND referenced_column_name = %s ",
                          (fk['fktab'], fk['fkcol'], fk['rtab'], fk['rcol']) )
                cons = c.fetchone()
                #print "afterbulk: cons=", cons
                if cons:
                    pass
                else:
                    print "creating fk ", fk['fktab'], fk['fkcol'], "->", fk['rtab'], fk['rcol']
                    try:
                        c.execute("alter table " + fk['fktab'] + " add foreign key (" 
                                  + fk['fkcol'] + ") references " + fk['rtab'] + "(" 
                                  + fk['rcol'] + ")")
                    except:
                        print "    create fk failed: " + str(sys.exc_info())
            elif self.backend == self.PGSQL:
                print "creating fk ", fk['fktab'], fk['fkcol'], "->", fk['rtab'], fk['rcol']
                try:
                    c.execute("alter table " + fk['fktab'] + " add constraint "
                              + fk['fktab'] + '_' + fk['fkcol'] + '_fkey'
                              + " foreign key (" + fk['fkcol']
                              + ") references " + fk['rtab'] + "(" + fk['rcol'] + ")")
                except:
                    print "   create fk failed: " + str(sys.exc_info())
            else:
                print "Only MySQL and Postgres supported so far"

        try:
            if self.backend == self.PGSQL:
                self.connection.set_isolation_level(1)   # go back to normal isolation level
        except:
            print "    set_isolation_level failed: " + str(sys.exc_info())
    #end def createAllForeignKeys

    def dropAllForeignKeys(self):
        """Drop all standalone indexes (i.e. not including primary keys or foreign keys)
           using list of indexes in indexes data structure"""
        # maybe upgrade to use data dictionary?? (but take care to exclude PK and FK)
        if self.backend == self.PGSQL:
            self.connection.set_isolation_level(0)   # allow table/index operations to work
        c = self.get_cursor()

        for fk in self.foreignKeys[self.backend]:
            if self.backend == self.MYSQL_INNODB:
                c.execute("SELECT constraint_name " +
                          "FROM information_schema.KEY_COLUMN_USAGE " +
                          #"WHERE REFERENCED_TABLE_SCHEMA = 'fpdb'
                          "WHERE 1=1 " +
                          "AND table_name = %s AND column_name = %s " + 
                          "AND referenced_table_name = %s " +
                          "AND referenced_column_name = %s ",
                          (fk['fktab'], fk['fkcol'], fk['rtab'], fk['rcol']) )
                cons = c.fetchone()
                #print "preparebulk find fk: cons=", cons
                if cons:
                    print "dropping mysql fk", cons[0], fk['fktab'], fk['fkcol']
                    try:
                        c.execute("alter table " + fk['fktab'] + " drop foreign key " + cons[0])
                    except:
                        print "    drop failed: " + str(sys.exc_info())
            elif self.backend == self.PGSQL:
#    DON'T FORGET TO RECREATE THEM!!
                print "dropping pg fk", fk['fktab'], fk['fkcol']
                try:
                    # try to lock table to see if index drop will work:
                    # hmmm, tested by commenting out rollback in grapher. lock seems to work but 
                    # then drop still hangs :-(  does work in some tests though??
                    # will leave code here for now pending further tests/enhancement ...
                    c.execute( "lock table %s in exclusive mode nowait" % (fk['fktab'],) )
                    #print "after lock, status:", c.statusmessage
                    #print "alter table %s drop constraint %s_%s_fkey" % (fk['fktab'], fk['fktab'], fk['fkcol'])
                    try:
                        c.execute("alter table %s drop constraint %s_%s_fkey" % (fk['fktab'], fk['fktab'], fk['fkcol']))
                        print "dropped pg fk pg fk %s_%s_fkey, continuing ..." % (fk['fktab'], fk['fkcol'])
                    except:
                        if "does not exist" not in str(sys.exc_value):
                            print "warning: drop pg fk %s_%s_fkey failed: %s, continuing ..." \
                                  % (fk['fktab'], fk['fkcol'], str(sys.exc_value).rstrip('\n') )
                except:
                    print "warning: constraint %s_%s_fkey not dropped: %s, continuing ..." \
                          % (fk['fktab'],fk['fkcol'], str(sys.exc_value).rstrip('\n'))
            else:
                print "Only MySQL and Postgres supported so far"
        
        if self.backend == self.PGSQL:
            self.connection.set_isolation_level(1)   # go back to normal isolation level
    #end def dropAllForeignKeys

    
    def fillDefaultData(self):
        from AlchemyMappings import Site, Version
        conn = self.fdb.engine 

        Version(conn).set_initial()
        Site.insert_initial(conn)


        #c = self.get_cursor() 
        #if self.backend == self.SQLITE:
        #    c.execute("INSERT INTO TourneyTypes (id, siteId, buyin, fee) VALUES (NULL, 1, 0, 0);")
        #elif self.backend == self.PGSQL:
        #    c.execute("""insert into TourneyTypes(siteId, buyin, fee, maxSeats, knockout
        #                                         ,rebuyOrAddon, speed, headsUp, shootout, matrix)
        #                 values (1, 0, 0, 0, False, False, null, False, False, False);""")
        #elif self.backend == self.MYSQL_INNODB:
        #    c.execute("""insert into TourneyTypes(id, siteId, buyin, fee, maxSeats, knockout
        #                                         ,rebuyOrAddon, speed, headsUp, shootout, matrix)
        #                 values (DEFAULT, 1, 0, 0, 0, False, False, null, False, False, False);""")


    def rebuild_indexes(self, start=None):
        self.dropAllIndexes()
        self.createAllIndexes()
        self.dropAllForeignKeys()
        self.createAllForeignKeys()

    def rebuild_hudcache(self, h_start=None, v_start=None):
        """clears hudcache and rebuilds from the individual handsplayers records"""

        try:
            stime = time()
            # derive list of program owner's player ids
            self.hero = {}                               # name of program owner indexed by site id
            self.hero_ids = {'dummy':-53, 'dummy2':-52}  # playerid of owner indexed by site id
                                                         # make sure at least two values in list
                                                         # so that tuple generation creates doesn't use
                                                         # () or (1,) style
            for site in self.config.get_supported_sites():
                result = self.get_site_id(site)
                if result:
                    site_id = result[0][0]
                    self.hero[site_id] = self.config.supported_sites[site].screen_name
                    p_id = self.get_player_id(self.config, site, self.hero[site_id])
                    if p_id:
                        self.hero_ids[site_id] = int(p_id)
            
            if h_start is None:
                h_start = self.hero_hudstart_def
            if v_start is None:
                v_start = self.villain_hudstart_def
            if self.hero_ids == {}:
                where = ""
            else:
                where =   "where (    hp.playerId not in " + str(tuple(self.hero_ids.values())) \
                        + "       and h.handStart > '" + v_start + "')" \
                        + "   or (    hp.playerId in " + str(tuple(self.hero_ids.values())) \
                        + "       and h.handStart > '" + h_start + "')"
            rebuild_sql = self.sql.query['rebuildHudCache'].replace('<where_clause>', where)

            self.get_cursor().execute(self.sql.query['clearHudCache'])
            self.get_cursor().execute(rebuild_sql)
            self.commit()
            print "Rebuild hudcache took %.1f seconds" % (time() - stime,)
        except:
            err = traceback.extract_tb(sys.exc_info()[2])[-1]
            print "Error rebuilding hudcache:", str(sys.exc_value)
            print err
    #end def rebuild_hudcache

    def get_hero_hudcache_start(self):
        """fetches earliest stylekey from hudcache for one of hero's player ids"""

        try:
            # derive list of program owner's player ids
            self.hero = {}                               # name of program owner indexed by site id
            self.hero_ids = {'dummy':-53, 'dummy2':-52}  # playerid of owner indexed by site id
                                                         # make sure at least two values in list
                                                         # so that tuple generation creates doesn't use
                                                         # () or (1,) style
            for site in self.config.get_supported_sites():
                result = self.get_site_id(site)
                if result:
                    site_id = result[0][0]
                    self.hero[site_id] = self.config.supported_sites[site].screen_name
                    p_id = self.get_player_id(self.config, site, self.hero[site_id])
                    if p_id:
                        self.hero_ids[site_id] = int(p_id)
            
            q = self.sql.query['get_hero_hudcache_start'].replace("<playerid_list>", str(tuple(self.hero_ids.values())))
            c = self.get_cursor()
            c.execute(q)
            tmp = c.fetchone()
            if tmp == (None,):
                return self.hero_hudstart_def
            else:
                return "20"+tmp[0][1:3] + "-" + tmp[0][3:5] + "-" + tmp[0][5:7]
        except:
            err = traceback.extract_tb(sys.exc_info()[2])[-1]
            print "Error rebuilding hudcache:", str(sys.exc_value)
            print err
    #end def get_hero_hudcache_start


    def analyzeDB(self):
        """Do whatever the DB can offer to update index/table statistics"""
        stime = time()
        if self.backend == self.MYSQL_INNODB:
            try:
                self.get_cursor().execute(self.sql.query['analyze'])
            except:
                print "Error during analyze:", str(sys.exc_value)
        elif self.backend == self.PGSQL:
            self.connection.set_isolation_level(0)   # allow analyze to work
            try:
                self.get_cursor().execute(self.sql.query['analyze'])
            except:
                print "Error during analyze:", str(sys.exc_value)
            self.connection.set_isolation_level(1)   # go back to normal isolation level
        self.commit()
        atime = time() - stime
        print "Analyze took %.1f seconds" % (atime,)
    #end def analyzeDB

    def vacuumDB(self):
        """Do whatever the DB can offer to update index/table statistics"""
        stime = time()
        if self.backend == self.MYSQL_INNODB:
            try:
                self.get_cursor().execute(self.sql.query['vacuum'])
            except:
                print "Error during vacuum:", str(sys.exc_value)
        elif self.backend == self.PGSQL:
            self.connection.set_isolation_level(0)   # allow vacuum to work
            try:
                self.get_cursor().execute(self.sql.query['vacuum'])
            except:
                print "Error during vacuum:", str(sys.exc_value)
            self.connection.set_isolation_level(1)   # go back to normal isolation level
        self.commit()
        atime = time() - stime
        print "Vacuum took %.1f seconds" % (atime,)
    #end def analyzeDB

# Start of Hand Writing routines. Idea is to provide a mixture of routines to store Hand data
# however the calling prog requires. Main aims:
# - existing static routines from fpdb_simple just modified

    def lock_for_insert(self):
        """Lock tables in MySQL to try to speed inserts up"""
        try:
            self.get_cursor().execute(self.sql.query['lockForInsert'])
        except:
            print "Error during fdb.lock_for_insert:", str(sys.exc_value)
    #end def lock_for_insert

###########################
# NEWIMPORT CODE
###########################

    def storeHudCache(self, hand):
        """Update cached statistics. If update fails because no record exists, do an insert."""

        starttime = hand.handStart
        if self.use_date_in_hudcache:
            styleKey = datetime.strftime(starttime, 'd%y%m%d')
            #styleKey = "d%02d%02d%02d" % (hand_start_time.year-2000, hand_start_time.month, hand_start_time.day)
        else:
            # hard-code styleKey as 'A000000' (all-time cache, no key) for now
            styleKey = 'A000000'

        update_hudcache = self.sql.query['update_hudcache']
        update_hudcache = update_hudcache.replace('%s', self.sql.query['placeholder'])
        insert_hudcache = self.sql.query['insert_hudcache']
        insert_hudcache = insert_hudcache.replace('%s', self.sql.query['placeholder'])
            
        #print "DEBUG: %s %s %s" %(hid, pids, pdata)
        inserts = []
        for hp in hand.handplayers_by_name.itervalues():
            line = [0]*62
            
            line[0] = 1 # HDs
            if hp.street0VPI:                  line[1] = 1
            if hp.street0Aggr:                 line[2] = 1
            if hp.street0_3BChance:            line[3] = 1
            if hp.street0_3BDone:              line[4] = 1
            if hp.street1Seen:                 line[5] = 1
            if hp.street2Seen:                 line[6] = 1
            if hp.street3Seen:                 line[7] = 1
            if hp.street4Seen:                 line[8] = 1
            if hp.sawShowdown:                 line[9] = 1
            if hp.street1Aggr:                 line[10] = 1
            if hp.street2Aggr:                 line[11] = 1
            if hp.street3Aggr:                 line[12] = 1
            if hp.street4Aggr:                 line[13] = 1
            if hp.otherRaisedStreet1:          line[14] = 1
            if hp.otherRaisedStreet2:          line[15] = 1
            if hp.otherRaisedStreet3:          line[16] = 1
            if hp.otherRaisedStreet4:          line[17] = 1
            if hp.foldToOtherRaisedStreet1:    line[18] = 1
            if hp.foldToOtherRaisedStreet2:    line[19] = 1
            if hp.foldToOtherRaisedStreet3:    line[20] = 1
            if hp.foldToOtherRaisedStreet4:    line[21] = 1
            line[22] = hp.wonWhenSeenStreet1
            line[23] = hp.wonAtSD
            if hp.stealAttemptChance:          line[24] = 1
            if hp.stealAttempted:              line[25] = 1
            if hp.foldBbToStealChance:         line[26] = 1
            if hp.foldedBbToSteal:             line[27] = 1
            if hp.foldSbToStealChance:         line[28] = 1
            if hp.foldedSbToSteal:             line[29] = 1
            if hp.street1CBChance:             line[30] = 1
            if hp.street1CBDone:               line[31] = 1
            if hp.street2CBChance:             line[32] = 1
            if hp.street2CBDone:               line[33] = 1
            if hp.street3CBChance:             line[34] = 1
            if hp.street3CBDone:               line[35] = 1
            if hp.street4CBChance:             line[36] = 1
            if hp.street4CBDone:               line[37] = 1
            if hp.foldToStreet1CBChance:       line[38] = 1
            if hp.foldToStreet1CBDone:         line[39] = 1
            if hp.foldToStreet2CBChance:       line[40] = 1
            if hp.foldToStreet2CBDone:         line[41] = 1
            if hp.foldToStreet3CBChance:       line[42] = 1
            if hp.foldToStreet3CBDone:         line[43] = 1
            if hp.foldToStreet4CBChance:       line[44] = 1
            if hp.foldToStreet4CBDone:         line[45] = 1
            line[46] = hp.totalProfit
            if hp.street1CheckCallRaiseChance: line[47] = 1
            if hp.street1CheckCallRaiseDone:   line[48] = 1
            if hp.street2CheckCallRaiseChance: line[49] = 1
            if hp.street2CheckCallRaiseDone:   line[50] = 1
            if hp.street3CheckCallRaiseChance: line[51] = 1
            if hp.street3CheckCallRaiseDone:   line[52] = 1
            if hp.street4CheckCallRaiseChance: line[53] = 1
            if hp.street4CheckCallRaiseDone:   line[54] = 1
            line[55] = hand.gametypeId
            line[56] = hp.playerId
            line[57] = len(hand.handplayers_by_name)
            pos = {-2:'B', -1:'S', 'B': 'B', 'S': 'S', '0':'D', '1':'C', '2':'M', '3':'M', '4':'M', '5':'E', '6':'E', '7':'E', '8':'E', '9':'E' }
            line[58] = pos[str(hp.position)]
            line[59] = hp.tourneyTypeId
            line[60] = styleKey    # styleKey
            line[61] = hp.m_factor
            inserts.append(line)


        cursor = self.get_cursor()

        for row in inserts:
            # Try to do the update first:
            num = cursor.execute(update_hudcache, row)
            #print "DEBUG: values: %s" % row[-6:]
            # Test statusmessage to see if update worked, do insert if not
            # num is a cursor in sqlite
            if ((self.backend == self.PGSQL and cursor.statusmessage != "UPDATE 1")
                    or (self.backend == self.MYSQL_INNODB and num == 0) 
                    or (self.backend == self.SQLITE and num.rowcount == 0)):
                #move the last 6 items in WHERE clause of row from the end of the array
                # to the beginning for the INSERT statement
                #print "DEBUG: using INSERT: %s" % num
                row = row[-7:-1] + row[:-7] + row[-1:]
                num = cursor.execute(insert_hudcache, row)
                #print "DEBUG: Successfully(?: %s) updated HudCacho using INSERT" % num
            else:
                #print "DEBUG: Successfully updated HudCacho using UPDATE"
                pass

#################################
# Finish of NEWIMPORT CODE
#################################



    def storeHands(self, backend, site_hand_no, gametype_id
                  ,hand_start_time, names, tableName, maxSeats, hudCache
                  ,board_values, board_suits):

        cards = [Card.cardFromValueSuit(v,s) for v,s in zip(board_values,board_suits)]
        #stores into table hands:
        try:
            c = self.get_cursor()
            c.execute ("""INSERT INTO Hands 
                          (siteHandNo, gametypeId, handStart, seats, tableName, importTime, maxSeats
                          ,boardcard1,boardcard2,boardcard3,boardcard4,boardcard5
                          ,playersVpi, playersAtStreet1, playersAtStreet2
                          ,playersAtStreet3, playersAtStreet4, playersAtShowdown
                          ,street0Raises, street1Raises, street2Raises
                          ,street3Raises, street4Raises, street1Pot
                          ,street2Pot, street3Pot, street4Pot
                          ,showdownPot
                          ) 
                          VALUES 
                          (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                          %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       """.replace('%s', self.sql.query['placeholder'])
                      ,   (site_hand_no, gametype_id, hand_start_time, len(names), tableName, datetime.today(), maxSeats
                          ,cards[0], cards[1], cards[2], cards[3], cards[4]
                          ,hudCache['playersVpi'], hudCache['playersAtStreet1'], hudCache['playersAtStreet2']
                          ,hudCache['playersAtStreet3'], hudCache['playersAtStreet4'], hudCache['playersAtShowdown']
                          ,hudCache['street0Raises'], hudCache['street1Raises'], hudCache['street2Raises']
                          ,hudCache['street3Raises'], hudCache['street4Raises'], hudCache['street1Pot']
                          ,hudCache['street2Pot'], hudCache['street3Pot'], hudCache['street4Pot']
                          ,hudCache['showdownPot']
                          ))
            ret = self.get_last_insert_id(c)
        except:
            ret = -1
            raise FpdbError( "storeHands error: " + str(sys.exc_value) )

        return ret
    #end def storeHands
     
    def store_tourneys_players(self, tourney_id, player_ids, payin_amounts, ranks, winnings):
        try:
            result=[]
            cursor = self.get_cursor()
            #print "in store_tourneys_players. tourney_id:",tourney_id
            #print "player_ids:",player_ids
            #print "payin_amounts:",payin_amounts
            #print "ranks:",ranks
            #print "winnings:",winnings
            for i in xrange(len(player_ids)):
                try:
                    cursor.execute("savepoint ins_tplayer")
                    cursor.execute("""INSERT INTO TourneysPlayers
                    (tourneyId, playerId, payinAmount, rank, winnings) VALUES (%s, %s, %s, %s, %s)""".replace('%s', self.sql.query['placeholder']),
                    (tourney_id, player_ids[i], payin_amounts[i], ranks[i], winnings[i]))
                    
                    tmp = self.get_last_insert_id(cursor)
                    result.append(tmp)
                    #print "created new tourneys_players.id:", tmp
                except:
                    cursor.execute("rollback to savepoint ins_tplayer")
                    cursor.execute("SELECT id FROM TourneysPlayers WHERE tourneyId=%s AND playerId+0=%s".replace('%s', self.sql.query['placeholder'])
                                  ,(tourney_id, player_ids[i]))
                    tmp = cursor.fetchone()
                    #print "tried SELECTing tourneys_players.id:", tmp
                    try:
                        len(tmp)
                        result.append(tmp[0])
                    except:
                        print "tplayer id not found for tourney,player %s,%s" % (tourney_id, player_ids[i])
                        pass
        except:
            raise FpdbError( "store_tourneys_players error: " + str(sys.exc_value) )

        cursor.execute("release savepoint ins_tplayer")
        #print "store_tourneys_players returning", result
        return result
    #end def store_tourneys_players


    # read HandToWrite objects from q and insert into database
    def insert_queue_hands(self, q, maxwait=10, commitEachHand=True):
        n,fails,maxTries,firstWait = 0,0,4,0.1
        sendFinal = False
        t0 = time()
        while True:
            try:
                h = q.get(True)  # (True,maxWait) has probs if 1st part of import is all dups
            except Queue.Empty:
                # Queue.Empty exception thrown if q was empty for
                # if q.empty() also possible - no point if testing for Queue.Empty exception
                # maybe increment a counter and only break after a few times?
                # could also test threading.active_count() or look through threading.enumerate()
                # so break immediately if no threads, but count up to X exceptions if a writer
                # thread is still alive???
                print "queue empty too long - writer stopping ..."
                break
            except:
                print "writer stopping, error reading queue: " + str(sys.exc_info())
                break
            #print "got hand", str(h.get_finished())

            tries,wait,again = 0,firstWait,True
            while again:
                try:
                    again = False # set this immediately to avoid infinite loops!
                    if h.get_finished():
                        # all items on queue processed
                        sendFinal = True
                    else:
                        self.store_the_hand(h)
                        # optional commit, could be every hand / every N hands / every time a 
                        # commit message received?? mark flag to indicate if commits outstanding
                        if commitEachHand:
                            self.commit()
                        n = n + 1
                except:
                    #print "iqh store error", sys.exc_value # debug
                    self.rollback()
                    if re.search('deadlock', str(sys.exc_info()[1]), re.I):
                        # deadlocks only a problem if hudcache is being updated
                        tries = tries + 1
                        if tries < maxTries and wait < 5:    # wait < 5 just to make sure
                            print "deadlock detected - trying again ..."
                            sleep(wait)
                            wait = wait + wait
                            again = True
                        else:
                            print "too many deadlocks - failed to store hand " + h.get_siteHandNo()
                    if not again:
                        fails = fails + 1
                        err = traceback.extract_tb(sys.exc_info()[2])[-1]
                        print "***Error storing hand: "+err[2]+"("+str(err[1])+"): "+str(sys.exc_info()[1])
            # finished trying to store hand

            # always reduce q count, whether or not this hand was saved ok
            q.task_done()
        # while True loop

        self.commit()
        if sendFinal:
            q.task_done()
        print "db writer finished: stored %d hands (%d fails) in %.1f seconds" % (n, fails, time()-t0)
    # end def insert_queue_hands():


    def send_finish_msg(self, q):
        try:
            h = HandToWrite(True)
            q.put(h)
        except:
            err = traceback.extract_tb(sys.exc_info()[2])[-1]
            print "***Error sending finish: "+err[2]+"("+str(err[1])+"): "+str(sys.exc_info()[1])
    # end def send_finish_msg():

    def tRecogniseTourneyType(self, tourney):
        logging.debug("Database.tRecogniseTourneyType")
        typeId = 1
        # Check if Tourney exists, and if so retrieve TTypeId : in that case, check values of the ttype
        cursor = self.get_cursor()
        cursor.execute (self.sql.query['getTourneyTypeIdByTourneyNo'].replace('%s', self.sql.query['placeholder']),
                        (tourney.tourNo, tourney.siteId)
                        )
        result=cursor.fetchone()

        expectedValues = { 1 : "buyin", 2 : "fee", 4 : "isKO", 5 : "isRebuy", 6 : "speed", 
                           7 : "isHU", 8 : "isShootout", 9 : "isMatrix" }
        typeIdMatch = True

        try:
            len(result)
            typeId = result[0]
            logging.debug("Tourney found in db with Tourney_Type_ID = %d" % typeId)
            for ev in expectedValues :
                if ( getattr( tourney, expectedValues.get(ev) ) <> result[ev] ):
                    logging.debug("TypeId mismatch : wrong %s : Tourney=%s / db=%s" % (expectedValues.get(ev), getattr( tourney, expectedValues.get(ev)), result[ev]) )
                    typeIdMatch = False
                    #break
        except:
            # Tourney not found : a TourneyTypeId has to be found or created for that specific tourney
            typeIdMatch = False
    
        if typeIdMatch == False :
            # Check for an existing TTypeId that matches tourney info (buyin/fee, knockout, rebuy, speed, matrix, shootout)
            # if not found create it
            logging.debug("Searching for a TourneyTypeId matching TourneyType data")
            cursor.execute (self.sql.query['getTourneyTypeId'].replace('%s', self.sql.query['placeholder']), 
                            (tourney.siteId, tourney.buyin, tourney.fee, tourney.isKO,
                             tourney.isRebuy, tourney.speed, tourney.isHU, tourney.isShootout, tourney.isMatrix)
                            )
            result=cursor.fetchone()
        
            try:
                len(result)
                typeId = result[0]
                logging.debug("Existing Tourney Type Id found : %d" % typeId)
            except TypeError: #this means we need to create a new entry
                logging.debug("Tourney Type Id not found : create one")
                cursor.execute (self.sql.query['insertTourneyTypes'].replace('%s', self.sql.query['placeholder']),
                                (tourney.siteId, tourney.buyin, tourney.fee, tourney.isKO, tourney.isRebuy,
                                 tourney.speed, tourney.isHU, tourney.isShootout, tourney.isMatrix)
                                )
                typeId = self.get_last_insert_id(cursor)

        return typeId
    #end def tRecogniseTourneyType

        

# Class used to hold all the data needed to write a hand to the db
# mainParser() in fpdb_parse_logic.py creates one of these and then passes it to 
# self.insert_queue_hands()

class HandToWrite:

    def __init__(self, finished = False): # db_name and game not used any more
        try:
            self.finished = finished
            self.config = None
            self.settings = None
            self.base = None
            self.category = None
            self.siteTourneyNo = None
            self.buyin = None
            self.fee = None
            self.knockout = None
            self.entries = None
            self.prizepool = None
            self.tourneyStartTime = None
            self.isTourney = None
            self.tourneyTypeId = None
            self.siteID = None
            self.siteHandNo = None
            self.gametypeID = None
            self.handStartTime = None
            self.names = None
            self.playerIDs = None
            self.startCashes = None
            self.positions = None
            self.antes = None
            self.cardValues = None
            self.cardSuits = None
            self.boardValues = None
            self.boardSuits = None
            self.winnings = None
            self.rakes = None
            self.actionTypes = None
            self.allIns = None
            self.actionAmounts = None
            self.actionNos = None
            self.hudImportData = None
            self.maxSeats = None
            self.tableName = None
            self.seatNos = None
            self.payin_amounts = None # tourney import was complaining mightily about this missing
        except:
            print "htw.init error: " + str(sys.exc_info())
            raise
    # end def __init__

    def set_all( self, config, settings, base, category, siteTourneyNo, buyin
               , fee, knockout, entries, prizepool, tourneyStartTime
               , isTourney, tourneyTypeId, siteID, siteHandNo
               , gametypeID, handStartTime, names, playerIDs, startCashes
               , positions, antes, cardValues, cardSuits, boardValues, boardSuits
               , winnings, rakes, actionTypes, allIns, actionAmounts
               , actionNos, hudImportData, maxSeats, tableName, seatNos):
        
        try:
            self.config = config
            self.settings = settings
            self.base = base
            self.category = category
            self.siteTourneyNo = siteTourneyNo
            self.buyin = buyin
            self.fee = fee
            self.knockout = knockout
            self.entries = entries
            self.prizepool = prizepool
            self.tourneyStartTime = tourneyStartTime
            self.isTourney = isTourney
            self.tourneyTypeId = tourneyTypeId
            self.siteID = siteID
            self.siteHandNo = siteHandNo
            self.gametypeID = gametypeID
            self.handStartTime = handStartTime
            self.names = names
            self.playerIDs = playerIDs
            self.startCashes = startCashes
            self.positions = positions
            self.antes = antes
            self.cardValues = cardValues
            self.cardSuits = cardSuits
            self.boardValues = boardValues
            self.boardSuits = boardSuits
            self.winnings = winnings
            self.rakes = rakes
            self.actionTypes = actionTypes
            self.allIns = allIns
            self.actionAmounts = actionAmounts
            self.actionNos = actionNos
            self.hudImportData = hudImportData
            self.maxSeats = maxSeats
            self.tableName = tableName
            self.seatNos = seatNos
        except:
            print "htw.set_all error: " + str(sys.exc_info())
            raise
    # end def set_hand

    def get_finished(self):
        return( self.finished )
    # end def get_finished
    
    def get_siteHandNo(self):
        return( self.siteHandNo )
    # end def get_siteHandNo


if __name__=="__main__":
    c = Configuration.Config()

    db_connection = Database(c) # mysql fpdb holdem
#    db_connection = Database(c, 'fpdb-p', 'test') # mysql fpdb holdem
#    db_connection = Database(c, 'PTrackSv2', 'razz') # mysql razz
#    db_connection = Database(c, 'ptracks', 'razz') # postgres
    print "database connection object = ", db_connection.connection
    # db_connection.recreate_tables()
    db_connection.dropAllIndexes()
    db_connection.createAllIndexes()
    
    h = db_connection.get_last_hand()
    print "last hand = ", h
    
    hero = db_connection.get_player_id(c, 'PokerStars', 'nutOmatic')
    if hero:
        print "nutOmatic is id_player = %d" % hero
    
    stat_dict = db_connection.get_stats_from_hand(h, "ring")
    for p in stat_dict.keys():
        print p, "  ", stat_dict[p]
        
    print "cards =", db_connection.get_cards(u'1')
    db_connection.close_connection

    print "press enter to continue"
    sys.stdin.readline()

#Code borrowed from http://push.cx/2008/caching-dictionaries-in-python-vs-ruby
class LambdaDict(dict):
    def __init__(self, l):
        super(LambdaDict, self).__init__()
        self.l = l

    def __getitem__(self, key):
        if key in self:
            return self.get(key)
        else:
            self.__setitem__(key, self.l(key))
            return self.get(key)
