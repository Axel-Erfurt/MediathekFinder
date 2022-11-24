#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Mediathek Finder
=====
© 2022 by Axel Schneider
https://github.com/Axel-Erfurt
"""
import gi
gi.require_versions({'Gtk': '3.0', 'Gdk': '3.0'})
gi.require_version('WebKit2', '4.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, GObject, GLib
import requests
import xml.etree.ElementTree as et
import threading
import datetime
import warnings
import mf_player
import sys
import urllib.parse
from os import path
warnings.filterwarnings("ignore")

CSS = """
headerbar entry {
    margin-top: 10px;
    margin-bottom: 10px;
    background: #ddd;
}
headerbar {
    min-height: 24px;
    padding-left: 2px;
    padding-right: 2px;
    margin: 0px;
    padding: 10px;
    background: #ddd;
    border: 0px;
}
headerbar .title {
    font-size: 10pt;
    color: #5b5b5b;
}
headerbar .subtitle {
    font-size: 8pt;
    color: #5b5b5b;
}
#volume_label {
    color: #555753;
    font-size: 8pt;
}
#desc_label {
    color: #1f3c5d;
    font-size: 8pt;
    font-weight: bold;
    padding-top: 6px;
    padding-bottom: 4px;
}
window, iconview {
    background: #e9e9e9;
    color: #413c0f;
    font-size: 9pt;
}
iconview:selected {
    background: lightsteelblue;
    color: #2e3436;
    }
slider {
    background: lightsteelblue;
}
#dl_btn:hover, #play_btn:hover {
    background: lightsteelblue;
    color: #1a73e8;
}
progressbar {
    margin-left: 10px;
    margin-right: 10px;
    color: #555753;
}
progressbar progress {
    background: lightsteelblue;
}
scrolledwindow {
    margin-bottom: 10px;
}
"""

wildcards = """
Wildcards:

Sender        !
Titel        +
Thema        #
Beschreibung    *
<x        kleiner als x Minuten
>x        grösser als x Minuten

Beispiel: Wilsberg im ZDF mit über 70 Minuten Länge:

!ZDF +Wilsberg >70
"""
threads = []

license = """MIT License

Copyright (c) 2022 Axel Schneider

Jedem, der eine Kopie dieser Software und der zugehörigen 
Dokumentationsdateien (die „Software“) erhält, 
wird hiermit kostenlos die Erlaubnis erteilt, 
ohne Einschränkung mit der Software zu handeln, 
einschließlich und ohne Einschränkung der Rechte zur Nutzung, 
zum Kopieren, Ändern, Zusammenführen, 
Veröffentlichen, Verteilen, Unterlizenzieren 
und/oder Verkaufen von Kopien der Software, 
und Personen, denen die Software zur Verfügung gestellt wird, 
dies unter den folgenden Bedingungen zu gestatten:

Der obige Urheberrechtshinweis und dieser Genehmigungshinweis müssen 
in allen Kopien oder wesentlichen Teilen der Software enthalten sein.

