# USB camera display using PyQt and OpenCV, from iosoft.blog
# Copyright (c) Jeremy P Bentham 2019
# Please credit iosoft.blog if you use the information or software in it
from live_widget import LiveWidget
from playback_widget import VideoPlayer
from yolo_formatter import YoloVideoSelf

VERSION = "Heads-Up v0.10"

import sys, time, threading, cv2
from PyQt5.QtCore import QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QApplication, QMainWindow, QTextEdit, QTabWidget
from PyQt5.QtWidgets import QWidget, QAction, QVBoxLayout, QHBoxLayout
from PyQt5.QtGui import QFont, QImage, QTextCursor

try:
    import Queue as Queue
except:
    import queue as Queue

IMG_SIZE = 1920, 1080  # 640,480 or 1280,720 or 1920,1080    --
IMG_FORMAT = QImage.Format_RGB888
DISP_SCALE = 2  # Scaling factor for display image
DISP_MSEC = 50  # Delay between display cycles
CAP_API = cv2.CAP_ANY  # API: CAP_ANY or CAP_DSHOW etc...
EXPOSURE = 0  # Zero for automatic exposure
TEXT_FONT = QFont("Courier", 10)
    
camera_num = 0  # Default camera (first in list)
image_queue = Queue.Queue()  # Queue to hold images
capturing = True  # Flag to indicate capturing


# Grab images from the camera (separate thread)
def grab_images(cam_num, queue, self=None):
    cap = cv2.VideoCapture(camera_num)
    neural_network = cv2.dnn.readNet("yolov4-tiny_best-5.weights", "yolov4-tiny-5.cfg")
    neural_network.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
    neural_network.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
    yoloVideoSelf = YoloVideoSelf()
    yoloVideoSelf.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) + 0.5)
    yoloVideoSelf.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) + 0.5)

    # Define the codec and create VideoWriter object
    yoloVideoSelf.fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Be sure to use the lower case
    # yoloVideoSelf.out = cv2.VideoWriter('output.mp4', yoloVideoSelf.fourcc, 20.0, (yoloVideoSelf.width, yoloVideoSelf.height))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, IMG_SIZE[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, IMG_SIZE[1])
    if EXPOSURE:
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0)
        cap.set(cv2.CAP_PROP_EXPOSURE, EXPOSURE)
    else:
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
    while capturing:
        if cap.grab():
            retval, image = cap.retrieve(0)
            if image is not None and queue.qsize() < 2:
                yoloVideoSelf.processFrame(image, neural_network, cap, camera_num)
                queue.put(image)
            else:
                time.sleep(DISP_MSEC / 1000.0)
        else:
            print("Error: can't grab camera image")
            break
    cap.release()


# Image widget


# Main window
class MyWindow(QMainWindow):
    text_update = pyqtSignal(str)

    # Create main window
    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)
        self.qWidget = QWidget(self)
        self.textbox = QTextEdit(self.qWidget)
        self.textbox.setFont(TEXT_FONT)
        self.textbox.setMinimumSize(300, 100)
        self.text_update.connect(self.append_text)
        sys.stdout = self
        print("Camera number %u" % camera_num)
        print("Image size %u x %u" % IMG_SIZE)
        if DISP_SCALE > 1:
            print("Display scale %u:1" % DISP_SCALE)

        # Initialize tab screen
        self.tabs = QTabWidget()
        self.tab1 = QWidget()
        self.tab2 = QWidget()

        # Add tabs
        self.tabs.addTab(self.tab1, "Live")
        self.tabs.addTab(self.tab2, "Play Back")

        # Create first tab
        self.tab1.layout = QVBoxLayout()
        self.liveWidget = LiveWidget(self)
        self.tab1.layout.addWidget(self.liveWidget)
        self.tab1.setLayout(self.tab1.layout)

        # Create first tab
        self.tab2.layout = QVBoxLayout()
        self.playBackWidget = VideoPlayer(self)
        self.tab2.layout.addWidget(self.playBackWidget)
        self.tab2.setLayout(self.tab2.layout)

        self.vLayout = QVBoxLayout()  # Window layout
        self.hBoxLayout = QHBoxLayout()

        # self.hBoxLayout.addWidget(self.imageWidget)
        self.hBoxLayout.addWidget(self.tabs)

        self.vLayout.addLayout(self.hBoxLayout)
        self.vLayout.addWidget(self.textbox)
        self.qWidget.setLayout(self.vLayout)
        self.setCentralWidget(self.qWidget)

        self.mainMenu = self.menuBar()  # Menu bar
        exitAction = QAction('&Exit', self)
        exitAction.setShortcut('Ctrl+Q')
        exitAction.triggered.connect(self.close)
        self.fileMenu = self.mainMenu.addMenu('&File')
        self.fileMenu.addAction(exitAction)

    @pyqtSlot()
    def on_click(self):
        print("\n")
        for currentQTableWidgetItem in self.tableWidget.selectedItems():
            print(currentQTableWidgetItem.row(), currentQTableWidgetItem.column(), currentQTableWidgetItem.text())

    # Start image capture & display
    def start(self):
        self.timer = QTimer(self)  # Timer to trigger display
        self.timer.timeout.connect(lambda:
                                   self.show_image(image_queue, self.liveWidget, DISP_SCALE))
        self.timer.start(DISP_MSEC)
        self.capture_thread = threading.Thread(target=grab_images,
                                               args=(camera_num, image_queue))
        self.capture_thread.start()  # Thread to grab images

    # Fetch camera image from queue, and display it
    def show_image(self, imageq, display, scale):
        if not imageq.empty():
            image = imageq.get()
            if image is not None and len(image) > 0:
                img = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                self.display_image(img, display, scale)

    # Display an image, reduce size if required
    def display_image(self, img, display, scale=1):
        disp_size = img.shape[1] // scale, img.shape[0] // scale
        disp_bpl = disp_size[0] * 3
        if scale > 1:
            img = cv2.resize(img, disp_size,
                             interpolation=cv2.INTER_CUBIC)
        qimg = QImage(img.data, disp_size[0], disp_size[1],
                      disp_bpl, IMG_FORMAT)
        display.setImage(qimg)

    # Handle sys.stdout.write: update text display
    def write(self, text):
        self.text_update.emit(str(text))
        with open('log.txt', 'a') as f:
            f.write(text)
            f.close()

    def flush(self):
        pass

    # Append to text display
    def append_text(self, text):
        cur = self.textbox.textCursor()  # Move cursor to end of text
        cur.movePosition(QTextCursor.End)
        s = str(text)
        while s:
            head, sep, s = s.partition("\n")  # Split line at LF
            cur.insertText(head)  # Insert text at cursor
            if sep:  # New line if LF
                cur.insertBlock()
        self.textbox.setTextCursor(cur)  # Update visible cursor

    # Window is closing: stop video capture
    def closeEvent(self, event):
        global capturing
        capturing = False
        self.capture_thread.join()


if __name__ == '__main__':
    app = QApplication([])
    win = MyWindow()
    win.show()
    win.setWindowTitle(VERSION)
    win.start()
    sys.exit(app.exec_())
