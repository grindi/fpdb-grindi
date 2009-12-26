# -*- coding: utf-8 -*-
"""@package print_hand_stats
Supply debugging facilities: parse hand and print its stats.
Usage:
    python print_hand_stats.py <site-name> <path to hh>
    <site-name> is something like PartyPoker
"""

import sys

from HandHistoryConverter import getSiteHhc
from AlchemyTables import sss

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print "Usage: python %s <site-name> <path to hh>" % sys.argv[0]
        sys.exit(0)
    site_name, hh_path = sys.argv[1:3]
    (config, sql, db) = sss()
    hhc = getSiteHhc(config, site_name)
    hands = hhc(hh_path).processedHands
    for hand in hands:
        hand.prepInsert(db)
        print hand.handText
        print hand.internal
        print '\n', '#'*50, '\n'


    
    


