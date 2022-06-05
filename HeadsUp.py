# USB camera display using PyQt and OpenCV, from iosoft.blog
# Copyright (c) Jeremy P Bentham 2019
# Please credit iosoft.blog if you use the information or software in it
from PyQt5.Qt3DRender import QCamera
from PyQt5.QtMultimedia import QCameraInfo, QCameraImageCapture

from live_widget import LiveWidget
from playback_widget import VideoPlayer
from yolo_formatter import YoloVideoSelf

VERSION = "Heads-Up v0.10"

import sys, time, threading, cv2
from PyQt5.QtCore import QTimer, pyqtSignal, pyqtSlot, QSize
from PyQt5.QtWidgets import QApplication, QMainWindow, QTextEdit, QTabWidget, QToolBar, QComboBox
from PyQt5.QtWidgets import QWidget, QAction, QVBoxLayout, QHBoxLayout
from PyQt5.QtGui import QFont, QImage, QTextCursor

try:
    import Queue as Queue
except:
    import queue as Queue

camera_num = 1
IMG_SIZE = 1920, 1080  # 640,480 or 1280,720 or 1920,1080    --
IMG_FORMAT = QImage.Format_RGB888
DISP_SCALE = 2  # Scaling factor for display image
DISP_MSEC = 50  # Delay between display cycles
CAP_API = cv2.CAP_ANY  # API: CAP_ANY or CAP_DSHOW etc...
EXPOSURE = 0  # Zero for automatic exposure
TEXT_FONT = QFont("Courier", 10)
image_queue = Queue.Queue()  # Queue to hold images
capturing = True  # Flag to indicate capturing


