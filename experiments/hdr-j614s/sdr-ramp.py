#!/usr/bin/env python3
"""Temporary fullscreen neutral SDR patches for scanout inspection."""
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,GLib,Gdk
VALUES=[16,32,64,96,128,160,192,224]
w=Gtk.Window(title='m4rch HDR SDR ramp');w.fullscreen();w.set_keep_above(True)
b=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL);w.add(b)
css=Gtk.CssProvider();css.load_from_data(''.join(f'#gray{i} {{ background-color: rgb({x},{x},{x}); }}\n' for i,x in enumerate(VALUES)).encode())
Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
for i in range(len(VALUES)):
 e=Gtk.EventBox();e.set_name(f'gray{i}');e.set_hexpand(True);e.set_vexpand(True);b.pack_start(e,True,True,0)
w.connect('destroy',Gtk.main_quit);w.connect('key-press-event',lambda *_: Gtk.main_quit());w.show_all();GLib.timeout_add_seconds(90,lambda:(Gtk.main_quit(),False)[1]);Gtk.main()
