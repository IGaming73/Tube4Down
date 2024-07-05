import pytube  # interact with YouTube
import PyQt5.QtWidgets as Qt  # UI
from PyQt5 import QtCore
from PyQt5 import QtGui
import PyQt5.QtWebEngineWidgets as QtWeb  # web interface
from PyQt5.QtCore import QThread, pyqtSignal  # threading
import tkinter as tk  # file dialog
from PIL import Image  # image handling
from bs4 import BeautifulSoup  # HTML parsing
import threading as thr  # threading
import requests  # HTTP requests
import urllib  # URL handling
import urllib.error
import os  # interact with the system
import sys  # system handling
import glob  # list files
import time  # time handling
import io  # byte handling for images


class YTDownloader(Qt.QMainWindow):
    """YouTube video downloader with GUI"""

    class Downloader(QThread):
        """Class containing all the needed functions to download a video or audio with the desired settings"""
        size = pyqtSignal(int)  # signal to send the total file size in bytes (audio + video if needed)
        progress = pyqtSignal(int)  # signal to send the download progress in remaining bytes
        converting = pyqtSignal()  # signal to send when the file is being converted
        finished = pyqtSignal()  # signal to send when the download is finished

        def __init__(self, video_id:str, media_type:str, settings:dict, measure_size:bool=False):
            """the type can be "video" or "audio" and the settings are the video quality, if there is audio, the format, the file name and the save path, use measure_size to get the total file size and not download anything"""
            super().__init__()
            self.video_id = video_id
            self.type = media_type
            self.settings = settings
            self.measure_size = measure_size

        def start(self):
            """start the download process"""
            self.qualities = ["2160p", "1440p", "1080p", "720p", "480p", "360p", "240p", "144p"]
            self.video_url = f"https://www.youtube.com/watch?v={self.video_id}"
            self.total_size = 0  # total file size in bytes
            self.video = pytube.YouTube(self.video_url, on_progress_callback=lambda stream, data, remaining: self.progress.emit(remaining))  # video object

            if self.type == "video":
                self.quality = self.settings["quality"]
                if self.quality.lower() == "max":
                    self.quality = self.qualities[0]
                self.has_audio = self.settings["has_audio"]
            else:
                self.quality = None
                self.has_audio = None
            self.format = self.settings["format"].lower()
            self.file_name = self.settings["file_name"]
            self.save_path = self.settings["save_path"]
            self.download()
        
        def download(self):
            """Download the video or audio with the desired settings"""
            self.get_best_streams()
            if not self.measure_size:  # if we want to download the file
                self.download_base_files()
                self.convert_file()
        
        def get_best_streams(self):
            """determine the best data streams depending on the quality and format settings"""
            # finding the best stream for the used settings and choosing the required resolution quality
            if self.type == "video":
                self.video_instances = self.video.streams.filter(adaptive=True, type="video")
                quality_index = self.qualities.index(self.quality)
                self.quality_ranked = [self.qualities[quality_index]] + self.qualities[quality_index+1:] + self.qualities[:quality_index][::-1]  # ordered list of qualities, preffering the first available one
                for quality in self.quality_ranked:
                    self.video_instances_quality = self.video_instances.filter(res=quality)
                    if self.video_instances_quality:
                        self.used_quality = quality
                        break
                # choosing the best refresh rate, if possible with the wanted format
                self.video_instances_quality = self.video_instances_quality.order_by("fps").desc()
                best_fps = self.video_instances_quality.first().fps
                self.video_instances_quality = self.video_instances_quality.filter(fps=best_fps)
                if self.video_instances_quality.filter(mime_type=f"video/{self.format}"):
                    self.video_instance = self.video_instances_quality.filter(mime_type=f"video/{self.format}").first()
                else:
                    self.video_instance = self.video_instances_quality.first()
                # getting the file type
                self.video_instance_file_type = self.video_instance.mime_type.split("/")[1]
                self.total_size += self.video_instance.filesize
            
            if self.type == "audio" or self.has_audio:
                # choosing the best audio quality
                self.audio_instances = self.video.streams.filter(adaptive=True, type="audio").order_by("abr")
                self.audio_instance = self.audio_instances.last()
                self.audio_instance_file_type = self.audio_instance.mime_type.split("/")[1]
                self.total_size += self.audio_instance.filesize
            
            self.size.emit(self.total_size)  # send the total file size to the main thread
        
        def download_base_files(self):
            """Download the files (video and/or audio) with the default format in the cache (webp/mp4 for both video and audio)"""
            if self.type == "video":
                # download the video
                self.video_instance.download("cache\\videos", filename=f"{self.video_id}.{self.video_instance_file_type}")
            if self.type == "audio" or self.has_audio:
                # download the audio
                self.audio_instance.download("cache\\audios", filename=f"{self.video_id}.{self.audio_instance_file_type}")

        def convert_file(self):
            """If needed, convert the file to the desired format, merge audio and video, and move it to the save path"""
            self.converting.emit()  # send the converting signal to the main thread
            ffmpeg_path = "ffmpeg\\ffmpeg.exe"  # path to the ffmpeg executable
            if self.type == "video":
                # convert the video to the desired format
                if self.video_instance_file_type != self.format:
                    os.system(f"{ffmpeg_path} -i cache\\videos\\{self.video_id}.{self.video_instance_file_type} cache\\videos\\{self.video_id}.{self.format}")
                    os.remove(f"cache\\videos\\{self.video_id}.{self.video_instance_file_type}")
            if self.type == "audio" or self.has_audio:
                # convert the audio to the desired format
                if self.audio_instance_file_type != self.format:
                    os.system(f"{ffmpeg_path} -i cache\\audios\\{self.video_id}.{self.audio_instance_file_type} cache\\audios\\{self.video_id}.{self.format}")
                    os.remove(f"cache\\audios\\{self.video_id}.{self.audio_instance_file_type}")
            
            if self.has_audio:
                # merge the audio and video
                os.system(f"{ffmpeg_path} -i cache\\videos\\{self.video_id}.{self.format} -i cache\\audios\\{self.video_id}.{self.format} -c copy cache\\media\\{self.video_id}.{self.format}")
                os.remove(f"cache\\videos\\{self.video_id}.{self.format}")
                os.remove(f"cache\\audios\\{self.video_id}.{self.format}")
            
            # get the cache path of the file to move
            cache_file_name = f"{self.video_id}.{self.format}"
            if self.type == "audio":
                output = f"cache\\audios\\{cache_file_name}"
            elif self.has_audio:
                output = f"cache\\media\\{cache_file_name}"
            else:
                output = f"cache\\videos\\{cache_file_name}"
            
            # make sure the file name is not already taken
            while os.path.exists(f"{self.save_path}\\{self.file_name}.{self.format}"):
                self.file_name += "_"
            # rename and move the file to the final save path
            os.rename(output, f"{self.save_path}\\{self.file_name}.{self.format}")
            self.finished.emit()  # send the finished signal to the main thread
    
    
    class VideoInfos(Qt.QWidget):
        """Widget displaying video information and live preview with a checkbox to select it"""

        def __init__(self, video_id:str):
            self.video_id = video_id  # video id
        
        def get_data(self):
            """retrieve all the data from the video, including finding and downloading the channel icon"""
            try:
                self.video = pytube.YouTube.from_id(self.video_id)  # video object
                self.video_title = self.video.title
                self.channel_name = self.video.author
                self.channel_id = self.video.channel_id
                self.channel_url = self.video.channel_url
                self.embed_url = self.video.embed_url
                self.channel_icon_path = f"cache/channel_icons/{self.channel_id}.jpg"
                self.channel_icon_pixmap = self.channel_icon_pixmap = None
            except urllib.error.URLError:
                self.video_title = "Pas d'internet"
                self.channel_name = "Vérifiez votre connexion réseau"
                self.embed_url = "https://youtube.com"
                self.channel_icon_path = "assets/no_internet.png"
                self.channel_url = "https://youtube.com"
                self.channel_icon_pixmap = self.channel_icon_pixmap = None

        def build_widget(self):
            """builds the widget and its elements"""
            super().__init__()

            self.preview_height = 200
            self.channel_icon_size = 100

            self.big_layout = Qt.QVBoxLayout()
            self.setLayout(self.big_layout)

            # creating the main layout
            self.main_widget = Qt.QWidget()
            self.main_layout = Qt.QHBoxLayout()
            self.main_widget.setLayout(self.main_layout)
            self.big_layout.addWidget(self.main_widget)

            # creating the checkbox
            self.add_button = Qt.QPushButton()
            self.add_button.setFixedSize(30, self.preview_height)
            self.add_button.setIcon(QtGui.QIcon("assets/add.png"))
            self.main_layout.addWidget(self.add_button)

            # creating the video preview
            self.web_view = QtWeb.QWebEngineView()
            self.web_view.setFixedHeight(self.preview_height)
            self.web_view.setFixedWidth(round(16/9*self.preview_height))
            htmlString = '<style> body{margin:0px} </style> <iframe width="100%" height="100%" src="' + self.embed_url + '" frameborder="0" allow="autoplay; encrypted-media"></iframe>'
            self.web_view.setHtml(htmlString, QtCore.QUrl("local"))
            self.main_layout.addWidget(self.web_view)

            # creating the infos layout
            self.infos_widget = Qt.QWidget()
            self.infos_layout = Qt.QVBoxLayout()
            self.infos_widget.setLayout(self.infos_layout)
            self.main_layout.addWidget(self.infos_widget)

            # creating the video title label
            self.title_label = Qt.QLabel(self.video_title)
            self.title_label.setWordWrap(True)
            self.title_label.setFont(QtGui.QFont("Arial", 20))
            self.title_label.setAlignment(QtCore.Qt.AlignCenter)
            self.infos_layout.addWidget(self.title_label)

            # creating the channel layout
            self.channel_widget = Qt.QWidget()
            self.channel_layout = Qt.QHBoxLayout()
            self.channel_widget.setLayout(self.channel_layout)
            self.infos_layout.addWidget(self.channel_widget)
            self.channel_layout.addStretch()

            # creating the channel label
            self.channel_label = Qt.QLabel(self.channel_name)
            self.channel_label.setWordWrap(True)
            self.channel_label.setFont(QtGui.QFont("Arial", 18))
            self.channel_label.setAlignment(QtCore.Qt.AlignCenter)
            self.channel_layout.addWidget(self.channel_label)
            
            # creating the channel icon
            self.channel_icon = Qt.QLabel()
            self.channel_icon_pixmap = QtGui.QPixmap("assets/profile.png")
            self.channel_icon_pixmap = self.channel_icon_pixmap.scaled(self.channel_icon_size, self.channel_icon_size, QtCore.Qt.KeepAspectRatio)
            self.channel_icon.setPixmap(self.channel_icon_pixmap)
            self.channel_layout.addWidget(self.channel_icon)

            # creating the separator
            self.separator = Qt.QFrame()
            self.separator.setFrameShape(Qt.QFrame.HLine)
            self.separator.setFrameShadow(Qt.QFrame.Sunken)
            self.big_layout.addWidget(self.separator)
        
        def get_channel_icon_url(self) -> str:
            """finds the channel icon URL from the channel page"""
            response = requests.get(self.channel_url)  # get the channel page html content
            soup = BeautifulSoup(response.text, 'html.parser')  # parse the html content
            meta_tag = soup.find('meta', attrs={'property': 'og:image'})  # find the meta tag with the channel icon URL
            if meta_tag:
                self.channel_icon_url = meta_tag['content']  # get the channel icon URL
                return self.channel_icon_url
            else:
                return "https://static.thenounproject.com/png/2247019-200.png"
        
        def download_channel_icon(self, path:str):
            """downloads the channel icon in the given folder"""
            if not os.path.exists(path):
                os.makedirs(path)  # create the destination folder if it doesn't exist
            image_url = self.get_channel_icon_url()  # get the channel icon URL
            image_data = requests.get(image_url).content  # get the image data
            with open(f"{path}/{self.channel_id}.jpg", "wb") as image_file:
                image_file.write(image_data)  # write the image data in the file
        
        def apply_channel_icon(self):
            """download and display the channel icon"""
            try:
                self.download_channel_icon("cache/channel_icons")
            except requests.exceptions.ConnectionError:
                self.channel_icon_path = "assets/no_internet.png"
            self.channel_icon_pixmap = QtGui.QPixmap(self.channel_icon_path)
            self.channel_icon_pixmap = self.channel_icon_pixmap.scaled(self.channel_icon_size, self.channel_icon_size, QtCore.Qt.KeepAspectRatio)
            self.channel_icon.setPixmap(self.channel_icon_pixmap)
    

    class VideoInfosThread(QThread):
        """Thread to load the video infos widgets in the background after a search"""
        video_loaded = pyqtSignal(object)  # signal to send the video infos widget one by one
        finished = pyqtSignal()  # signal to send when the thread is finished

        def __init__(self, search_query:str):
            super().__init__()
            self.running = True  # is the thread running
            self.search_query = search_query  # search query

        def run(self):
            """code to run in the thread, search for the videos and send them one by one to the main thread"""
            try:
                self.search = pytube.Search(self.search_query)  # search for the videos
                self.search_results = self.search.results  # get the search results list

                for result in self.search_results:  # for each result
                    result_id = result.video_id
                    self.preview = YTDownloader.VideoInfos(result_id)  # create a video infos widget
                    self.preview.get_data()  # load the required data for the video infos widget
                    if self.running:
                        self.video_loaded.emit(self.preview)  # send the video infos widget, it will be build in the main thread to avoid errors
                    else:
                        return
                self.finished.emit()  # send the finished signal only if the thread is not stopped
            
            except urllib.error.URLError:  # if there is no internet
                self.search_results = []
                self.preview = YTDownloader.VideoInfos("00000000000")
                self.preview.get_data()
                self.video_loaded.emit(self.preview)  # if there is no internet, seld an "empty" video infos widget
                self.finished.emit()
        
        def stop(self):
            """stops the thread"""
            self.running = False
    

    class DownloadInfos(Qt.QWidget):
        """Widget displaying a preview of the videos that are going to be downloaded and allows to change the file name"""
        
        def __init__(self, video_id:str):
            self.video_id = video_id
        
        def get_data(self):
            self.video = pytube.YouTube.from_id(self.video_id)  # video object
            self.thumbnail_height = 150
            self.video_thumbnail = self.video.thumbnail_url  # video thumbnail URL
            
            try:
                self.video_title = self.video.title  # video title
                self.channel_name = self.video.author  # channel name
                self.download_video_thumbnail("cache/thumbnails")  # download the video thumbnail in the cache folder
                self.thumbnail_path = f"cache/thumbnails/{self.video_id}.jpg"  # thumbnail path
            except urllib.error.URLError:
                self.video_title = "Pas d'internet"
                self.channel_name = "Vérifiez votre connexion réseau"
                self.thumbnail_path = "assets/no_internet.png"

        def build_widget(self):
            super().__init__()

            self.big_layout = Qt.QVBoxLayout()
            self.setLayout(self.big_layout)

            # creating the main layout
            self.main_widget = Qt.QWidget()
            self.main_layout = Qt.QHBoxLayout()
            self.main_widget.setLayout(self.main_layout)
            self.big_layout.addWidget(self.main_widget)

            # creating the checkbox
            self.remove_button = Qt.QPushButton()
            self.remove_button.setFixedSize(30, round(self.thumbnail_height*0.6))
            self.remove_button.setIcon(QtGui.QIcon("assets/remove.png"))
            self.main_layout.addWidget(self.remove_button)

            # creating the thumbnail
            self.thumbnail = Qt.QLabel()
            self.thumbnail_pixmap = QtGui.QPixmap(self.thumbnail_path)
            self.thumbnail_pixmap = self.thumbnail_pixmap.scaled(self.thumbnail_height, int(16/9*self.thumbnail_height), QtCore.Qt.KeepAspectRatio)
            self.thumbnail.setPixmap(self.thumbnail_pixmap)
            self.main_layout.addWidget(self.thumbnail)

            # creating the text layout
            self.text_widget = Qt.QWidget()
            self.text_layout = Qt.QVBoxLayout()
            self.text_widget.setLayout(self.text_layout)
            self.main_layout.addWidget(self.text_widget)

            # creating the file name field
            self.file_name = Qt.QLineEdit(self.video_title)
            self.file_name.setFont(QtGui.QFont("Arial", 14))
            self.text_layout.addWidget(self.file_name)

            # creating the video title label
            self.title_label = Qt.QLabel(self.video_title)
            self.title_label.setWordWrap(True)
            self.title_label.setFont(QtGui.QFont("Arial", 14))
            self.text_layout.addWidget(self.title_label)

            # creating the channel label
            self.channel_label = Qt.QLabel(self.channel_name)
            self.channel_label.setWordWrap(True)
            self.channel_label.setFont(QtGui.QFont("Arial", 12))
            self.text_layout.addWidget(self.channel_label)

            # creating the separator
            self.separator = Qt.QFrame()
            self.separator.setFrameShape(Qt.QFrame.HLine)
            self.separator.setFrameShadow(Qt.QFrame.Sunken)
            self.big_layout.addWidget(self.separator)
        
        def download_video_thumbnail(self, path:str):
            """downloads the video thumbnail in the given folder"""
            if not os.path.exists(path):
                os.makedirs(path)  # create the destination folder if it doesn't exist
            image_data = requests.get(self.video_thumbnail).content  # get the image data
            image = Image.open(io.BytesIO(image_data))  # open the image as an image object

            # crop the image to 16:9 ratio
            width, height = image.size
            new_width, new_height = width, int(width * 9/16)
            if new_height > height:
                new_height, new_width = height, int(new_height * 16/9)
            left = (width - new_width) / 2
            top = (height - new_height) / 2
            right = (width + new_width) / 2
            bottom = (height + new_height) / 2

            image = image.crop((left, top, right, bottom))
            image.save(f"{path}/{self.video_id}.jpg", "JPEG")  # save the image in the file
    

    class DownloadInfosThread(QThread):
        """Thread to load the download infos widgets in the background after selecting a video"""
        finished = pyqtSignal(object)  # signal to send when the thread is finished with the download infos widgets

        def __init__(self, video_id:str):
            super().__init__()
            self.video_id = video_id  # video id

        def run(self):
            """code to run in the thread, load the download infos widget and send it to the main thread"""
            self.preview = YTDownloader.DownloadInfos(self.video_id)  # create a download infos widget
            self.preview.get_data()  # load the required data for the widget
            self.finished.emit(self.preview)  # send the finished signal with the widget which will have every required data already loaded

    

    def test(self):
        """video_id = "WO2b03Zdu4Q"
        url = f"https://www.youtube.com/watch?v={video_id}"  # short 4K 60fps video
        yt = pytube.YouTube(url, on_progress_callback=lambda *args: print(args[2]))
        video = yt.streams.filter(adaptive=True).filter(mime_type='video/webm').first()  # no sound, up to 4K, webm file
        video.download("cache")"""
        pass
    
    def start(self):
        """creates UI and launches the interactive GUI"""
        super().__init__()  # initialize the UI module
        self.setWindowTitle("YouTube Downloader")  # set the window title
        self.setWindowIcon(QtGui.QIcon("assets/icon.png"))  # set the window icon
        self.build_ui()  # build the UI
        self.setup_software()  # setup the UI, the events and the variables
        self.showMaximized()  # maximize the window
        self.show()  # display the UI
    
    def build_ui(self):
        """creates the UI base layout and widgets"""

        # creating base layout
        self.central_widget = Qt.QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = Qt.QHBoxLayout(self.central_widget)

        # creating secondary layouts
        self.videos_layout = Qt.QVBoxLayout()
        self.settings_layout = Qt.QVBoxLayout()
        self.download_layout = Qt.QVBoxLayout()

        # creating corresponding widgets an setting their layout
        self.videos_zone = Qt.QWidget()
        self.settings_tab = Qt.QTabWidget()
        self.download_widget = Qt.QWidget()

        # setting the layouts
        self.videos_zone.setLayout(self.videos_layout)
        self.settings_tab.setLayout(self.settings_layout)
        self.download_widget.setLayout(self.download_layout)

        # creating splitter and adding the layouts
        self.splitter = Qt.QSplitter(1)  # create a horizontal splitter
        self.main_layout.addWidget(self.splitter)
        self.splitter.addWidget(self.videos_zone)
        self.splitter.addWidget(self.settings_tab)
        self.splitter.addWidget(self.download_widget)
        self.splitter.setSizes([500, 200, 300])  # set the size ratio of each section

        # creating items and scrollbox for the video layout
        self.last_search_time = time.time()  # last time a search was made to implement a cooldown
        self.search_widget = Qt.QWidget()
        self.search_layout = Qt.QHBoxLayout()
        self.search_widget.setLayout(self.search_layout)
        self.videos_layout.addWidget(self.search_widget)

        self.searchbar = Qt.QLineEdit()
        self.searchbar.setPlaceholderText("Rechercher une vidéo")
        self.searchbar.setFixedHeight(30)
        self.searchbar.setFont(QtGui.QFont("Arial", 16))
        self.search_layout.addWidget(self.searchbar)

        self.search_button = Qt.QPushButton()
        self.search_button.setFixedSize(50, 30)
        self.search_button.setIcon(QtGui.QIcon("assets/search.png"))
        self.search_layout.addWidget(self.search_button)

        self.videos_scroll = Qt.QScrollArea()
        self.videos_scroll.setWidgetResizable(True)
        self.videos_scroll.setStyleSheet("QScrollArea { border: none; }")
        self.videos_scroll_inner_widget = Qt.QWidget()
        self.videos_scroll_layout = Qt.QVBoxLayout()
        self.videos_scroll.setWidget(self.videos_scroll_inner_widget)
        self.videos_scroll_inner_widget.setLayout(self.videos_scroll_layout)
        self.videos_layout.addWidget(self.videos_scroll)

        self.videos_scroll_layout.addStretch()

        # creating items for the settings layout
        self.settings_tab.setStyleSheet("QTabBar::tab { font-size: 16px; width: 80px; height: 30px; }")

        self.video_tab = Qt.QWidget()
        self.settings_tab.addTab(self.video_tab, "Vidéo")
        self.settings_video_tab = Qt.QVBoxLayout(self.video_tab)
        self.settings_video = Qt.QVBoxLayout()
        self.settings_video_scroll = Qt.QScrollArea()
        self.settings_video_scroll.setWidgetResizable(True)
        self.settings_video_scroll.setStyleSheet("QScrollArea { border: none; }")
        self.settings_video_scroll_inner_widget = Qt.QWidget()
        self.settings_video_scroll.setWidget(self.settings_video_scroll_inner_widget)
        self.settings_video_scroll_inner_widget.setLayout(self.settings_video)
        self.settings_video_tab.addWidget(self.settings_video_scroll)

        self.audio_tab = Qt.QWidget()
        self.settings_tab.addTab(self.audio_tab, "Audio")
        self.settings_audio_tab = Qt.QVBoxLayout(self.audio_tab)
        self.settings_audio = Qt.QVBoxLayout()
        self.settings_audio_scroll = Qt.QScrollArea()
        self.settings_audio_scroll.setWidgetResizable(True)
        self.settings_audio_scroll.setStyleSheet("QScrollArea { border: none; }")
        self.settings_audio_scroll_inner_widget = Qt.QWidget()
        self.settings_audio_scroll.setWidget(self.settings_audio_scroll_inner_widget)
        self.settings_audio_scroll_inner_widget.setLayout(self.settings_audio)
        self.settings_audio_tab.addWidget(self.settings_audio_scroll)
        
        # video settings
        self.video_hasAudio_box = Qt.QGroupBox("Audio")
        self.video_hasAudio_box.setFont(QtGui.QFont("Arial", 16))
        self.video_hasAudio_layout = Qt.QVBoxLayout()
        self.video_hasAudio_box.setLayout(self.video_hasAudio_layout)
        self.settings_video_hasAudio = Qt.QCheckBox("Inclure l'audio dans la vidéo")
        self.settings_video_hasAudio.setChecked(True)
        self.video_hasAudio_layout.addWidget(self.settings_video_hasAudio)
        self.settings_video.addWidget(self.video_hasAudio_box)

        self.settings_video_quality = Qt.QButtonGroup()
        self.video_qualities = ["Max", "2160p 4K", "1440p 2K", "1080p FHD", "720p HD", "480p SD", "360p", "240p", "144p"]
        self.video_quality_box = Qt.QGroupBox("Qualité vidéo")
        self.video_quality_box.setFont(QtGui.QFont("Arial", 16))
        self.video_quality_layout = Qt.QVBoxLayout()
        self.video_quality_box.setLayout(self.video_quality_layout)
        video_quality_info = Qt.QLabel("Pour chaque vidéo, la qualité maximale sera utilisée si la qualité sélectionnée n'est pas disponible.")
        video_quality_info.setWordWrap(True)
        video_quality_info.setFont(QtGui.QFont("Arial", 12))
        video_quality_info.setStyleSheet("color: gray;")
        self.video_quality_layout.addWidget(video_quality_info)
        buttons = [Qt.QRadioButton(quality) for quality in self.video_qualities]
        buttons[0].setChecked(True)
        for button in buttons:
            self.settings_video_quality.addButton(button)
            self.video_quality_layout.addWidget(button)
        self.settings_video.addWidget(self.video_quality_box)

        self.settings_video_format = Qt.QButtonGroup()
        self.video_formats = ["MP4", "MOV", "AVI", "MKV", "WebM"]
        self.video_format_box = Qt.QGroupBox("Format vidéo")
        self.video_format_box.setFont(QtGui.QFont("Arial", 16))
        self.video_format_layout = Qt.QVBoxLayout()
        self.video_format_box.setLayout(self.video_format_layout)
        buttons = [Qt.QRadioButton(format) for format in self.video_formats]
        buttons[0].setChecked(True)
        for button in buttons:
            self.settings_video_format.addButton(button)
            self.video_format_layout.addWidget(button)
        self.settings_video.addWidget(self.video_format_box)

        self.settings_video.addStretch()
        
        # audio settings
        self.settings_audio_format = Qt.QButtonGroup()
        self.audio_formats = ["MP3", "MP4", "M4A", "OGG", "WAV", "FLAC"]
        self.audio_format_box = Qt.QGroupBox("Format audio")
        self.audio_format_box.setFont(QtGui.QFont("Arial", 16))
        self.audio_format_layout = Qt.QVBoxLayout()
        self.audio_format_box.setLayout(self.audio_format_layout)
        buttons = [Qt.QRadioButton(format) for format in self.audio_formats]
        buttons[0].setChecked(True)
        for button in buttons:
            self.settings_audio_format.addButton(button)
            self.audio_format_layout.addWidget(button)
        self.settings_audio.addWidget(self.audio_format_box)

        self.settings_audio.addStretch()

        # download section
        self.download_list_layout = Qt.QVBoxLayout()
        self.download_list = Qt.QScrollArea()
        self.download_list.setStyleSheet("QScrollArea { border: none; }")
        self.download_list.setWidgetResizable(True)
        self.download_inner_widget = Qt.QWidget()
        self.download_list.setWidget(self.download_inner_widget)
        self.download_inner_widget.setLayout(self.download_list_layout)
        self.download_layout.addWidget(self.download_list)
        
        self.download_button_widget = Qt.QWidget()
        self.download_button_layout = Qt.QVBoxLayout()
        self.download_button_widget.setLayout(self.download_button_layout)
        self.download_layout.addWidget(self.download_button_widget)

        self.add_video_widget = Qt.QWidget()
        self.add_video_layout = Qt.QHBoxLayout()
        self.add_video_widget.setLayout(self.add_video_layout)
        self.download_button_layout.addWidget(self.add_video_widget)

        self.add_video_field = Qt.QLineEdit()
        self.add_video_field.setPlaceholderText("Ajouter une vidéo avec l'URL")
        self.add_video_field.setFixedHeight(30)
        self.add_video_field.setFont(QtGui.QFont("Arial", 14))
        self.add_video_layout.addWidget(self.add_video_field)

        self.add_video_button = Qt.QPushButton()
        self.add_video_button.setFixedSize(30, 30)
        self.add_video_button.setIcon(QtGui.QIcon("assets/add.png"))
        self.add_video_layout.addWidget(self.add_video_button)

        self.file_size_widget = Qt.QWidget()
        self.file_size_layout = Qt.QHBoxLayout()
        self.file_size_widget.setLayout(self.file_size_layout)
        self.download_button_layout.addWidget(self.file_size_widget)

        self.file_size_text_label = Qt.QLabel("Taille totale :")
        self.file_size_text_label.setFont(QtGui.QFont("Arial", 16))
        self.file_size_layout.addWidget(self.file_size_text_label)

        self.file_size_label = Qt.QLabel(self.standard_size(0))
        self.file_size_label.setFont(QtGui.QFont("Arial", 16))
        self.file_size_layout.addWidget(self.file_size_label)

        self.file_size_layout.addStretch()

        self.download_button = Qt.QPushButton("Télécharger")
        self.download_button.setFixedHeight(50)
        self.download_button.setFont(QtGui.QFont("Arial", 20))
        self.download_button_layout.addWidget(self.download_button)
        
        self.download_list_layout.addStretch()
    
    def setup_software(self):
        """sets up the UI, the events and the variables"""
        self.selected_videos = []  # ids of the selected videos
        self.total_file_size = 0  # total size of the selected videos in bytes
        self.search_display_thread = None  # thread to display the search results

        self.searchbar.returnPressed.connect(self.search_video)  # search when pressing enter
        self.search_button.clicked.connect(self.search_video)  # search when clicking the search button
        self.add_video_field.returnPressed.connect(self.add_video_from_url)  # add a video when pressing enter in the add video field
        self.add_video_button.clicked.connect(self.add_video_from_url)  # add a video when clicking the add video button
        self.download_button.clicked.connect(self.download_selected_videos)  # download the selected videos when clicking the download button
    
    def download_selected_videos(self):
        """downloads the selected videos with the selected settings after asking for the save folder"""
        if not self.selected_videos:
            return
        self.save_path = tk.filedialog.askdirectory()  # ask for the save folder
        if not self.save_path:
            return
        
        if self.settings_tab.currentIndex() == 0:
            self.type = "video"
            self.settings = {
                "quality": self.settings_video_quality.checkedButton().text(),
                "has_audio": self.settings_video_hasAudio.isChecked(),
                "format": self.settings_video_format.checkedButton().text().lower(),
                "file_name": "",
                "save_path": self.save_path
            }
        else:
            self.type = "audio"
            self.settings = {
                "format": self.settings_audio_format.checkedButton().text().lower(),
                "file_name": "",
                "save_path": self.save_path
            }
        self.create_download_window()
    
    def create_download_window(self):
        """Create the window to indicate the download progress"""
        pass
    
    def add_video_from_url(self):
        """adds a video from the URL in the add video field"""
        url = self.add_video_field.text()
        if url:
            try:
                yt = pytube.YouTube(url)
                video_id = yt.video_id
                self.video_add(video_id)
                self.add_video_field.clear()
            except (pytube.exceptions.RegexMatchError, pytube.exceptions.VideoUnavailable):
                self.add_video_field.clear()
    
    def search_video(self):
        """searches for a video and displays the results via a thread"""
        current_time = time.time()
        if current_time - self.last_search_time < 1:
            return  # do not search before the cooldown
        
        self.last_search_time = current_time
        if self.search_display_thread:
            self.search_display_thread.stop()  # stop the previous search thread if it exists
        self.clear_layout(self.videos_scroll_layout)  # clear the previous search results
        self.search_query = self.searchbar.text()  # get the search query
        # creating loading label
        self.loading_label = Qt.QLabel("Chargement des résultats ...")
        self.loading_label.setFont(QtGui.QFont("Arial", 20))
        self.loading_label.setAlignment(QtCore.Qt.AlignCenter)
        self.videos_scroll_layout.insertWidget(self.videos_scroll_layout.count()-1, self.loading_label)  # display the loading label

        self.search_display_thread = self.VideoInfosThread(self.search_query)  # create a new search thread
        self.search_display_thread.video_loaded.connect(self.show_video_preview)  # display the video previews one by one when the thread sends it
        self.search_display_thread.video_loaded.connect(self.load_channel_icon)  # load the channel icons when the preview is loaded
        self.search_display_thread.finished.connect(self.remove_loading_label)  # remove the loading label when the thread is finished
        self.search_display_thread.start()  # start the search thread
    
    def show_video_preview(self, preview:VideoInfos):
        """displays a video preview"""
        preview.build_widget()  # build the video preview widget
        self.videos_scroll_layout.insertWidget(self.videos_scroll_layout.count()-2, preview)  # add the video preview widget to the layout
        preview.add_button.clicked.connect(lambda: self.video_add(preview.video_id))  # add the video to the selected videos list when the checkbox is checked or unchecked
    
    def load_channel_icon(self, preview:VideoInfos):
        """launches the thread to download and display the channel icon"""
        self.load_channel_icon_t = thr.Thread(target=self.load_channel_icon_thread, args=(preview,))
        self.load_channel_icon_t.start()  # start the thread
    
    def load_channel_icon_thread(self, preview:VideoInfos):
        """download and display the channel icons on the video previews"""
        preview.apply_channel_icon()  # download and display the channel icon

    def remove_loading_label(self):
        """removes the loading label from the search results if it exists"""
        if self.loading_label:
            try:
                self.videos_scroll_layout.removeWidget(self.loading_label)
                self.loading_label.deleteLater()
            except RuntimeError:
                pass
    
    def video_add(self, video_id:str):
        """adds a video in the selected videos list if it's not already in it"""
        if video_id not in self.selected_videos:
            self.selected_videos.append(video_id)  # add the video id to the selected videos list
            self.add_download_preview(video_id)  # add the video preview to the download list
    
    def add_download_preview(self, video_id:str):
        """adds a video preview to the download list"""
        self.download_infos_thread = self.DownloadInfosThread(video_id)
        self.download_infos_thread.finished.connect(self.show_download_preview)
        self.download_infos_thread.start()
    
    def show_download_preview(self, preview:DownloadInfos):
        """displays a video preview in the download list"""
        preview.build_widget()
        self.download_list_layout.insertWidget(self.download_list_layout.count()-1, preview)
        preview.remove_button.clicked.connect(lambda: self.video_remove(preview.video_id))
    
    def video_remove(self, video_id:str):
        """removes a video from the selected videos list and the download list"""
        self.selected_videos.remove(video_id)
        for i in range(self.download_list_layout.count()):
            item = self.download_list_layout.itemAt(i)
            if item:
                widget = item.widget()
                if widget and widget.video_id == video_id:
                    self.download_list_layout.removeWidget(widget)
                    widget.deleteLater()
    
    def standard_size(self, size:int) -> str:
        """converts a size in bytes to a human readable size"""
        units = ["o", "Ko", "Mo", "Go", "To", "Po", "Eo", "Zo", "Yo"]
        unit = 0
        while size >= 1024:
            size /= 1024
            unit += 1
            if unit == len(units)-1:
                break
        return f"{round(size, 2)} {units[unit]}"

    def clear_layout(self, layout:Qt.QLayout):
        """Clears a layout"""
        while layout.count() > 1:
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:  # if the item is a widget
                widget.deleteLater()  # delete the widget


def clear_cache():
    """clears the cache folder"""
    cache = glob.glob("cache/*.*") + glob.glob("cache/*/*.*")
    for f in cache:
        try: os.remove(f)
        except: pass

def create_cache():
    """creates the cache folder if it doesn't exist"""
    if not os.path.exists("cache"):
        os.makedirs("cache")
    for folder in ["videos", "audios", "media", "thumbnails", "channel_icons"]:
        if not os.path.exists(f"cache/{folder}"):
            os.makedirs(f"cache/{folder}")

if __name__ == "__main__":
    #try:
        create_cache()
        clear_cache()
        if os.name == "posix":  # if the system is some sort of linux
            os.system("chmod -R 777 cache")  # get full permissions to the cache folder
            os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--no-sandbox"  # set the environment variable for the web engine
        App = Qt.QApplication(sys.argv)  # creating the app
        Window = YTDownloader()  # creating the GUI
        Window.test()
        Window.start()  # starting the GUI
        App.exec_()  # executing the app
    #except Exception as error:
        #error.with_traceback()  # display exception traceback if occured
    #finally:
        # always clear cache
        clear_cache()
