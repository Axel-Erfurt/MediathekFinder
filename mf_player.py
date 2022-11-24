#!/usr/bin/python3

import gi
gi.require_version('WebKit2', '4.0')
gi.require_version('Gtk', '3.0')
import sys

from gi.repository import Gtk, WebKit2 as WebKit

class Window(Gtk.ApplicationWindow):
    def __init__(self, dl_file):
        super(Gtk.ApplicationWindow, self).__init__() 
        
        self.url = ""
        self.dl_file = dl_file
        self.view = WebKit.WebView()
        self.view.set_size_request(640, 360)
        settings = self.view.get_settings()
        settings.set_enable_mediasource(True)
        settings.set_allow_file_access_from_file_urls(True)
        settings.set_enable_webaudio(True)
        settings.set_enable_webgl(True)
        settings.set_media_playback_allows_inline(True)

        vbox = Gtk.VBox()
        vbox.pack_start(self.view, True, True, 0)

        self.set_size_request(640, 360)
        self.connect("destroy", self.handle_close)
        self.view.connect("decide-policy", self.handle_download)
        self.set_title("Viewer")
        icontheme = Gtk.IconTheme.get_default()
        icon = icontheme.load_icon("browser", 32, 0)
        self.set_icon(icon)
        self.add(vbox)
        self.show_all()
        
        
    def handle_close(self, *args):
        self.view.load_uri("")
        
    def handle_download(self, *args):
        print(f"DL-File: {self.dl_file}")