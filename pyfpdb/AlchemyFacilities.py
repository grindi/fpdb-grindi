# -*- coding: utf-8 -*-
from decimal import Decimal

from sqlalchemy import types

import Card

class CardColumn(types.TypeDecorator):
    """Stores cards as smallints
    
    Automatically converts values like '9h' to smallint

    >>> CardColumn().process_bind_param( 'Td', '' )
    22
    >>> CardColumn().process_bind_param( u'Td', '' )
    22
    >>> CardColumn().process_bind_param( 22, '' )
    22
    >>> CardColumn().process_result_value( 22, '' )
    'Td'
    """

    impl = types.SmallInteger

    def process_bind_param(self, value, dialect):
        if value is None or isinstance(value, int):
            return value
        elif isinstance(value, basestring) and len(value) == 2:
            return Card.encodeCard(str(value))
        else:
            raise Exception, "Incorrect card value: " + repr(value)

    def process_result_value(self, value, dialect):
        return Card.valueSuitFromCard( value )


class MoneyColumn(types.TypeDecorator):
    """Stores money: bets, pots, etc
    
    Understands: 
        Decimal as real amount
        int     as amount mupliplied by 100
        string  as decimal
    Returns Decimal
    >>> MoneyColumn().process_bind_param( 230, '' )
    230
    >>> MoneyColumn().process_bind_param( Decimal('2.30'), '' )
    230
    >>> MoneyColumn().process_bind_param( '2.30', '' )
    230
    >>> MoneyColumn().process_result_value( 230, '' )
    Decimal('2.3')
    """

    impl = types.SmallInteger

    def process_bind_param(self, value, dialect):
        if value is None or isinstance(value, int):
            return value
        elif isinstance(value, basestring) or isinstance(value, Decimal): 
            return int(Decimal(value)*100)
        else:
            raise Exception, "Incorrect amount:" + repr(value)

    def process_result_value(self, value, dialect):
        return Decimal(value)/100


