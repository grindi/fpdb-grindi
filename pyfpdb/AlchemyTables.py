# -*- coding: utf-8 -*-
"""@package AlchemyTables
Contains all sqlalchemy tables
"""

from sqlalchemy import Table, Float, Column, Integer, String, MetaData, ForeignKey, Boolean, SmallInteger, DateTime, Text

from AlchemyFacilities import CardColumn, MoneyColumn


metadata = MetaData()


hands_table = Table('Hands', metadata,
        Column('id',            Integer, primary_key=True),
        Column('tableName',     String(30), nullable=False),
        Column('siteHandNo',    Integer, nullable=False),
        Column('gametypeId',    SmallInteger, ForeignKey('Gametypes.id'), nullable=False),
        Column('handStart',     DateTime, nullable=False),
        Column('importTime',    DateTime, nullable=False),
        Column('seats',         SmallInteger, nullable=False),
        Column('maxSeats',      SmallInteger, nullable=False),

        Column('boardcard1',    CardColumn),
        Column('boardcard2',    CardColumn),
        Column('boardcard3',    CardColumn),
        Column('boardcard4',    CardColumn),
        Column('boardcard5',    CardColumn),
        Column('texture',       SmallInteger),
        Column('playersVpi',    SmallInteger, nullable=False),
        Column('playersAtStreet1', SmallInteger, nullable=False, default=0),
        Column('playersAtStreet2', SmallInteger, nullable=False, default=0),
        Column('playersAtStreet3', SmallInteger, nullable=False, default=0),
        Column('playersAtStreet4', SmallInteger, nullable=False, default=0),
        Column('playersAtShowdown',SmallInteger, nullable=False),
        Column('street0Raises', SmallInteger, nullable=False),
        Column('street1Raises', SmallInteger, nullable=False),
        Column('street2Raises', SmallInteger, nullable=False),
        Column('street3Raises', SmallInteger, nullable=False),
        Column('street4Raises', SmallInteger, nullable=False),
        Column('street1Pot',    MoneyColumn),
        Column('street2Pot',    MoneyColumn),
        Column('street3Pot',    MoneyColumn),
        Column('street4Pot',    MoneyColumn),
        Column('showdownPot',   MoneyColumn),
        Column('comment',       Text),
        Column('commentTs',     DateTime),
)


hands_actions_table = Table('HandsActions', metadata,
        Column('id',            Integer, primary_key=True),
        Column('handsPlayerId', Integer, ForeignKey("HandsPlayers.id"), nullable=False),
        Column('street',        SmallInteger, nullable=False),
        Column('actionNo',      SmallInteger, nullable=False),
        # FIXME: change create table to string(20) \\grindi
        Column('action',        String(20), nullable=False), 
        Column('allIn',         Boolean, nullable=False),
        Column('amount',        MoneyColumn, nullable=False),
        Column('comment',       Text),
        Column('commentTs',     DateTime),
)