DIE SOFTWARE WIRD OHNE MÄNGELGEWÄHR UND OHNE JEGLICHE AUSDRÜCKLICHE 
ODER STILLSCHWEIGENDE GEWÄHRLEISTUNG, 
EINSCHLIEẞLICH, ABER NICHT BESCHRÄNKT AUF DIE GEWÄHRLEISTUNG 
DER MARKTGÄNGIGKEIT, DER EIGNUNG FÜR EINEN BESTIMMTEN ZWECK 
UND DER NICHTVERLETZUNG VON RECHTEN DRITTER, ZUR VERFÜGUNG GESTELLT. 
DIE AUTOREN ODER URHEBERRECHTSINHABER SIND IN KEINEM FALL HAFTBAR FÜR ANSPRÜCHE, 
SCHÄDEN ODER ANDERE VERPFLICHTUNGEN, OB IN EINER VERTRAGS- ODER HAFTUNGSKLAGE, 
EINER UNERLAUBTEN HANDLUNG ODER ANDERWEITIG, 
DIE SICH AUS ODER IN VERBINDUNG MIT DER SOFTWARE ODER DER NUTZUNG 
ODER ANDEREN GESCHÄFTEN MIT DER SOFTWARE ERGEBEN. 
"""

class Window(Gtk.ApplicationWindow):
    def __init__(self):
        super(Gtk.ApplicationWindow, self).__init__()
        
        GObject.threads_init()
        self.desc_list = []
        self.duration_list = []
        self.category_list = []
        self.current_index = 0
        self.dl_file = ""
        med_icon = f"{path.dirname(sys.argv[0])}/icon.png"
        self.mediathek_icon = GdkPixbuf.Pixbuf.new_from_file_at_scale(med_icon, 32, 32, True)
        GLib.set_application_name("MediathekFinder")
        # style
        provider = Gtk.CssProvider()
        provider.load_from_data(bytes(CSS.encode()))
        style = self.get_style_context()
        screen = Gdk.Screen.get_default()
        priority = Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        style.add_provider_for_screen(screen, provider, priority)
        
        self.set_title('Mediathek Finder')
        self.set_icon(self.mediathek_icon)
        self.connect("destroy", self.handle_close)
        self.old_tag = ""

        self.header = Gtk.HeaderBar()
        self.header.set_title('Mediathek Finder')
        self.header.set_subtitle("Mediathek durchsuchen")
        self.header.set_show_close_button(True)
        self.set_titlebar(self.header)
        
        self.clip = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        
        # dl
        image = Gtk.Image(stock=Gtk.STOCK_SAVE)
        self.dl_btn = Gtk.Button(image=image, tooltip_text="Download") 
        self.dl_btn.set_name("dl_btn")
        self.dl_btn.set_relief(2)
        self.dl_btn.connect('clicked', self.doDownload)
        
        #play
        image = Gtk.Image(stock=Gtk.STOCK_MEDIA_PLAY)
        self.play_btn = Gtk.Button(image=image, tooltip_text="Wiedergabe") 
        self.play_btn.set_name("play_btn")
        self.play_btn.set_relief(2)
        self.play_btn.connect('clicked', self.play_from_button)
        
        self.header.pack_start(self.dl_btn)
        self.header.pack_start(self.play_btn)
        
        #info
        image = Gtk.Image(stock=Gtk.STOCK_INFO)
        self.info_btn = Gtk.Button(image=image, tooltip_text="Info zu Wilcards") 
        self.info_btn.set_name("info_btn")
        self.info_btn.set_relief(2)
        self.info_btn.connect('clicked', self.show_info)
        
        self.header.pack_end(self.info_btn)
        
        self.search_entry = Gtk.SearchEntry(
                            width_chars=40, 
                            text="!zdf +krimi >40", 
                            placeholder_text = "find ...",
                            tooltip_text = wildcards)
        self.search_entry.connect("activate", self.find_movies)

        self.header.pack_end(self.search_entry)

        self.model = Gtk.ListStore(object)
        self.model.set_column_types((str, str, GdkPixbuf.Pixbuf))
        
        self.icon_view = Gtk.IconView()
        self.icon_view.set_model(self.model)
        self.icon_view.set_item_width(-1)
        self.icon_view.set_text_column(0)
        self.icon_view.set_pixbuf_column(2)
        self.icon_view.set_activate_on_single_click(True)
        self.icon_view.connect('selection-changed', self.copy_url)

        scroll = Gtk.ScrolledWindow()
        scroll.add(self.icon_view)
        
        self.info_label = Gtk.Label(label="Info")
        self.info_label.set_line_wrap(True)
        self.info_label.set_line_wrap_mode(0)
        self.info_label.set_max_width_chars(50)
        self.info_label.set_name("desc_label")
        
        self.progressbar = Gtk.ProgressBar(show_text=True)
        
        vbox = Gtk.VBox()
        self.add(vbox)
        
        vbox.pack_start(scroll, True, True, 0)
        vbox.pack_start(self.info_label, False, False, 5)
        vbox.pack_start(self.progressbar, False, False, 5)

        self.set_size_request(750, 600)
        self.show_all()
        self.dl_btn.set_visible(False)
        self.progressbar.set_visible(False)
        self.search_entry.grab_focus()
        
    def show_info(self, *args):
        dialog = Gtk.AboutDialog()
        dialog.set_title("Info")
        dialog.set_name("MediathekFinder")
        dialog.set_version("1.0")
        dialog.set_comments(f"Mediatheken durchsuchen und herunterladen\n{wildcards}")
        dialog.set_website("https://github.com/Axel-Erfurt/MediathekFinder")
        dialog.set_website_label("MediathekFinder Github")
        dialog.set_authors(["Axel Schneider"])
        dialog.set_license(license)
        dialog.set_logo(GdkPixbuf.Pixbuf.new_from_file_at_size("icon.png", 64, 64))
        dialog.connect('response', lambda dialog, data: dialog.destroy())
        dialog.show_all()
        
    def on_save_file(self, *args):
        if len(self.icon_view.get_selected_items()) > 0:
            videos = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_VIDEOS)
            ind = self.icon_view.get_selected_items()[0]
            name = self.model[ind][0].replace('"', '')
            dlg = Gtk.FileChooserDialog(title="Speichern", parent=None, action = 1)
            dlg.add_buttons("Abbrechen", Gtk.ResponseType.CANCEL,
                     "Speichern", Gtk.ResponseType.OK)
                     
            filter = Gtk.FileFilter()
            filter.set_name("Videos")
            filter.add_pattern("*.mp4")
            dlg.add_filter(filter)
            dlg.set_current_folder(videos)
            dlg.set_current_name(f"{name}.mp4")
            response = dlg.run()
            if response == Gtk.ResponseType.OK:
                if dlg.get_filename():
                    self.dl_file = dlg.get_filename()
            else:
                self.dl_file = ""
            dlg.destroy()
        
    def doDownload(self, *args):
        if len(self.icon_view.get_selected_items()) > 0:
            # file selector
            self.on_save_file()
            self.progressbar.set_visible(True)
            t = threading.Thread(target=self.download_movie_new)
            t.daemon = True
            t.start()
            threads.append(t)
            
    def update_progess(self, i):
        self.header.set_subtitle(f"Download: {i}%")
        self.progressbar.set_fraction(i/100)
###################################################################
    def download_movie_new(self, *args):
        self.info_label.set_text("Download gestartet")
        self.progressbar.set_fraction(0)
        ind = self.icon_view.get_selected_items()[0]
        url = self.model[ind][1]
        filename = self.dl_file
        if filename:
            print(f"speichern als {filename}")
            with open(filename, 'wb') as f:
                response = requests.get(url, stream=True)
                total = response.headers.get('content-length')

                if total is None:
                    f.write(response.content)
                else:
                    downloaded = 0
                    total = int(total)
                    for data in response.iter_content(chunk_size=max(int(total/1000), 1024*1024)):
                        downloaded += len(data)
                        f.write(data)
                        done = int(100*downloaded/total)
                        sys.stdout.write(f"Download: {done}%")
                        GLib.idle_add(self.update_progess, done)
                        #sys.stdout.flush()
                    sys.stdout.write('\nDownload beendet!')
                    self.info_label.set_text("Download beendet!")
                    self.progressbar.set_visible(False)
###################################################################
               
    def copy_url(self, *args):
        if len(self.icon_view.get_selected_items()) > 0:
            ind = self.icon_view.get_selected_items()[0]
            index = int(str(self.icon_view.get_selected_items()[0]))
            if index != self.current_index:
                url = self.model[ind][1]
                self.clip.set_text(url, -1)
                print(url)
                seconds = self.duration_list[index]
                category = self.category_list[index]
                dur = str(datetime.timedelta(seconds=int(seconds)))
                self.info_label.set_text(f"Dauer: {dur}\n{category}\n{self.desc_list[index]}")
                self.current_index = index
        
    def handle_close(self, *args):
        Gtk.main_quit()

    def read_channels(self, result):
        self.model.clear()
        for section in result.splitlines():
            name = str(section.split(",")[0])
            url = str(section.split(",")[1])
            self.model.append((name, url, self.mediathek_icon))
        self.dl_btn.set_visible(True)
        #self.header.set_subtitle("Suche beendet")

    def play(self, view, path):
        url = self.model[path][1]
        name = self.model[path][0]
        viewer = mf_player.Window(f"{name}.mp4")
        viewer.url = url
        viewer.set_title(name)
        viewer.view.load_uri(url)

    def play_from_button(self, *args):
        if len(self.icon_view.get_selected_items()) > 0:
            ind = self.icon_view.get_selected_items()[0]
            name = self.model[ind][0]
            url = self.model[ind][1]
            if "webxxl" in url:
                url = url.replace(".webxxl.",".webm.")
            if "3360k_p36v15.mp4" in url:
                url = url.replace("3360k_p36v15.mp4", "1628k_p13v15.mp4")
            if ".xxl.mp4" in url:
                url = url.replace(".xxl.mp4", ".l.mp4")
            viewer = mf_player.Window(f"{name}.mp4")
            viewer.url = url
            viewer.set_title(name)
            viewer.view.load_uri(url)
        
    def find_movies(self, *args):
        print("durchsuchen ...")
        self.header.set_subtitle("durchsuchen ...")
        #self.current_index = 0
        self.desc_list = []
        self.duration_list = []
        self.category_list = []
        result_list = ""
        url = "https://mediathekviewweb.de/feed?query="

        searchterm = self.search_entry.get_text()
        film_title = ""
        self.info_label.set_text("suche ...")
        if searchterm != "":
            search_url = f'{url}{urllib.parse.quote(searchterm)}&everywhere=true&future=true&size=500'
            print(search_url)
            result = requests.get(search_url).text
            if result:
                mytree = et.fromstring(result)
                x = 0
                for child in mytree.iter('item'):
                    for title in child.iter('title'):
                        if "Audiodeskription" in title.text:
                            film_title = f'{title.text.split(" -")[0].replace("(Audiodeskription)", "")} [AD],'
                        else:
                            film_title = f'{title.text.split(" -")[0]},'
                        result_list += film_title.replace(", ", " ").replace(":", "")
                    for url in child.iter('link'):   
                        result_list += (url.text)
                    for desc in child.iter('description'):   
                        self.desc_list.append(desc.text)
                    for duration in child.iter('duration'):   
                        self.duration_list.append(duration.text)
                    for category in child.iter('category'): 
                        self.category_list.append(category.text)
                    result_list += "\n"
                    x += 1
                self.info_label.set_text(f"{x} Beiträge gefunden")
                self.header.set_subtitle(f"{x} Beiträge gefunden")        
                self.read_channels(result_list)
            else:
                print("no result")
        
        
if __name__ == '__main__':
    window = Window()
    window.resize(750, 600)
    window.move(0, 0)
    Gtk.main()