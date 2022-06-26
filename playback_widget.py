import glob
import os
import time
import yaml
from munch import munchify


from PyQt5.QtCore import Qt, QDir, QUrl
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtWidgets import QWidget, QPushButton, QStyle, QSlider, QLabel, \
    QSizePolicy, QHBoxLayout, QVBoxLayout, QFileDialog

RECORD_FOLDER = None

class VideoPlayer(QWidget):
    def __init__(self, parent=None, record_folder=None):
        super(VideoPlayer, self).__init__(parent)
        self.RECORD_FOLDER = record_folder
        self.mediaPlayer = QMediaPlayer(None, QMediaPlayer.VideoSurface)

        videoWidget = QVideoWidget()
        # 960 ,540

        self.playButton = QPushButton()
        self.playButton.setEnabled(False)
        self.playButton.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.playButton.clicked.connect(self.play)

        self.positionSlider = QSlider(Qt.Horizontal)
        self.positionSlider.setRange(0, 0)
        self.positionSlider.sliderMoved.connect(self.setPosition)

        self.error = QLabel()
        self.error.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        self.openButton = QPushButton("Open Video", self)
        self.openButton.setToolTip("Open Video File")
        self.openButton.setStatusTip("Open Video File")
        self.openButton.clicked.connect(self.openFile)

        # Create a widget for window contents
        # wid = QWidget(self)
        # self.setCentralWidget(wid)

        # Create layouts to place inside widget
        controlLayout = QHBoxLayout()
        controlLayout.setContentsMargins(0, 0, 0, 0)
        controlLayout.addWidget(self.openButton)
        controlLayout.addWidget(self.playButton)
        controlLayout.addWidget(self.positionSlider)

        layout = QVBoxLayout()
        layout.addWidget(videoWidget)
        layout.addLayout(controlLayout)
        layout.addWidget(self.error)

        # Set widget to contain window contents
        self.setLayout(layout)

        self.mediaPlayer.setVideoOutput(videoWidget)
        self.mediaPlayer.stateChanged.connect(self.mediaStateChanged)
        self.mediaPlayer.positionChanged.connect(self.positionChanged)
        self.mediaPlayer.durationChanged.connect(self.durationChanged)
        self.mediaPlayer.error.connect(self.handleError)
        self.installEventFilter(self)

    def eventFilter(self, object, event):
        if event.type() == 13 or event.type() == 17:  # Move or Showevent
            self.openLatestFile()
        return False

    def openLatestFile(self):
        currentDir = os.path.dirname(os.path.abspath(__file__))
        list_of_files = glob.glob(currentDir + '/' + self.RECORD_FOLDER + '/*')  # * means all if need specific format then *.csv
        print(str(list_of_files))
        if list_of_files and len(list_of_files) != 0:  # Empty list
            print(str(list_of_files))
            latest_file = max(list_of_files, key=os.path.getctime)
            print(str(latest_file) + ' ++++++++++++++++++++++++')
            self.mediaPlayer.setMedia(
                QMediaContent(QUrl.fromLocalFile(latest_file)))
            self.playButton.setEnabled(True)

            # place a video frame in the playback widget
            self.play()
            time.sleep(.1)
            self.play()

    def openFile(self):
        fileName, _ = QFileDialog.getOpenFileName(self, "Open Movie",
                                                  QDir.path(QDir(self.RECORD_FOLDER)))
        print (str(fileName) + '--------------------')
        if fileName != '':
            self.mediaPlayer.setMedia(
                QMediaContent(QUrl.fromLocalFile(fileName)))
            self.playButton.setEnabled(True)

            # place a video frame in the playback widget
            self.play()
            time.sleep(.01)
            self.play()

    def play(self):
        if self.mediaPlayer.state() == QMediaPlayer.PlayingState:
            self.mediaPlayer.pause()
        else:
            self.mediaPlayer.play()

    def mediaStateChanged(self, state):
        if self.mediaPlayer.state() == QMediaPlayer.PlayingState:
            self.playButton.setIcon(
                self.style().standardIcon(QStyle.SP_MediaPause))
        else:
            self.playButton.setIcon(
                self.style().standardIcon(QStyle.SP_MediaPlay))

    def positionChanged(self, position):
        self.positionSlider.setValue(position)

    def durationChanged(self, duration):
        self.positionSlider.setRange(0, duration)

    def setPosition(self, position):
        self.mediaPlayer.setPosition(position)

    def handleError(self):
        self.playButton.setEnabled(False)
        self.error.setText("Error: " + self.mediaPlayer.errorString())