hands_players_table = Table('HandsPlayers', metadata,
        Column('id',                Integer, primary_key=True),
        Column('handId',            Integer, ForeignKey("Hands.id"), nullable=False),
        Column('playerId',          Integer, ForeignKey("Players.id"), nullable=False),
        Column('startCash',         MoneyColumn),
        Column('position',          String(1)), #CHAR(1)
        Column('seatNo',            SmallInteger, nullable=False), #SMALLINT NOT NULL
            
        Column('card1',             SmallInteger, nullable=False), #smallint NOT NULL,
        Column('card2',             SmallInteger, nullable=False), #smallint NOT NULL
        Column('card3',             SmallInteger), #smallint
        Column('card4',             SmallInteger), #smallint
        Column('card5',             SmallInteger), #smallint
        Column('card6',             SmallInteger), #smallint
        Column('card7',             SmallInteger), #smallint
        Column('startCards',        SmallInteger), #smallint
            
        Column('ante',              Integer), #INT
        Column('winnings',          Integer, nullable=False), #int NOT NULL
        Column('rake',              Integer, nullable=False), #int NOT NULL
        Column('totalProfit',       Integer), #INT
        Column('comment',           Text), #text
        Column('commentTs',         DateTime), #DATETIME
        Column('tourneysPlayersId', Integer,), #BIGINT UNSIGNED
        Column('tourneyTypeId',     Integer,), #SMALLINT UNSIGNED
#        Column('tourneysPlayersId',Integer, ForeignKey("TourneyTypes.id"),), #BIGINT UNSIGNED
#        Column('tourneyTypeId',    Integer, ForeignKey("TourneyPlayers.id"),), #SMALLINT UNSIGNED

        Column('wonWhenSeenStreet1',Float), #FLOAT
        Column('wonWhenSeenStreet2',Float), #FLOAT
        Column('wonWhenSeenStreet3',Float), #FLOAT
        Column('wonWhenSeenStreet4',Float), #FLOAT
        Column('wonAtSD',           Float), #FLOAT

        Column('street0VPI',        Boolean), #BOOLEAN
        Column('street0Aggr',       Boolean), #BOOLEAN
        Column('street0_3BChance',  Boolean), #BOOLEAN
        Column('street0_3BDone',    Boolean), #BOOLEAN
        Column('street0_4BChance',  Boolean), #BOOLEAN
        Column('street0_4BDone',    Boolean), #BOOLEAN
        Column('other3BStreet0',    Boolean), #BOOLEAN
        Column('other4BStreet0',    Boolean), #BOOLEAN

        Column('street1Seen',       Boolean), #BOOLEAN
        Column('street2Seen',       Boolean), #BOOLEAN
        Column('street3Seen',       Boolean), #BOOLEAN
        Column('street4Seen',       Boolean), #BOOLEAN
        Column('sawShowdown',       Boolean), #BOOLEAN

        Column('street1Aggr',       Boolean), #BOOLEAN
        Column('street2Aggr',       Boolean), #BOOLEAN
        Column('street3Aggr',       Boolean), #BOOLEAN
        Column('street4Aggr',       Boolean), #BOOLEAN

        Column('otherRaisedStreet0',Boolean), #BOOLEAN
        Column('otherRaisedStreet1',Boolean), #BOOLEAN
        Column('otherRaisedStreet2',Boolean), #BOOLEAN
        Column('otherRaisedStreet3',Boolean), #BOOLEAN
        Column('otherRaisedStreet4',Boolean), #BOOLEAN
        Column('foldToOtherRaisedStreet0',   Boolean), #BOOLEAN
        Column('foldToOtherRaisedStreet1',   Boolean), #BOOLEAN
        Column('foldToOtherRaisedStreet2',   Boolean), #BOOLEAN
        Column('foldToOtherRaisedStreet3',   Boolean), #BOOLEAN
        Column('foldToOtherRaisedStreet4',   Boolean), #BOOLEAN

        Column('stealAttemptChance',         Boolean), #BOOLEAN
        Column('stealAttempted',             Boolean), #BOOLEAN
        Column('foldBbToStealChance',        Boolean), #BOOLEAN
        Column('foldedBbToSteal',            Boolean), #BOOLEAN
        Column('foldSbToStealChance',        Boolean), #BOOLEAN
        Column('foldedSbToSteal',            Boolean), #BOOLEAN

        Column('street1CBChance',            Boolean), #BOOLEAN
        Column('street1CBDone',              Boolean), #BOOLEAN
        Column('street2CBChance',            Boolean), #BOOLEAN
        Column('street2CBDone',              Boolean), #BOOLEAN
        Column('street3CBChance',            Boolean), #BOOLEAN
        Column('street3CBDone',              Boolean), #BOOLEAN
        Column('street4CBChance',            Boolean), #BOOLEAN
        Column('street4CBDone',              Boolean), #BOOLEAN

        Column('foldToStreet1CBChance',      Boolean), #BOOLEAN
        Column('foldToStreet1CBDone',        Boolean), #BOOLEAN
        Column('foldToStreet2CBChance',      Boolean), #BOOLEAN
        Column('foldToStreet2CBDone',        Boolean), #BOOLEAN
        Column('foldToStreet3CBChance',      Boolean), #BOOLEAN
        Column('foldToStreet3CBDone',        Boolean), #BOOLEAN
        Column('foldToStreet4CBChance',      Boolean), #BOOLEAN
        Column('foldToStreet4CBDone',        Boolean), #BOOLEAN

        Column('street1CheckCallRaiseChance',Boolean), #BOOLEAN
        Column('street1CheckCallRaiseDone',  Boolean), #BOOLEAN
        Column('street2CheckCallRaiseChance',Boolean), #BOOLEAN
        Column('street2CheckCallRaiseDone',  Boolean), #BOOLEAN
        Column('street3CheckCallRaiseChance',Boolean), #BOOLEAN
        Column('street3CheckCallRaiseDone',  Boolean), #BOOLEAN
        Column('street4CheckCallRaiseChance',Boolean), #BOOLEAN
        Column('street4CheckCallRaiseDone',  Boolean), #BOOLEAN

        Column('street0Calls',               SmallInteger), #TINYINT
        Column('street1Calls',               SmallInteger), #TINYINT
        Column('street2Calls',               SmallInteger), #TINYINT
        Column('street3Calls',               SmallInteger), #TINYINT
        Column('street4Calls',               SmallInteger), #TINYINT
        Column('street0Bets',                SmallInteger), #TINYINT
        Column('street1Bets',                SmallInteger), #TINYINT
        Column('street2Bets',                SmallInteger), #TINYINT
        Column('street3Bets',                SmallInteger), #TINYINT
        Column('street4Bets',                SmallInteger), #TINYINT
        Column('street0Raises',              SmallInteger), #TINYINT
        Column('street1Raises',              SmallInteger), #TINYINT
        Column('street2Raises',              SmallInteger), #TINYINT
        Column('street3Raises',              SmallInteger), #TINYINT
        Column('street4Raises',              SmallInteger), #TINYINT

        Column('actionString',               String), #VARCHAR(15)
)