class MyWindow(QMainWindow):
    text_update = pyqtSignal(str)

    # Create main window
    def __init__(self, parent=None):
        # self.deBugLogPorts()
        QMainWindow.__init__(self, parent)
        self.qWidget = QWidget(self)
        # sys.stdout = self
        print("Camera number %u" % camera_num)
        print("Image size %u x %u" % IMG_SIZE)
        if DISP_SCALE > 1:
            print("Display scale %u:1" % DISP_SCALE)

        # Initialize tab screen
        self.tabs = QTabWidget()
        self.tab1 = QWidget()
        self.tab2 = QWidget()

        camera_toolbar = QToolBar("Camera X")
        camera_toolbar.setIconSize(QSize(14, 14))
        self.addToolBar(camera_toolbar)
        self.stop_capture_thread = False
        self.available_cameras = QCameraInfo.availableCameras()
        print(self.available_cameras)
        if not self.available_cameras:
            pass  # quit
        camera_selector = QComboBox()
        # print(''.join([c.description() for c in self.available_cameras]))
        camera_selector.addItems([c.description() for c in self.available_cameras])
        camera_selector.setCurrentIndex(camera_num)
        camera_selector.currentIndexChanged.connect(self.restart)

        camera_toolbar.addWidget(camera_selector)

        # Add tabs
        self.tabs.addTab(self.tab1, "Live")
        self.tabs.addTab(self.tab2, "Play Back")

        # Create first tab
        self.tab1.layout = QVBoxLayout()
        self.liveWidget = LiveWidget(self)
        self.tab1.layout.addWidget(self.liveWidget)
        self.tab1.setLayout(self.tab1.layout)

        # Create 2nd tab
        self.tab2.layout = QVBoxLayout()
        self.playBackWidget = VideoPlayer(self)
        self.tab2.layout.addWidget(self.playBackWidget)
        self.tab2.setLayout(self.tab2.layout)

        self.vLayout = QVBoxLayout()  # Window layout
        self.hBoxLayout = QHBoxLayout()

        # self.hBoxLayout.addWidget(self.imageWidget)
        self.hBoxLayout.addWidget(self.tabs)

        self.vLayout.addLayout(self.hBoxLayout)
        self.qWidget.setLayout(self.vLayout)
        self.setCentralWidget(self.qWidget)

        self.mainMenu = self.menuBar()  # Menu bar
        exitAction = QAction('&Exit', self)
        exitAction.setShortcut('Ctrl+Q')
        exitAction.triggered.connect(self.close)
        self.fileMenu = self.mainMenu.addMenu('&File')
        self.fileMenu.addAction(exitAction)

    def deBugLogPorts(self):
        is_working = True
        dev_port = 1
        working_ports = []
        available_ports = []
        while is_working:
            camera = cv2.VideoCapture(dev_port)
            camera.set(15, 0.05)
            if not camera.isOpened():
                is_working = False
                print("Port %s is not working." % dev_port)
            else:
                is_reading, img = camera.read()
                w = camera.get(3)
                h = camera.get(4)
                if is_reading:
                    print("Port %s is working and reads images (%s x %s)" % (dev_port, h, w))
                    time.sleep(1)
                    cv2.imwrite("frame%d.jpg" % dev_port, img)
                    working_ports.append(dev_port)
                else:
                    print("Port %s for camera ( %s x %s) is present but does not reads." % (dev_port, h, w))
                    available_ports.append(dev_port)
            camera.release()
            dev_port += 1
        print(str(available_ports))

    @pyqtSlot()
    def on_click(self):
        for currentQTableWidgetItem in self.tableWidget.selectedItems():
            print(currentQTableWidgetItem.row(), currentQTableWidgetItem.column(), currentQTableWidgetItem.text())

        # Start image capture & display

    def start(self):
        self.timer = QTimer(self)  # Timer to trigger display
        self.timer.timeout.connect(lambda:
                                   self.show_image(image_queue, self.liveWidget, DISP_SCALE))
        self.timer.start(DISP_MSEC)
        self.stop_capture_thread = False
        self.capture_thread = threading.Thread(target=grab_images,
                                               args=(camera_num, image_queue, lambda: self.stop_capture_thread))
        self.capture_thread.start()  # Thread to grab images

    # Restart image capture & display
    def restart(self, i):
        self.stop_capture_thread = True
        time.sleep(1)
        self.stop_capture_thread = False
        self.capture_thread = threading.Thread(target=grab_images,
                                               args=(i, image_queue, lambda: self.stop_capture_thread))
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
            img = cv2.resize(img, disp_size, interpolation=cv2.INTER_CUBIC)
        qimg = QImage(img.data, disp_size[0], disp_size[1], disp_bpl, IMG_FORMAT)
        display.setImage(qimg)

    # Handle sys.stdout.write: update text display
    def write(self, text):
        self.text_update.emit(str(text))
        with open('log.txt', 'a') as f:
            f.write(text)
            f.close()

    def flush(self):
        pass

    # Window is closing: stop video capture
    def closeEvent(self, event):
        global capturing
        capturing = False
        self.capture_thread.join()


# Grab images from the camera (separate thread)
def grab_images(cam_num, queue, stop, self=None):
    capture = cv2.VideoCapture(cam_num)
    time.sleep(0.5)  # Need this timer here for MackBookPro Camera to work
    neural_network = cv2.dnn.readNet("config/yolov4-tiny_best-5.weights", "config/yolov4-tiny-5.cfg")
    neural_network.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
    neural_network.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
    yoloVideoSelf = YoloVideoSelf()
    yoloVideoSelf.width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) + 0.5)
    yoloVideoSelf.height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) + 0.5)
    # Codec = 7634706D in HEX
    yoloVideoSelf.codec = cv2.VideoWriter_fourcc(*'mp4v')  # Be sure to use the lower case

    capture.set(cv2.CAP_PROP_FRAME_WIDTH, IMG_SIZE[0])
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, IMG_SIZE[1])
    if EXPOSURE:
        capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0)
        capture.set(cv2.CAP_PROP_EXPOSURE, EXPOSURE)
    else:
        capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
    while capturing:
        if capture.grab():
            retval, image = capture.retrieve(0)
            if image is not None and queue.qsize() < 2:
                yoloVideoSelf.processFrame(image, neural_network)
                queue.put(image)
            else:
                time.sleep(DISP_MSEC / 1000.0)
        else:
            print("Error: can't grab camera image")
            break

        if stop():
            break
    capture.release()


if __name__ == '__main__':
    app = QApplication([])
    win = MyWindow()
    win.show()
    win.setWindowTitle(VERSION)
    win.start()
    sys.exit(app.exec_())
