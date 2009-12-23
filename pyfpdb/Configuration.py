#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Configuration.py

Handles HUD configuration files.
"""
#    Copyright 2008, 2009,  Ray E. Barker

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

#    Standard Library modules
from __future__ import with_statement
import os
import sys
import inspect
import string
import traceback
import shutil
import xml.dom.minidom
from xml.dom.minidom import Node

import logging, logging.config
import ConfigParser

##############################################################################
#    Functions for finding config files and setting up logging
#    Also used in other modules that use logging.

def get_default_config_path():
    """Returns the path where the fpdb config file _should_ be stored."""
    if os.name == 'posix':
        config_path = os.path.join(os.path.expanduser("~"), '.fpdb')
    elif os.name == 'nt':
        config_path = os.path.join(os.environ["APPDATA"], 'fpdb')
    else: config_path = False
    return config_path

def get_exec_path():
    """Returns the path to the fpdb.(py|exe) file we are executing"""
    if hasattr(sys, "frozen"):  # compiled by py2exe
        return os.path.dirname(sys.executable)
    else:
        pathname = os.path.dirname(sys.argv[0])
        return os.path.abspath(pathname)

def get_config(file_name, fallback = True):
    """Looks in cwd and in self.default_config_path for a config file."""
    config_path = os.path.join(get_exec_path(), file_name)
#    print "config_path=", config_path
    if os.path.exists(config_path):    # there is a file in the cwd
        return config_path             # so we use it
    else: # no file in the cwd, look where it should be in the first place
        config_path = os.path.join(get_default_config_path(), file_name)
#        print "config path 2=", config_path
        if os.path.exists(config_path):
            return config_path

#    No file found
    if not fallback:
        return False

#    OK, fall back to the .example file, should be in the start dir
    if os.path.exists(file_name + ".example"):
        try:
            shutil.copyfile(file_name + ".example", file_name)
            print "No %s found, using %s.example.\n" % (file_name, file_name)
            print "A %s file has been created.  You will probably have to edit it." % file_name
            sys.stderr.write("No %s found, using %s.example.\n" % (file_name, file_name) )
        except:
            print "No %s found, cannot fall back. Exiting.\n" % file_name
            sys.stderr.write("No %s found, cannot fall back. Exiting.\n" % file_name)
            sys.exit()
    return file_name

def get_logger(file_name, config = "config", fallback = False):
    conf = get_config(file_name, fallback = fallback)
    if conf:
        try:
            logging.config.fileConfig(conf)
            log = logging.getLogger(config)
            log.debug("%s logger initialised" % config)
            return log
        except:
            pass

    log = logging.basicConfig()
    log = logging.getLogger()
    log.debug("config logger initialised")
    return log

#    find a logging.conf file and set up logging
log = get_logger("logging.conf")

########################################################################
# application wide consts

APPLICATION_NAME_SHORT = 'fpdb'
APPLICATION_VERSION = 'xx.xx.xx'

DIR_SELF = os.path.dirname(get_exec_path())
#TODO: imo no good idea to place 'database' in parent dir
DIR_DATABASES = os.path.join(os.path.dirname(DIR_SELF), 'database')

DATABASE_TYPE_POSTGRESQL = 'postgresql'
DATABASE_TYPE_SQLITE = 'sqlite'
DATABASE_TYPE_MYSQL = 'mysql'
DATABASE_TYPES = (
        DATABASE_TYPE_POSTGRESQL,
        DATABASE_TYPE_SQLITE,
        DATABASE_TYPE_MYSQL,
        )

NEWIMPORT = True

########################################################################
def string_to_bool(string, default=True):
    """converts a string representation of a boolean value to boolean True or False
    @param string: (str) the string to convert
    @param default: value to return if the string can not be converted to a boolean value
    """
    string = string.lower()
    if string in ('1', 'true', 't'):
        return True
    elif string in ('0', 'false', 'f'):
        return False
    return default

class Layout:
    def __init__(self, node):

        self.max    = int( node.getAttribute('max') )
        if node.hasAttribute('fav_seat'): self.fav_seat = int( node.getAttribute('fav_seat') )
        self.width    = int( node.getAttribute('width') )
        self.height   = int( node.getAttribute('height') )

        self.location = []
        self.location = map(lambda x: None, range(self.max+1)) # fill array with max seats+1 empty entries

        for location_node in node.getElementsByTagName('location'):
            if location_node.getAttribute('seat') != "":
                self.location[int( location_node.getAttribute('seat') )] = (int( location_node.getAttribute('x') ), int( location_node.getAttribute('y')))
            elif location_node.getAttribute('common') != "":
                self.common = (int( location_node.getAttribute('x') ), int( location_node.getAttribute('y')))

    def __str__(self):
        temp = "    Layout = %d max, width= %d, height = %d" % (self.max, self.width, self.height)
        if hasattr(self, 'fav_seat'): temp = temp + ", fav_seat = %d\n" % self.fav_seat
        else: temp = temp + "\n"
        if hasattr(self, "common"):
            temp = temp + "        Common = (%d, %d)\n" % (self.common[0], self.common[1])
        temp = temp + "        Locations = "
        for i in range(1, len(self.location)):
            temp = temp + "(%d,%d)" % self.location[i]

        return temp + "\n"

class Site:
    def __init__(self, node):
        def normalizePath(path):
            "Normalized existing pathes"
            if os.path.exists(path):
                return os.path.abspath(path)
            return path

        self.site_name    = node.getAttribute("site_name")
        self.table_finder = node.getAttribute("table_finder")
        self.screen_name  = node.getAttribute("screen_name")
        self.site_path    = normalizePath(node.getAttribute("site_path"))
        self.HH_path    = normalizePath(node.getAttribute("HH_path"))
        self.decoder    = node.getAttribute("decoder")
        self.hudopacity   = node.getAttribute("hudopacity")
        self.hudbgcolor   = node.getAttribute("bgcolor")
        self.hudfgcolor   = node.getAttribute("fgcolor")
        self.converter    = node.getAttribute("converter")
        self.aux_window   = node.getAttribute("aux_window")
        self.font        = node.getAttribute("font")
        self.font_size    = node.getAttribute("font_size")
        self.use_frames   = node.getAttribute("use_frames")
        self.enabled    = string_to_bool(node.getAttribute("enabled"), default=True)
        self.xpad         = node.getAttribute("xpad")
        self.ypad         = node.getAttribute("ypad")
        self.layout       = {}

        print "Loading site", self.site_name

        for layout_node in node.getElementsByTagName('layout'):
            lo = Layout(layout_node)
            self.layout[lo.max] = lo

#   Site defaults
        self.xpad = 1 if self.xpad == "" else int(self.xpad)
        self.ypad = 0 if self.ypad == "" else int(self.ypad)
        self.font_size = 7 if self.font_size == "" else int(self.font_size)
        self.hudopacity = 1.0 if self.hudopacity == "" else float(self.hudopacity)

        if self.use_frames == "": self.use_frames = False
        if self.font       == "": self.font = "Sans"
        if self.hudbgcolor == "": self.hudbgcolor = "#000000"
        if self.hudfgcolor == "": self.hudfgcolor = "#FFFFFF"

    def __str__(self):
        temp = "Site = " + self.site_name + "\n"
        for key in dir(self):
            if key.startswith('__'): continue
            if key == 'layout':  continue
            value = getattr(self, key)
            if callable(value): continue
            temp = temp + '    ' + key + " = " + str(value) + "\n"

        for layout in self.layout:
            temp = temp + "%s" % self.layout[layout]

        return temp

class Stat:
    def __init__(self):
        pass

    def __str__(self):
        temp = "        stat_name = %s, row = %d, col = %d, tip = %s, click = %s, popup = %s\n" % (self.stat_name, self.row, self.col, self.tip, self.click, self.popup)
        return temp

class Game:
    def __init__(self, node):
        self.game_name = node.getAttribute("game_name")
        self.rows    = int( node.getAttribute("rows") )
        self.cols    = int( node.getAttribute("cols") )
        self.xpad    = node.getAttribute("xpad")
        self.ypad    = node.getAttribute("ypad")

#    Defaults
        if self.xpad == "": self.xpad = 1
        else: self.xpad = int(self.xpad)
        if self.ypad == "": self.ypad = 0
        else: self.ypad = int(self.ypad)

        aux_text = node.getAttribute("aux")
        aux_list = aux_text.split(',')
        for i in range(0, len(aux_list)):
            aux_list[i] = aux_list[i].strip()
        self.aux = aux_list

        self.stats    = {}
        for stat_node in node.getElementsByTagName('stat'):
            stat = Stat()
            stat.stat_name = stat_node.getAttribute("stat_name")
            stat.row     = int( stat_node.getAttribute("row") )
            stat.col     = int( stat_node.getAttribute("col") )
            stat.tip     = stat_node.getAttribute("tip")
            stat.click    = stat_node.getAttribute("click")
            stat.popup    = stat_node.getAttribute("popup")
            stat.hudprefix = stat_node.getAttribute("hudprefix")
            stat.hudsuffix = stat_node.getAttribute("hudsuffix")
            stat.hudcolor  = stat_node.getAttribute("hudcolor")

            self.stats[stat.stat_name] = stat

    def __str__(self):
        temp = "Game = " + self.game_name + "\n"
        temp = temp + "    rows = %d\n" % self.rows
        temp = temp + "    cols = %d\n" % self.cols
        temp = temp + "    xpad = %d\n" % self.xpad
        temp = temp + "    ypad = %d\n" % self.ypad
        temp = temp + "    aux = %s\n" % self.aux

        for stat in self.stats.keys():
            temp = temp + "%s" % self.stats[stat]

        return temp

class Database:
    def __init__(self, node):
        self.db_name   = node.getAttribute("db_name")
        self.db_server = node.getAttribute("db_server").lower()
        self.db_ip    = node.getAttribute("db_ip")
        self.db_user   = node.getAttribute("db_user")
        self.db_pass   = node.getAttribute("db_pass")
        self.db_selected = string_to_bool(node.getAttribute("default"), default=False)
        log.debug("Database db_name:'%(name)s'  db_server:'%(server)s'  db_ip:'%(ip)s'  db_user:'%(user)s'  db_pass (not logged)  selected:'%(sel)s'" \
                % { 'name':self.db_name, 'server':self.db_server, 'ip':self.db_ip, 'user':self.db_user, 'sel':self.db_selected} )

    def __str__(self):
        temp = 'Database = ' + self.db_name + '\n'
        for key in dir(self):
            if key.startswith('__'): continue
            value = getattr(self, key)
            if callable(value): continue
            temp = temp + '    ' + key + " = " + repr(value) + "\n"
        return temp

class Aux_window:
    def __init__(self, node):
        for (name, value) in node.attributes.items():
            setattr(self, name, value)

        self.layout = {}
        for layout_node in node.getElementsByTagName('layout'):
            lo = Layout(layout_node)
            self.layout[lo.max] = lo

    def __str__(self):
        temp = 'Aux = ' + self.name + "\n"
        for key in dir(self):
            if key.startswith('__'): continue
            if key == 'layout':  continue
            value = getattr(self, key)
            if callable(value): continue
            temp = temp + '    ' + key + " = " + value + "\n"

        for layout in self.layout:
            temp = temp + "%s" % self.layout[layout]
        return temp

class HHC:
    def __init__(self, node):
        self.site    = node.getAttribute("site")
        self.converter = node.getAttribute("converter")

    def __str__(self):
        return "%s:\t%s" % (self.site, self.converter)


class Popup:
    def __init__(self, node):
        self.name  = node.getAttribute("pu_name")
        self.pu_stats    = []
        for stat_node in node.getElementsByTagName('pu_stat'):
            self.pu_stats.append(stat_node.getAttribute("pu_stat_name"))

    def __str__(self):
        temp = "Popup = " + self.name + "\n"
        for stat in self.pu_stats:
            temp = temp + " " + stat
        return temp + "\n"

class Import:
    def __init__(self, node):
        self.node = node
        self.interval    = node.getAttribute("interval")
        self.callFpdbHud   = node.getAttribute("callFpdbHud")
        self.hhArchiveBase = node.getAttribute("hhArchiveBase")
        self.saveActions = string_to_bool(node.getAttribute("saveActions"), default=True)
        self.fastStoreHudCache = string_to_bool(node.getAttribute("fastStoreHudCache"), default=False)

    def __str__(self):
        return "    interval = %s\n    callFpdbHud = %s\n    hhArchiveBase = %s\n    saveActions = %s\n    fastStoreHudCache = %s\n" \
            % (self.interval, self.callFpdbHud, self.hhArchiveBase, self.saveActions, self.fastStoreHudCache)

class HudUI:
    def __init__(self, node):
        self.node = node
        self.label  = node.getAttribute('label')
        #
        self.hud_style      = node.getAttribute('stat_range')
        self.hud_days       = node.getAttribute('stat_days')
        self.aggregate_ring = string_to_bool(node.getAttribute('aggregate_ring_game_stats'))
        self.aggregate_tour = string_to_bool(node.getAttribute('aggregate_tourney_stats'))
        self.agg_bb_mult    = node.getAttribute('aggregation_level_multiplier')
        #
        self.h_hud_style      = node.getAttribute('hero_stat_range')
        self.h_hud_days       = node.getAttribute('hero_stat_days')
        self.h_aggregate_ring = string_to_bool(node.getAttribute('aggregate_hero_ring_game_stats'))
        self.h_aggregate_tour = string_to_bool(node.getAttribute('aggregate_hero_tourney_stats'))
        self.h_agg_bb_mult    = node.getAttribute('hero_aggregation_level_multiplier')


    def __str__(self):
        return "    label = %s\n" % self.label


class Tv:
    def __init__(self, node):
        self.combinedStealFold = string_to_bool(node.getAttribute("combinedStealFold"), default=True)
        self.combined2B3B    = string_to_bool(node.getAttribute("combined2B3B"), default=True)
        self.combinedPostflop  = string_to_bool(node.getAttribute("combinedPostflop"), default=True)

    def __str__(self):
        return ("    combinedStealFold = %s\n    combined2B3B = %s\n    combinedPostflop = %s\n" %
                (self.combinedStealFold, self.combined2B3B, self.combinedPostflop) )

class Config:
    def __init__(self, file = None, dbname = ''):

#    "file" is a path to an xml file with the fpdb/HUD configuration
#    we check the existence of "file" and try to recover if it doesn't exist

#        self.default_config_path = self.get_default_config_path()
        if file is not None: # config file path passed in
            file = os.path.expanduser(file)
            if not os.path.exists(file):
                print "Configuration file %s not found.  Using defaults." % (file)
                sys.stderr.write("Configuration file %s not found.  Using defaults." % (file))
                file = None

        if file is None: file = get_config("HUD_config.xml")

#    Parse even if there was no real config file found and we are using the example
#    If using the example, we'll edit it later
        log.info("Reading configuration file %s" % file)
        print "\nReading configuration file %s\n" % file
        try:
            doc = xml.dom.minidom.parse(file)
        except:
            log.error("Error parsing %s.  See error log file." % (file))
            traceback.print_exc(file=sys.stderr)
            print "press enter to continue"
            sys.stdin.readline()
            sys.exit()

        self.doc = doc
        self.file = file
        self.supported_sites = {}
        self.supported_games = {}
        self.supported_databases = {}        # databaseName --> Database instance
        self.aux_windows = {}
        self.hhcs = {}
        self.popup_windows = {}
        self.db_selected = None    # database the user would like to use
        self.tv = None


#        s_sites = doc.getElementsByTagName("supported_sites")
        for site_node in doc.getElementsByTagName("site"):
            site = Site(node = site_node)
            self.supported_sites[site.site_name] = site

#        s_games = doc.getElementsByTagName("supported_games")
        for game_node in doc.getElementsByTagName("game"):
            game = Game(node = game_node)
            self.supported_games[game.game_name] = game

        # parse databases defined by user in the <supported_databases> section
        # the user may select the actual database to use via commandline or by setting the selected="bool"
        # attribute of the tag. if no database is explicitely selected, we use the first one we come across
#        s_dbs = doc.getElementsByTagName("supported_databases")
        #TODO: do we want to take all <database> tags or all <database> tags contained in <supported_databases>
        #         ..this may break stuff for some users. so leave it unchanged for now untill there is a decission
        for db_node in doc.getElementsByTagName("database"):
            db = Database(node=db_node)
            if db.db_name in self.supported_databases:
                raise ValueError("Database names must be unique")
            if self.db_selected is None or db.db_selected:
                self.db_selected = db.db_name
            self.supported_databases[db.db_name] = db
        #TODO: if the user may passes '' (empty string) as database name via command line, his choice is ignored
        #           ..when we parse the xml we allow for ''. there has to be a decission if to allow '' or not
        if dbname and dbname in self.supported_databases:
            self.db_selected = dbname
        #NOTE: fpdb can not handle the case when no database is defined in xml, so we throw an exception for now
        if self.db_selected is None:
            raise ValueError('There must be at least one database defined')

#     s_dbs = doc.getElementsByTagName("mucked_windows")
        for aw_node in doc.getElementsByTagName("aw"):
            aw = Aux_window(node = aw_node)
            self.aux_windows[aw.name] = aw

#     s_dbs = doc.getElementsByTagName("mucked_windows")
        for hhc_node in doc.getElementsByTagName("hhc"):
            hhc = HHC(node = hhc_node)
            self.hhcs[hhc.site] = hhc

#        s_dbs = doc.getElementsByTagName("popup_windows")
        for pu_node in doc.getElementsByTagName("pu"):
            pu = Popup(node = pu_node)
            self.popup_windows[pu.name] = pu

        for imp_node in doc.getElementsByTagName("import"):
            imp = Import(node = imp_node)
            self.imp = imp

        for hui_node in doc.getElementsByTagName('hud_ui'):
            hui = HudUI(node = hui_node)
            self.ui = hui

        for tv_node in doc.getElementsByTagName("tv"):
            self.tv = Tv(node = tv_node)

        db = self.get_db_parameters()
        if db['db-password'] == 'YOUR MYSQL PASSWORD':
            df_file = self.find_default_conf()
            if df_file is None: # this is bad
                pass
            else:
                df_parms = self.read_default_conf(df_file)
                self.set_db_parameters(db_name = 'fpdb', db_ip = df_parms['db-host'],
                                     db_user = df_parms['db-user'],
                                     db_pass = df_parms['db-password'])
                self.save(file=os.path.join(self.default_config_path, "HUD_config.xml"))

        print ""

    def set_hhArchiveBase(self, path):
        self.imp.node.setAttribute("hhArchiveBase", path)

    def find_default_conf(self):
        if os.name == 'posix':
            config_path = os.path.join(os.path.expanduser("~"), '.fpdb', 'default.conf')
        elif os.name == 'nt':
            config_path = os.path.join(os.environ["APPDATA"], 'fpdb', 'default.conf')
        else: config_path = False

        if config_path and os.path.exists(config_path):
            file = config_path
        else:
            file = None
        return file

    def get_doc(self):
        return self.doc

    def get_site_node(self, site):
        for site_node in self.doc.getElementsByTagName("site"):
            if site_node.getAttribute("site_name") == site:
                return site_node

    def get_aux_node(self, aux):
        for aux_node in self.doc.getElementsByTagName("aw"):
            if aux_node.getAttribute("name") == aux:
                return aux_node

    def get_db_node(self, db_name):
        for db_node in self.doc.getElementsByTagName("database"):
            if db_node.getAttribute("db_name") == db_name:
                return db_node
        return None

    def get_layout_node(self, site_node, layout):
        for layout_node in site_node.getElementsByTagName("layout"):
            if layout_node.getAttribute("max") is None:
                return None
            if int( layout_node.getAttribute("max") ) == int( layout ):
                return layout_node

    def get_location_node(self, layout_node, seat):
        if seat == "common":
            for location_node in layout_node.getElementsByTagName("location"):
                if location_node.hasAttribute("common"):
                    return location_node
        else:
            for location_node in layout_node.getElementsByTagName("location"):
                if int( location_node.getAttribute("seat") ) == int( seat ):
                    return location_node

    def save(self, file = None):
        if file is None:
            file = self.file
        shutil.move(file, file+".backup")
        with open(file, 'w') as f:
            self.doc.writexml(f)

    def edit_layout(self, site_name, max, width = None, height = None,
                    fav_seat = None, locations = None):
        site_node   = self.get_site_node(site_name)
        layout_node = self.get_layout_node(site_node, max)
        # TODO: how do we support inserting new layouts?
        if layout_node is None:
            return
        for i in range(1, max + 1):
            location_node = self.get_location_node(layout_node, i)
            location_node.setAttribute("x", str( locations[i-1][0] ))
            location_node.setAttribute("y", str( locations[i-1][1] ))
            self.supported_sites[site_name].layout[max].location[i] = ( locations[i-1][0], locations[i-1][1] )

    def edit_aux_layout(self, aux_name, max, width = None, height = None, locations = None):
        aux_node   = self.get_aux_node(aux_name)
        layout_node = self.get_layout_node(aux_node, max)
        if layout_node is None:
            print "aux node not found"
            return
        print "editing locations =", locations
        for (i, pos) in locations.iteritems():
            location_node = self.get_location_node(layout_node, i)
            location_node.setAttribute("x", str( locations[i][0] ))
            location_node.setAttribute("y", str( locations[i][1] ))
            if i == "common":
                self.aux_windows[aux_name].layout[max].common = ( locations[i][0], locations[i][1] )
            else:
                self.aux_windows[aux_name].layout[max].location[i] = ( locations[i][0], locations[i][1] )

    #NOTE: we got a nice Database class, so why map it again here?
    #            user input validation should be done when initializing the Database class. this allows to give appropriate feddback when something goes wrong
    #            try ..except is evil here. it swallows all kinds of errors. dont do this
    #            naming database types 2, 3, 4 on the fly is no good idea. i see this all over the code. better use some globally defined consts (see DATABASE_TYPE_*)
    #            i would like to drop this method entirely and replace it by get_selected_database() or better get_active_database(), returning one of our Database instances
    #            thus we can drop self.db_selected (holding database name) entirely and replace it with self._active_database = Database, avoiding to define the same
    #            thing multiple times
    def get_db_parameters(self):
        db = {}
        name = self.db_selected
        # TODO: What's up with all the exception handling here?!
        try:    db['db-databaseName'] = name
        except: pass

        try:    db['db-host'] = self.supported_databases[name].db_ip
        except: pass

        try:    db['db-user'] = self.supported_databases[name].db_user
        except: pass

        try:    db['db-password'] = self.supported_databases[name].db_pass
        except: pass

        try:    db['db-server'] = self.supported_databases[name].db_server
        except: pass

        if self.supported_databases[name].db_server== DATABASE_TYPE_MYSQL:
            db['db-backend'] = 2
        elif self.supported_databases[name].db_server== DATABASE_TYPE_POSTGRESQL:
            db['db-backend'] = 3
        elif self.supported_databases[name].db_server== DATABASE_TYPE_SQLITE:
            db['db-backend'] = 4
        else:
            raise ValueError('Unsupported database backend: %s' % self.supported_databases[name].db_server)
        return db

    def set_db_parameters(self, db_name = 'fpdb', db_ip = None, db_user = None,
                        db_pass = None, db_server = None):
        db_node = self.get_db_node(db_name)
        if db_node != None:
            if db_ip     is not None: db_node.setAttribute("db_ip", db_ip)
            if db_user   is not None: db_node.setAttribute("db_user", db_user)
            if db_pass   is not None: db_node.setAttribute("db_pass", db_pass)
            if db_server is not None: db_node.setAttribute("db_server", db_server)
            if db_type   is not None: db_node.setAttribute("db_type", db_type)
        if self.supported_databases.has_key(db_name):
            if db_ip     is not None: self.supported_databases[db_name].dp_ip     = db_ip
            if db_user   is not None: self.supported_databases[db_name].dp_user   = db_user
            if db_pass   is not None: self.supported_databases[db_name].dp_pass   = db_pass
            if db_server is not None: self.supported_databases[db_name].dp_server = db_server
            if db_type   is not None: self.supported_databases[db_name].dp_type   = db_type
        return

    def getDefaultSite(self):
        "Returns first enabled site or None"
        for site_name,site in self.supported_sites.iteritems():
            if site.enabled:
                return site_name
        return None

    def get_tv_parameters(self):
        if self.tv is not None:
            return {
                    'combinedStealFold': self.tv.combinedStealFold,
                    'combined2B3B': self.tv.combined2B3B,
                    'combinedPostflop': self.tv.combinedPostflop
                    }
        return {}

    # Allow to change the menu appearance
    def get_hud_ui_parameters(self):
        hui = {}

        default_text = 'FPDB Menu - Right click\nLeft-Drag to Move'
        try:
            hui['label'] = self.ui.label
            if self.ui.label == '':    # Empty menu label is a big no-no
                hui['label'] = default_text
        except:
            hui['label'] = default_text

        try:    hui['hud_style']        = self.ui.hud_style
        except: hui['hud_style']        = 'A'  # default is show stats for All-time, also S(session) and T(ime)

        try:    hui['hud_days']        = int(self.ui.hud_days)
        except: hui['hud_days']        = 90

        try:    hui['aggregate_ring']   = self.ui.aggregate_ring
        except: hui['aggregate_ring']   = False

        try:    hui['aggregate_tour']   = self.ui.aggregate_tour
        except: hui['aggregate_tour']   = True

        try:    hui['agg_bb_mult']    = self.ui.agg_bb_mult
        except: hui['agg_bb_mult']    = 1

        try:    hui['seats_style']    = self.ui.seats_style
        except: hui['seats_style']    = 'A'  # A / C / E, use A(ll) / C(ustom) / E(xact) seat numbers

        try:    hui['seats_cust_nums']    = self.ui.seats_cust_nums
        except: hui['seats_cust_nums']    = ['n/a', 'n/a', (2,2), (3,4), (3,5), (4,6), (5,7), (6,8), (7,9), (8,10), (8,10)]

        # Hero specific

        try:    hui['h_hud_style']    = self.ui.h_hud_style
        except: hui['h_hud_style']    = 'S'

        try:    hui['h_hud_days']     = int(self.ui.h_hud_days)
        except: hui['h_hud_days']     = 30

        try:    hui['h_aggregate_ring'] = self.ui.h_aggregate_ring
        except: hui['h_aggregate_ring'] = False

        try:    hui['h_aggregate_tour'] = self.ui.h_aggregate_tour
        except: hui['h_aggregate_tour'] = True

        try:    hui['h_agg_bb_mult']    = self.ui.h_agg_bb_mult
        except: hui['h_agg_bb_mult']    = 1

        try:    hui['h_seats_style']    = self.ui.h_seats_style
        except: hui['h_seats_style']    = 'A'  # A / C / E, use A(ll) / C(ustom) / E(xact) seat numbers

        try:    hui['h_seats_cust_nums']    = self.ui.h_seats_cust_nums
        except: hui['h_seats_cust_nums']    = ['n/a', 'n/a', (2,2), (3,4), (3,5), (4,6), (5,7), (6,8), (7,9), (8,10), (8,10)]

        return hui


    def get_import_parameters(self):
        imp = {}
        try:    imp['callFpdbHud']     = self.imp.callFpdbHud
        except:  imp['callFpdbHud']     = True

        try:    imp['interval']        = self.imp.interval
        except:  imp['interval']        = 10

        try:    imp['hhArchiveBase']    = self.imp.hhArchiveBase
        except:  imp['hhArchiveBase']    = "~/.fpdb/HandHistories/"

        try:    imp['saveActions']     = self.imp.saveActions
        except:  imp['saveActions']     = True

        try:    imp['fastStoreHudCache'] = self.imp.fastStoreHudCache
        except:  imp['fastStoreHudCache'] = True
        return imp

    def get_default_paths(self, site = None):
        if site is None: site = self.getDefaultSite()
        paths = {}
        try:
            path = os.path.expanduser(self.supported_sites[site].HH_path)
            assert(os.path.isdir(path) or os.path.isfile(path)) # maybe it should try another site?
            paths['hud-defaultPath'] = paths['bulkImport-defaultPath'] = path
        except AssertionError:
            paths['hud-defaultPath'] = paths['bulkImport-defaultPath'] = "** ERROR DEFAULT PATH IN CONFIG DOES NOT EXIST **"
        return paths

    def get_frames(self, site = "PokerStars"):
        if site not in self.supported_sites: return False
        return self.supported_sites[site].use_frames == True

    def get_default_colors(self, site = "PokerStars"):
        colors = {}
        if site not in self.supported_sites or self.supported_sites[site].hudopacity == "":
            colors['hudopacity'] = 0.90
        else:
            colors['hudopacity'] = float(self.supported_sites[site].hudopacity)
        if site not in self.supported_sites or self.supported_sites[site].hudbgcolor == "":
            colors['hudbgcolor'] = "#FFFFFF"
        else:
            colors['hudbgcolor'] = self.supported_sites[site].hudbgcolor
        if site not in self.supported_sites or self.supported_sites[site].hudfgcolor == "":
            colors['hudfgcolor'] = "#000000"
        else:
            colors['hudfgcolor'] = self.supported_sites[site].hudfgcolor
        return colors

    def get_default_font(self, site='PokerStars'):
        font = "Sans"
        font_size = "8"
        site = self.supported_sites.get(site, None)
        if site is not None:
            if site.font:
                font = site.font
            if site.font_size:
                font_size = site.font_size
        return font, font_size

    def get_locations(self, site_name="PokerStars", max=8):
        site = self.supported_sites.get(site_name, None)
        if site is not None:
            location = site.layout.get(max, None)
            if location is not None:
                return location.location
        return (
                    (  0,   0), (684,  61), (689, 239), (692, 346),
                    (586, 393), (421, 440), (267, 440), (  0, 361),
                    (  0, 280), (121, 280), ( 46,  30)
                )

    def get_aux_locations(self, aux = "mucked", max = "9"):

        try:
            locations = self.aux_windows[aux].layout[max].location
        except:
            locations = ( (  0,   0), (684,  61), (689, 239), (692, 346),
                        (586, 393), (421, 440), (267, 440), (  0, 361),
                        (  0, 280), (121, 280), ( 46,  30) )
        return locations

    def get_supported_sites(self, all=False):
        """Returns the list of supported sites."""
        if all:
            return self.supported_sites.keys()
        else:
            return [site_name for (site_name, site) in self.supported_sites.items() if site.enabled]

    def get_site_parameters(self, site):
        """Returns a dict of the site parameters for the specified site"""
        parms = {}
        parms["converter"]    = self.supported_sites[site].converter
        parms["decoder"]    = self.supported_sites[site].decoder
        parms["hudbgcolor"]   = self.supported_sites[site].hudbgcolor
        parms["hudfgcolor"]   = self.supported_sites[site].hudfgcolor
        parms["hudopacity"]   = self.supported_sites[site].hudopacity
        parms["screen_name"]  = self.supported_sites[site].screen_name
        parms["site_path"]    = self.supported_sites[site].site_path
        parms["table_finder"] = self.supported_sites[site].table_finder
        parms["HH_path"]    = self.supported_sites[site].HH_path
        parms["site_name"]    = self.supported_sites[site].site_name
        parms["aux_window"]   = self.supported_sites[site].aux_window
        parms["font"]        = self.supported_sites[site].font
        parms["font_size"]    = self.supported_sites[site].font_size
        parms["enabled"]    = self.supported_sites[site].enabled
        parms["xpad"]        = self.supported_sites[site].xpad
        parms["ypad"]        = self.supported_sites[site].ypad
        return parms

    def set_site_parameters(self, site_name, converter = None, decoder = None,
                            hudbgcolor = None, hudfgcolor = None,
                            hudopacity = None, screen_name = None,
                            site_path = None, table_finder = None,
                            HH_path = None, enabled = None,
                            font = None, font_size = None):
        """Sets the specified site parameters for the specified site."""
        site_node = self.get_site_node(site_name)
        if db_node is not None:
            if converter      is not None: site_node.setAttribute("converter", converter)
            if decoder        is not None: site_node.setAttribute("decoder", decoder)
            if hudbgcolor     is not None: site_node.setAttribute("hudbgcolor", hudbgcolor)
            if hudfgcolor     is not None: site_node.setAttribute("hudfgcolor", hudfgcolor)
            if hudopacity     is not None: site_node.setAttribute("hudopacity", hudopacity)
            if screen_name    is not None: site_node.setAttribute("screen_name", screen_name)
            if site_path      is not None: site_node.setAttribute("site_path", site_path)
            if table_finder   is not None: site_node.setAttribute("table_finder", table_finder)
            if HH_path        is not None: site_node.setAttribute("HH_path", HH_path)
            if enabled        is not None: site_node.setAttribute("enabled", enabled)
            if font           is not None: site_node.setAttribute("font", font)
            if font_size      is not None: site_node.setAttribute("font_size", font_size)
        return

    def get_aux_windows(self):
        """Gets the list of mucked window formats in the configuration."""
        return self.aux_windows.keys()

    def get_aux_parameters(self, name):
        """Gets a dict of mucked window parameters from the named mw."""
        param = {}
        if self.aux_windows.has_key(name):
            for key in dir(self.aux_windows[name]):
                if key.startswith('__'): continue
                value = getattr(self.aux_windows[name], key)
                if callable(value): continue
                param[key] = value

            return param
        return None

    def get_game_parameters(self, name):
        """Get the configuration parameters for the named game."""
        param = {}
        if self.supported_games.has_key(name):
            param['game_name'] = self.supported_games[name].game_name
            param['rows']    = self.supported_games[name].rows
            param['cols']    = self.supported_games[name].cols
            param['xpad']    = self.supported_games[name].xpad
            param['ypad']    = self.supported_games[name].ypad
            param['aux']     = self.supported_games[name].aux
        return param

    def get_supported_games(self):
        """Get the list of supported games."""
        sg = []
        for game in c.supported_games.keys():
            sg.append(c.supported_games[game].game_name)
        return sg

    def execution_path(self, filename):
        """Join the fpdb path to filename."""
        return os.path.join(os.path.dirname(inspect.getfile(sys._getframe(0))), filename)

if __name__== "__main__":
    c = Config()

    print "\n----------- SUPPORTED SITES -----------"
    for s in c.supported_sites.keys():
        print c.supported_sites[s]
    print "----------- END SUPPORTED SITES -----------"


    print "\n----------- SUPPORTED GAMES -----------"
    for game in c.supported_games.keys():
        print c.supported_games[game]
    print "----------- END SUPPORTED GAMES -----------"


    print "\n----------- SUPPORTED DATABASES -----------"
    for db in c.supported_databases.keys():
        print c.supported_databases[db]
    print "----------- END SUPPORTED DATABASES -----------"

    print "\n----------- AUX WINDOW FORMATS -----------"
    for w in c.aux_windows.keys():
        print c.aux_windows[w]
    print "----------- END AUX WINDOW FORMATS -----------"

    print "\n----------- HAND HISTORY CONVERTERS -----------"
    for w in c.hhcs.keys():
        print c.hhcs[w]
    print "----------- END HAND HISTORY CONVERTERS -----------"

    print "\n----------- POPUP WINDOW FORMATS -----------"
    for w in c.popup_windows.keys():
        print c.popup_windows[w]
    print "----------- END POPUP WINDOW FORMATS -----------"

    print "\n----------- IMPORT -----------"
    print c.imp
    print "----------- END IMPORT -----------"

    print "\n----------- TABLE VIEW -----------"
#    print c.tv
    print "----------- END TABLE VIEW -----------"

    c.edit_layout("PokerStars", 6, locations=( (1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 6) ))
    c.save(file="testout.xml")

    print "db    = ", c.get_db_parameters()
#    print "tv    = ", c.get_tv_parameters()
#    print "imp    = ", c.get_import_parameters()
    print "paths  = ", c.get_default_paths("PokerStars")
    print "colors = ", c.get_default_colors("PokerStars")
    print "locs   = ", c.get_locations("PokerStars", 8)
    for mw in c.get_aux_windows():
        print c.get_aux_parameters(mw)

    print "mucked locations =", c.get_aux_locations('mucked', 9)
#    c.edit_aux_layout('mucked', 9, locations = [(487, 113), (555, 469), (572, 276), (522, 345),
#                                                (333, 354), (217, 341), (150, 273), (150, 169), (230, 115)])
#    print "mucked locations =", c.get_aux_locations('mucked', 9)

    for site in c.supported_sites.keys():
        print "site = ", site,
        print c.get_site_parameters(site)
        print c.get_default_font(site)

    for game in c.get_supported_games():
        print c.get_game_parameters(game)

    for hud_param, value in c.get_hud_ui_parameters().iteritems():
        print "hud param %s = %s" % (hud_param, value)

    print "start up path = ", c.execution_path("")

    try:
        from xml.dom.ext import PrettyPrint
        for site_node in c.doc.getElementsByTagName("site"):
            PrettyPrint(site_node, stream=sys.stdout, encoding="utf-8")
    except:
        print "xml.dom.ext needs PyXML to be installed!"