players_table = Table('Players', metadata,
        Column('id',            Integer, primary_key=True),
        Column('name',          String(32), nullable=False), # VARCHAR(32) CHARACTER SET utf8 NOT NULL
        Column('siteId',        SmallInteger, ForeignKey("Sites.id"), nullable=False), # SMALLINT 
        Column('comment',       Text), # text
        Column('commentTs',     DateTime), # DATETIME
)


sites_table = Table('Sites', metadata,
        Column('id',            Integer, primary_key=True),
        Column('name',          String(32), nullable=False), # varchar(32) NOT NULL
        Column('currency',      String(3), nullable=False), # char(3) NOT NULL
)


gametypes_table = Table('Gametypes', metadata,
        Column('id',            Integer, primary_key=True),
        Column('siteId',        SmallInteger, ForeignKey("Sites.id"), nullable=False), # SMALLINT
        Column('type',          String(4), nullable=False), # char(4) NOT NULL
        Column('base',          String(4), nullable=False), # char(4) NOT NULL
        Column('category',      String(9), nullable=False), # varchar(9) NOT NULL
        Column('limitType',     String(2), nullable=False), # char(2) NOT NULL
        Column('hiLo',          String(1), nullable=False), # char(1) NOT NULL
        Column('smallBlind',    Integer(3)), # int
        Column('bigBlind',      Integer(3)), # int
        Column('smallBet',      Integer(3), nullable=False), # int NOT NULL
        Column('bigBet',        Integer(3), nullable=False), # int NOT NULL
)


