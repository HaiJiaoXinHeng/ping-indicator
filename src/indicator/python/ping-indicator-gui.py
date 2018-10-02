#!/usr/bin/env python
# coding: utf-8

import gtk
import gtk.glade
import appindicator
import time
try:
    import Image
except ImportError:
    from PIL import Image
import os.path
import subprocess
import sys
import math

import data_exch
import conf

sys.path.append('/usr/share/ping-indicator/python/')


LOGO = os.path.expanduser("/usr/share/ping-indicator/imgs/over.png")
UPDATE_TIMEOUT = 1000  # ms

# MAX_PING = 100 # ms

BIN_DIR = os.path.expanduser("/usr/bin/")
UI_DIR = os.path.expanduser("/usr/share/ping-indicator/ui/")

IMAGES_DIR = os.path.expanduser("/usr/share/ping-indicator/imgs/")
IMAGES_EXT = '.png'
IMAGES_THEME = 'dark'
IMAGES_INDICATOR_FORMAT = "{}ping-indicator-{}-status-{}.png"
TMP_DIR = os.path.expanduser("/tmp/")

MENU_HOST_FORMAT = "{}  : {} ms"
MENU_HOST_FORMAT_NONE = "{}  : -- n/a --"
MENU_HOST_SEPARATOR = "  : "


class IconCache:
    def __init__(self):
        self.images = dict()
        for i in range(0, 11):
            img = Image.open(self._build_filename(i))
            self.images[i] = img
        self.images['none'] = Image.open(self._build_filename('none'))
        self.images['over'] = Image.open(self._build_filename('over'))

    def _build_filename(self, name):
        fn = IMAGES_DIR
        if (name == 'over') or (name == 'none'):
            fn += name + IMAGES_EXT
        else:
            fn += 'dark_' + str(name) + IMAGES_EXT
        return fn

    def image_by_delay(self, delay):
        if delay > 0:
            ind = int(min(delay / 10, math.log(delay + 1.643, 1.643) - 1.643))
            if ind > 10:
                ind = 'over'
        else:
            ind = 'none'

        try:
            return self.images[ind]
        except:
            return False


class AppIndicator(object):
    def __init__(self):
        path = os.path.expanduser('~')
        # print path;
        p, user = os.path.split(path)
        # print "user = {}\n".format(user);
        self.needToRebuildMenu = True
        self.user = user
        self.conf = conf.Conf(self.user)
        self.daemon = None
        self.start_deamon()

        self.icons = IconCache()
        # self.ind = appindicator.Indicator("ping-indicator-applet", LOGO, appindicator.CATEGORY_APPLICATION_STATUS)
        self.ind = appindicator.Indicator("ping-indicator-applet", LOGO, appindicator.CATEGORY_COMMUNICATIONS)
        self.ind.set_status(appindicator.STATUS_ACTIVE)
        self.menu = gtk.Menu()
        sep = gtk.SeparatorMenuItem()
        pref_item = gtk.MenuItem()
        pref_item.add(gtk.Label("Preferences"))
        pref_item.connect("activate", self.show_prefs)
        item = gtk.MenuItem()
        item.add(gtk.Label("exit"))
        item.connect("activate", self.exit)

        self.menu.append(sep)
        self.menu.append(pref_item)
        self.menu.append(item)
        self.menu.show_all()
        self.ind.set_menu(self.menu)
        self.gtkTimer = gtk.timeout_add(UPDATE_TIMEOUT, self.update)

    def start_deamon(self):
        self.daemon = subprocess.Popen([os.path.expanduser(BIN_DIR + "ping-indicator-daemon-wrapper"), self.user])

    def show_prefs(self, obj):
        self.pref_tree = gtk.glade.XML(UI_DIR + "conf.glade", "dialog1")
        window = self.pref_tree.get_widget("dialog1")
        # window.connect("delete_event", gtk.main_quit)
        c = conf.Conf(self.user)
        data_file = data_exch.Data_Exch(self.user)
        data = data_file.read()
        text = ""
        for host, dalay in data:
            text += host + "\n"

        tw = self.pref_tree.get_widget("hosts__textview")
        buf = tw.get_buffer()
        buf.set_text(text)

        scale = self.pref_tree.get_widget("interval__hscale")
        scale.set_value(c.refreshInterval)

        self.pref_tree.get_widget("cancel__button").connect("clicked", self.close_prefs)
        self.pref_tree.get_widget("ok__button").connect("clicked", self.apply_prefs)
        window.show_all()

    def close_prefs(self, obj):
        window = self.pref_tree.get_widget("dialog1")
        window.destroy()

    def apply_prefs(self, obj):
        buf = self.pref_tree.get_widget("hosts__textview").get_buffer()
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter())
        scale = self.pref_tree.get_widget("interval__hscale")

        c = conf.Conf(self.user)
        c.set_servers(text)
        c.refreshInterval = int(scale.get_value())
        c.write()

        self.restart_timer(c.refreshInterval)
        self.restart_deamon()

        self.close_prefs(obj)
        self.needToRebuildMenu = True

    def restart_timer(self, timeout):
        gtk.timeout_remove(self.gtkTimer)
        self.gtkTimer = gtk.timeout_add(timeout, self.update)

    def restart_deamon(self):
        self.daemon.terminate()
        self.start_deamon()

    def exit(self, obj):
        self.daemon.terminate()
        gtk.main_quit()

    def update(self):
        data_file = data_exch.Data_Exch(self.user)
        data = data_file.read()
        if data:
            count = len(data)
            img = Image.new("RGBA", (count * 8, 22))
            i = 0
            for host, delay in data:
                icon = self.icons.image_by_delay(delay)
                img.paste(icon, (i * 8, 1))
                i += 1

            suffix = int(time.time()) % 4
            indicator_fn = IMAGES_INDICATOR_FORMAT.format(TMP_DIR, self.user, suffix)
            img.save(indicator_fn)
            self.ind.set_icon(indicator_fn)
            self.update_menu(data)
        return True

    def build_menu(self, data):
        i = 0
        for host, delay in data:
            item = gtk.MenuItem()
            if delay > 0:
                item.add(gtk.Label(MENU_HOST_FORMAT.format(host, round(delay, 1))))
            else:
                item.add(gtk.Label(MENU_HOST_FORMAT_NONE.format(host)))
            self.menu.insert(item, i)
            i += 1

    def clear_menu(self):
        items = self.menu.get_children()
        for item in items:
            if isinstance(item, gtk.SeparatorMenuItem):
                break
            else:
                self.menu.remove(item)

    def update_menu(self, data):
        # first_one = items[0]
        # first_host, first_delay = data[0]
        if self.needToRebuildMenu:
            # or first_one.get_label().split(MENU_HOST_SEPARATOR)[0] != first_host:
            # if not isinstance(first_one, gtk.SeparatorMenuItem):
            self.clear_menu()
            self.build_menu(data)
            self.menu.show_all()
            self.needToRebuildMenu = False
        else:
            items = self.menu.get_children()
            i = 0
            for host, responseTime in data:
                item = items[i]
                if responseTime > 0:
                    item.set_label(MENU_HOST_FORMAT.format(host, round(responseTime, 1)))
                else:
                    item.set_label(MENU_HOST_FORMAT_NONE.format(host))
                i += 1

        self.ind.set_menu(self.menu)

indicator = AppIndicator()
gtk.main()
