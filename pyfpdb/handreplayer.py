# -*- coding: utf-8 -*-

import threading
import subprocess
import traceback

import pygtk
pygtk.require('2.0')
import gtk
import gobject
import os
import sys
import math
import time
import datetime

import fpdb_import
import Database 
import Configuration
from AlchemyMappings import *

class HandReplayer (threading.Thread):
    def __init__(self, config, sql, mainwin, debug=True):
        self.db = Database.Database(config, sql=sql)

        # create table for list of hands
        self.hands_list = SimpleSpreadSheetWidget(['id', 'start time'])
        self.hands = self.db.session.query(HandInternal)[:10]
        for hand in self.hands:
            self.hands_list.append( [ hand.id, hand.handStart ] )

        self.table = TableWidget()

        
        self.vpane = gtk.VPaned()
        self.vpane.add1(self.hands_list)
        self.vpane.add2(self.table)


        self.main_vbox = gtk.VBox(False,1)
        self.main_vbox.add(self.vpane)
        self.main_vbox.show_all()

        self.hands_list.connect("select-cursor-row", self.open_hand)

    def get_vbox(self):
        return self.main_vbox

    def open_hand(self, *args):
        hn = self.hands_list.get_selected_index()
        hand = self.hands[hn]
        return self.table.open_hand(hand)



class SimpleSpreadSheetWidget(gtk.TreeView):
    def __init__(self, cols):
        """ cols is a list of columns headers """
        self.cols_headers = cols
        self.store = gtk.ListStore( *([str]*len(self.cols_headers)))

        super(SimpleSpreadSheetWidget, self).__init__(self.store)

        self.columns = [ gtk.TreeViewColumn(header) for header in self.cols_headers  ]
        self.cell = gtk.CellRendererText()
        for column in self.columns:
            self.append_column(column)
        for i, col in enumerate(self.columns):
            col.pack_start(self.cell, False if i==0 else True )
            col.add_attribute(self.cell, 'text', i)

    def append(self, row):
        self.store.append( map(str, row) ) 

    def get_selected_index(self):
        return self.get_selection().get_selected_rows()[1][0][0]

    def get_selected_values(self):
        iter = self.get_selection().get_selected()[1]
        return [ self.store.get(iter, i)[0] for i in range(len(self.cols_headers)) ] 


class TableWidget(gtk.Frame):
    """Widget represents poker table
    
    Controls players (bets, cards) and flop
    """

    def __init__(self):
        super(TableWidget, self).__init__( )
        self.main_container = gtk.Fixed()
        #self.main_container.set_has_window(True)
        #self.main_container.set_size_request(400, 400)
        #self.main_container.set_has_window(True)
        self.move_stack = []
        self.add(self.main_container)

        self.players = None #[PlayerWidget(str(i), 1000) for i in range(6)]

        self.common_cards = CardsWidget("Flop")
        self.put(self.common_cards, 0, 0)

        self.main_container.connect("size-allocate", self.redraw)

        self.replay = 0

    def open_hand(self, hand):
        print 'openhand'

        self.common_cards.reset()
        if self.players is not None:
            [p.destroy() for p in self.players.itervalues()]
        self.players = {}
        self.maxseats = hand.maxSeats


        for card in hand.boardcards:
            self.common_cards.add_card(card)

        for i,hp in enumerate(hand.handPlayers):
            wp = PlayerWidget(hp.name, hp.startCash)
            self.put(wp, 0, 0)
            self.players[hp.seatNo] = wp
            for card in hp.cards:
                wp.add_card(card)
            wp.show_all()
        
        self.redraw()

        self.actions = hand.actions_all.flat_actions
        self.current_action = -1

        self.replay += 1
        gobject.timeout_add(int(1.1 * 1000), self.next_action, self.replay)


    def next_action(self, current_replay):
        from decimal import Decimal
        self.current_action += 1
        if self.current_action >= len(self.actions) or self.replay > current_replay: 
            return False
        [p.update() for p in self.players.itervalues()]
        action = self.actions[self.current_action]
        print 'gona', action
        wp = self.players[action['seat']]
        atype = action['action'][1]
        wp.action = atype
        if atype in ('bets','raises'):
            wp.add_bet(Decimal(action['action'][2]))
        if atype in ('posts',):
            wp.add_bet(Decimal(action['action'][3]))

        wp.update(highlight = True)


        return True


    def redraw(self, widget=None, rect=None):
        #import time
        if self.players is None: return
        print 'redraw'
        if rect is None:
            rect = self.get_allocation()
        self.last_rect = getattr(self, 'last_rect', None)
        if rect == self.last_rect:
            return
        self.last_rect = rect
        #print 'redraw'
        self.d = getattr(self, 'd', 0)
        if 1 or self.d < 50:
            for i,p in self.players.iteritems(): 
                x, y = self.get_absolute_seat_coordinates(rect, i, self.maxseats)
                self.move(p, x, y)
            self.move(self.common_cards, *(self.convert_relative_cooordinates(0., 0., rect=rect)))
            self.move_flush()
        self.d += 1
        
    def put(self, widget, x, y):
        wrect = widget.get_allocation()
        x -= wrect.width
        y -= wrect.height
        return self.main_container.put(widget, int(x), int(y))

    def move(self, widget, x, y):
        wrect = widget.get_allocation()
        #print x,y, wrect
        w = wrect.width; h = wrect.height;
        x -= w*.5; 
        y -= h*.5;
        self.move_stack.append( [widget, x, x+w, y, y+h] )

    def move_flush(self, padding=50):
        if not self.move_stack: return

        print 'move flush'

        rect = self.main_container.get_allocation()
        w = rect.width; h = rect.height;
        #print '#'*10, rect

        x_min, x_max, y_min, y_max = self.move_stack[0][1:]
        for i in self.move_stack:
            #print i[1:]
            x_min = min(x_min, i[1])
            x_max = max(x_max, i[2])
            y_min = min(y_min, i[3])
            y_max = max(y_max, i[4])
        
        print x_min, x_max, y_min, y_max
        def apply_padding(x, standard, padding):
            return x * (1. - 2.*padding/standard) + padding

        def transformation_generator(min_, max_, standard):
            #print (max_, min_, standard)
            k = max ( standard, (max_ - min_) ) # compress only
            return lambda x: (x - min_ ) / k * standard


        if x_min < 0 or x_max >= w:
            print "x is outrange"
            transform = transformation_generator(x_min, x_max, w)
            for i in range(len(self.move_stack)):
                self.move_stack[i][1] = transform( self.move_stack[i][1] ) 
        else:
            print "x is ok"

        if y_min < 0 or y_max >= h:
            print "y is outrange"
            transform = transformation_generator(y_min, y_max, h)
            for i in range(len(self.move_stack)):
                self.move_stack[i][3] = transform( self.move_stack[i][3] ) 
        else:
            print "y is ok"

        for i in self.move_stack:
            #print i[1:]
            self.main_container.move(i[0], int(apply_padding(i[1], w, padding)), int(apply_padding(i[3], h, padding)))
        self.move_stack = []

    def debug_click_handler(self, widget):
        r = widget.get_allocation()
        x,y = r.x, r.y
        print r
        print widget.get_label(), x, y
        self.move(widget, x, y)

    @classmethod
    def convert_relative_cooordinates(cls, x, y, **kwargs):
        """Converts relative coordinates to 'real'

        Usage:
          convert_relative_cooordinates(cls, x, y, rect=rect) 
        OR
          convert_relative_cooordinates(cls, x, y, width=w, height=h) 
        """
        if 'rect' in kwargs:
            width, height = kwargs['rect'].width, kwargs['rect'].height
        else:
            width, height = kwargs['width'], kwargs['height']
        x,y = map(lambda c: (c+1.)*.5, (x,y))
        return width*x, height*y

    @staticmethod
    def get_relative_seat_coordinates(seat, maxseats):
        """Return relative (point in [-1;1]x[-1;1]) coordinates for current seat
        
        seat in range(maxseats)
        """
        alpha = 2. * math.pi * float(seat)/maxseats
        return ( math.cos(alpha), math.sin(alpha) )

    @classmethod
    def get_absolute_seat_coordinates(cls, rect, seat, maxseats, padding=0):
        """Return absolute (relative to frame) coordinates for current seat
        
        seat in range(maxseats)
        """
        x,y = cls.convert_relative_cooordinates( 
                # FIXME: line below is required but raising SyntaxError on win py2.5
                #*cls.get_relative_seat_coordinates(seat, maxseats),
                width = rect.width - 2*padding, height = rect.height - 2*padding)
        return map(lambda c: int(c + padding), (x,y))