hud_cache_table = Table('HudCache', metadata,
        Column('id',            Integer, primary_key=True),
        Column('gametypeId',    SmallInteger, ForeignKey("Gametypes.id"), nullable=False), # SMALLINT 
        Column('playerId',      SmallInteger, ForeignKey("Players.id"), nullable=False), # SMALLINT 
        Column('activeSeats',   SmallInteger, nullable=False), # SMALLINT NOT NULL
        Column('position',      String(1)), # CHAR(1)
        Column('tourneyTypeId', SmallInteger,  nullable=False), # SMALLINT 
#        Column('tourneyTypeId', SmallInteger, ForeignKey("TourneyTypes.id"), nullable=False), # SMALLINT 
        Column('styleKey',      String(7), nullable=False), # CHAR(7) NOT NULL
        Column('HDs',           Integer, nullable=False), # INT NOT NULL

        Column('wonWhenSeenStreet1',    Float), # FLOAT
        Column('wonWhenSeenStreet2',    Float), # FLOAT
        Column('wonWhenSeenStreet3',    Float), # FLOAT
        Column('wonWhenSeenStreet4',    Float), # FLOAT
        Column('wonAtSD',               Float), # FLOAT

        Column('street0VPI',            Integer), # INT
        Column('street0Aggr',           Integer), # INT
        Column('street0_3BChance',      Integer), # INT
        Column('street0_3BDone',        Integer), # INT
        Column('street0_4BChance',      Integer), # INT
        Column('street0_4BDone',        Integer), # INT
        Column('other3BStreet0',        Integer), # INT
        Column('other4BStreet0',        Integer), # INT

        Column('street1Seen',           Integer), # INT
        Column('street2Seen',           Integer), # INT
        Column('street3Seen',           Integer), # INT
        Column('street4Seen',           Integer), # INT
        Column('sawShowdown',           Integer), # INT

        Column('street1Aggr',           Integer), # INT
        Column('street2Aggr',           Integer), # INT
        Column('street3Aggr',           Integer), # INT
        Column('street4Aggr',           Integer), # INT

        Column('otherRaisedStreet0',        Integer), # INT
        Column('otherRaisedStreet1',        Integer), # INT
        Column('otherRaisedStreet2',        Integer), # INT
        Column('otherRaisedStreet3',        Integer), # INT
        Column('otherRaisedStreet4',        Integer), # INT
        Column('foldToOtherRaisedStreet0',  Integer), # INT
        Column('foldToOtherRaisedStreet1',  Integer), # INT
        Column('foldToOtherRaisedStreet2',  Integer), # INT
        Column('foldToOtherRaisedStreet3',  Integer), # INT
        Column('foldToOtherRaisedStreet4',  Integer), # INT

        Column('stealAttemptChance',        Integer), # INT
        Column('stealAttempted',            Integer), # INT
        Column('foldBbToStealChance',       Integer), # INT
        Column('foldedBbToSteal',           Integer), # INT
        Column('foldSbToStealChance',       Integer), # INT
        Column('foldedSbToSteal',           Integer), # INT

        Column('street1CBChance',           Integer), # INT
        Column('street1CBDone',             Integer), # INT
        Column('street2CBChance',           Integer), # INT
        Column('street2CBDone',             Integer), # INT
        Column('street3CBChance',           Integer), # INT
        Column('street3CBDone',             Integer), # INT
        Column('street4CBChance',           Integer), # INT
        Column('street4CBDone',             Integer), # INT

        Column('foldToStreet1CBChance',     Integer), # INT
        Column('foldToStreet1CBDone',       Integer), # INT
        Column('foldToStreet2CBChance',     Integer), # INT
        Column('foldToStreet2CBDone',       Integer), # INT
        Column('foldToStreet3CBChance',     Integer), # INT
        Column('foldToStreet3CBDone',       Integer), # INT
        Column('foldToStreet4CBChance',     Integer), # INT
        Column('foldToStreet4CBDone',       Integer), # INT

        Column('totalProfit',               Integer), # INT

        Column('street1CheckCallRaiseChance',   Integer), # INT
        Column('street1CheckCallRaiseDone',     Integer), # INT
        Column('street2CheckCallRaiseChance',   Integer), # INT
        Column('street2CheckCallRaiseDone',     Integer), # INT
        Column('street3CheckCallRaiseChance',   Integer), # INT
        Column('street3CheckCallRaiseDone',     Integer), # INT
        Column('street4CheckCallRaiseChance',   Integer), # INT
        Column('street4CheckCallRaiseDone',     Integer), # INT

        Column('street0Calls',          Integer), # INT
        Column('street1Calls',          Integer), # INT
        Column('street2Calls',          Integer), # INT
        Column('street3Calls',          Integer), # INT
        Column('street4Calls',          Integer), # INT
        Column('street0Bets',           Integer), # INT
        Column('street1Bets',           Integer), # INT
        Column('street2Bets',           Integer), # INT
        Column('street3Bets',           Integer), # INT
        Column('street4Bets',           Integer), # INT
        Column('street0Raises',         Integer), # INT
        Column('street1Raises',         Integer), # INT
        Column('street2Raises',         Integer), # INT
        Column('street3Raises',         Integer), # INT
        Column('street4Raises',         Integer), # INT
)


def sss():
    "Debug function. Returns (config, sql, db)"

    import Configuration, SQL, Database, os
    class Dummy(object):
        pass
    self = Dummy()
    self.config = Configuration.Config()
    self.settings = {}
    if (os.sep=="/"):
        self.settings['os']="linuxmac"
    else:
        self.settings['os']="windows"

    self.settings.update(self.config.get_db_parameters())
    self.settings.update(self.config.get_tv_parameters())
    self.settings.update(self.config.get_import_parameters())
    self.settings.update(self.config.get_default_paths())

    self.sql = SQL.Sql(type = self.settings['db-type'], db_server = self.settings['db-server'])
    self.db = Database.Database(self.config, sql = self.sql)

    return self.config, self.sql, self.db