class CardsWidget(gtk.HBox):
    """Widget containing set of cards with label"""
    def __init__(self, label=None):
        super(CardsWidget, self).__init__()
        self.cards = []
        if label:
            l = gtk.Label(label)
            l.set_use_markup(True)
            self.pack_start(l)

    def reset(self):
        [self.pop_card() for card in self.cards]

    def add_card(self, card):
        """ Add card to the set in display it

        card matches /.{2}/ re
        """
        c = gtk.Label(card) # TODO: gtk.Image here
        self.cards.append(c)
        self.pack_start(c)
        c.show()

    def pop_card(self):
        c = self.cards.pop()
        c.destroy()

#class RelativeFixed(gtk.Fixed):
#    """Fixed layout with relative [-1;1]x[-1;1] coordinates"""
#    def __init__(self):
#        self.queue = []
#        super(RelativeFixed, self).__init__()
#
#    def add(self, widget):
#        """Add new object to the continer"""
#        self.put(widget, 0, 0)
#
#    def move(self, widget, x_rel, y_rel):
#        """Add widget moving to the queue. 
#        
#        On flush widget _center_ will be moved in x_rel, y_rel
#        """
#        self.queue.append((widget, x_rel, y_rel))
#
#    def flush(self):
#        pass

class PlayerWidget(gtk.VBox):
    def __init__(self, name='', stack='', cards=[]):
        super(PlayerWidget, self).__init__()

        for s in ('pname', 'stack', 'bets', 'action'):
            l = gtk.Label()
            setattr(self, '%s_w' % s, l)
            l.set_use_markup(True)
            self.pack_start(l)

        self.initial_stack = stack
        self.pname = name
        self.bets = []
        self.action = None
        self.update()

        self.cards = CardsWidget("<b>Cards: </b>")
        for card in cards:
            self.cards.add_card(card)

        self.pack_start(self.cards)

    @property
    def stack(self):
        return self.initial_stack - sum(self.bets)

    def update(self, highlight=False):
        if highlight:
            fmt = '<b>%s</b>: <span foreground="#DD0000">%s</span>'
        else:
            fmt = '<b>%s</b>: %s'
        self.pname_w.set_label( fmt % ('Name', self.pname) )
        self.stack_w.set_label( fmt % ('Stack', self.stack) )
        if self.action:
            self.action_w.set_label( fmt % ('Action', self.action) )
        self.bets_w.set_label( fmt % ('Bets', sum(self.bets)) )

    def add_bet(self, bet):
        self.bets.append(bet)
        self.update()

    def add_card(self, card):
        self.cards.add_card(card)

    

