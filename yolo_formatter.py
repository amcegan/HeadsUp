import glob

from cv2 import cv2
import numpy as np
import time
import os
import yaml
from munch import munchify
from datetime import datetime


class YoloVideoSelf:
    def __init__(self):
        print("************  Init YoloVideoSelf ************")
        settings = munchify(yaml.safe_load(open("config/config.yml")))
        self.RECORD_FOLDER_POOR = settings.record_folder_poor
        self.RECORD_FOLDER_GOOD = settings.record_folder_good
        self.poorPostureFile = None
        self.goodPostureFile = None

        self.THRESHOLD = 0.2
        # the lower the value: the fewer bounding boxes will remain
        self.SUPPRESSION_THRESHOLD = 0.4
        self.YOLO_IMAGE_SIZE = 416
        self.startPoorPostureTimer = time.time()
        self.startGoodPostureTimer = time.time()
        self.poorPostureTimerStarted = False
        self.goodPostureTimerStarted = False

        # Video Capture
        # Width and height of frame
        self.width = None
        self.height = None
        # Define the codec and create VideoWriter object
        self.codec = None
        self.poorPostureVideoWriter = None
        self.goodPostureVideoWriter = None

        self.freezeVideoTime = 3
        self.posteriorAngle = -13
        self.anteriorAngle = 12

    def processFrame(self, frame, neural_network):
        original_width, original_height = frame.shape[1], frame.shape[0]
        #  print('Dim ' + str(original_width) + ' ' + str(original_width))
        # the image into a BLOB [0-1] RGB - BGR
        blob = cv2.dnn.blobFromImage(frame, 1 / 255, (self.YOLO_IMAGE_SIZE, self.YOLO_IMAGE_SIZE), True, crop=False)
        neural_network.setInput(blob)

        layer_names = neural_network.getLayerNames()
        # YOLO network has 3 output layer - note: these indexes are starting with 1

        # output_names = [layer_names[index[0] - 1] for index in neural_network.getUnconnectedOutLayers()]
        output_names = [layer_names[65], layer_names[77]]

        model_outputs = neural_network.forward(output_names)
        predicted_objects, bbox_locations, class_label_ids, conf_values = self.find_objects(model_outputs)
        self.show_detected_objects(frame, predicted_objects, bbox_locations, class_label_ids, conf_values,
                                   original_width / self.YOLO_IMAGE_SIZE, original_height / self.YOLO_IMAGE_SIZE)

        return frame

    def find_objects(self, model_outputs):
        bounding_box_locations = []
        class_ids = []
        confidence_values = []

        for output in model_outputs:
            for prediction in output:
                class_probabilities = prediction[5:]
                class_id = np.argmax(class_probabilities)
                confidence = class_probabilities[class_id]

                if confidence > self.THRESHOLD:
                    w, h = int(prediction[2] * self.YOLO_IMAGE_SIZE), int(prediction[3] * self.YOLO_IMAGE_SIZE)
                    # the center of the bounding box (we should transform these values)
                    x, y = int(prediction[0] * self.YOLO_IMAGE_SIZE - w / 2), int(
                        prediction[1] * self.YOLO_IMAGE_SIZE - h / 2)
                    bounding_box_locations.append([x, y, w, h])
                    class_ids.append(class_id)
                    confidence_values.append(float(confidence))

        box_indexes_to_keep = cv2.dnn.NMSBoxes(bounding_box_locations, confidence_values, self.THRESHOLD,
                                               self.SUPPRESSION_THRESHOLD)

        return box_indexes_to_keep, bounding_box_locations, class_ids, confidence_values

    def show_detected_objects(self, img, bounding_box_ids, all_bounding_boxes, class_ids, confidence_values,
                              width_ratio,
                              height_ratio):
        ear = (0, 0)
        nose = (0, 0)
        earFound = False
        noseFound = False
        for index in bounding_box_ids:
            bounding_box = all_bounding_boxes[index]
            x1, y1, w, h = int(bounding_box[0]), int(bounding_box[1]), int(bounding_box[2]), int(bounding_box[3])
            # we have to transform the locations adn coordinates because the resized image
            x = int(x1 * width_ratio)
            y = int(y1 * height_ratio)
            w = int(w * width_ratio)
            h = int(h * height_ratio)

            # OpenCV deals with BGR blue green red (255,0,0) then it is the blue color
            # we are not going to detect every objects just PERSON and CAR
            if class_ids[index] == 1 or class_ids[index] == 2:
                noseFound = True
                nose = (x + (w // 2), y + (h // 2))
                cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 255), 3)
                class_with_confidence = 'NOSE ' + str(int(confidence_values[index] * 100)) + '%'
                cv2.putText(img, class_with_confidence, (x, y - 10), cv2.FONT_HERSHEY_PLAIN, 2, (0, 0, 255), 2)

            if class_ids[index] == 0:
                earFound = True
                ear = (x + (w // 2), y + (h // 2))
                cv2.rectangle(img, (x, y), (x + w, y + h), (255, 255, 255), 3)
                class_with_confidence = 'EAR ' + str(int(confidence_values[index] * 100)) + '%'
                cv2.putText(img, class_with_confidence, (x, y - 10), cv2.FONT_HERSHEY_PLAIN, 2, (255, 255, 255), 2)

        if earFound & noseFound:
            slope = self.slopeOf(ear[0], ear[1], nose[0], nose[1])
            angle = np.arctan(slope) * 57.2958
            cv2.putText(img, 'Angle :' + str(int(angle)), (1500, 1000), cv2.FONT_HERSHEY_PLAIN, 3, (255, 255, 255), 3)
            cv2.line(img, nose, ear, (255, 255, 255), 3)

            now = datetime.now().time()  # time object
            current_time = now.strftime("%H:%M:%S")

            poorPosture = angle < self.posteriorAngle or angle > self.anteriorAngle
            if poorPosture:
                # print('Angle is ' + str(int(angle)) + '  at ' + current_time)
                if not self.poorPostureTimerStarted:
                    self.poorPostureTimerStarted = True
                    self.startPoorPostureTimer = time.time()
                    print("************ Timer started now =", current_time + '************')
                    # os.makedirs(self.folder)  # important step
                    self.poorPostureFile = datetime.now().strftime('%Y-%m-%d__%H-%M-%S') + '.mp4'
                    self.poorPostureVideoWriter = cv2.VideoWriter(
                        os.path.join(self.RECORD_FOLDER_POOR, self.poorPostureFile),
                        self.codec, 10.0, (self.width, self.height))
                timedOut = time.time() - self.startPoorPostureTimer > 5
                # print('timed out ' + str(timedOut))
                if timedOut and self.poorPostureTimerStarted:
                    # sound alarm, reset timer,  release video writer
                    self.handleBadPostureAlarm(current_time, img)
            else:  # NOT angle < -12 or angle > 14
                if self.poorPostureTimerStarted:  # We were in poor posture
                    self.handleReturnedToGoodPosture()
                # Good posture
                # self.startGoodPostureTimer = time.time()
                if self.goodPostureVideoWriter is None:
                    self.createGoodPostureWriter1()

        if self.poorPostureTimerStarted:
            self.poorPostureVideoWriter.write(img)
        else:
            if self.goodPostureVideoWriter is None:
                self.createGoodPostureWriter2()
            self.goodPostureVideoWriter.write(img)
            if time.time() - self.startGoodPostureTimer > 10:
                self.goodPostureVideoWriter.release()
                self.goodPostureVideoWriter = None
                self.startGoodPostureTimer = time.time()  # Reset timer
                print("************ released createGoodPostureWriter ************")

    def createGoodPostureWriter1(self):
        print("************ createGoodPostureWriter 1 ************")

        self.deleteExcessGoodVideos()
        self.startGoodPostureTimer = time.time()
        self.goodPostureFile = datetime.now().strftime('%Y-%m-%d__%H-%M-%S') + '.mp4'
        self.goodPostureVideoWriter = cv2.VideoWriter(os.path.join(self.RECORD_FOLDER_GOOD, self.goodPostureFile),
                                                      self.codec, 10.0, (self.width, self.height))
        if self.goodPostureVideoWriter is None:
            print("************ Failed to create createGoodPostureWriter 1 ************")

    def createGoodPostureWriter2(self):
        print("************ createGoodPostureWriter 2 ************")
        self.deleteExcessGoodVideos()

        self.startGoodPostureTimer = time.time()
        self.goodPostureFile = datetime.now().strftime('%Y-%m-%d__%H-%M-%S') + '.mp4'
        self.goodPostureVideoWriter = cv2.VideoWriter(os.path.join(self.RECORD_FOLDER_GOOD, self.goodPostureFile),
                                                      self.codec, 10.0, (self.width, self.height))
        if self.goodPostureVideoWriter is None:
            print("************ Failed to create createGoodPostureWriter 2 ************")

    def handleReturnedToGoodPosture(self):
        self.poorPostureTimerStarted = False
        self.poorPostureVideoWriter.release()
        self.poorPostureVideoWriter = None
        try:
            recordFolderPath = os.path.dirname(os.path.abspath(__file__)) + self.RECORD_FOLDER_POOR
            # debug  print(str(os.path.join(recordFolderPath, self.recordFileName)))
            if os.path.isfile(os.path.join(self.RECORD_FOLDER_POOR, self.poorPostureFile)):
                os.remove(os.path.join(self.RECORD_FOLDER_POOR, self.poorPostureFile))
        except OSError as e:  ## if failed, report it back to the user ##
            print("Error: %s - %s." % (e.filename, e.strerror))
        print('********  reset timer ************')

    def handleBadPostureAlarm(self, current_time, img):
        print("************ Timed out ", current_time + '************')
        cv2.putText(img, 'Heads-Up', (1500, 1000), cv2.FONT_HERSHEY_PLAIN, 3, (255, 255, 0), 3)
        file = "3.wav"
        os.system("afplay " + file)
        print('*************** wav *******************')
        time.sleep(self.freezeVideoTime)
        self.poorPostureTimerStarted = False
        self.poorPostureVideoWriter.release()
        self.poorPostureVideoWriter = None

    def slopeOf(self, x1, y1, x2, y2):
        m = (y2 - y1) / (x2 - x1)
        return m

    def deleteExcessGoodVideos(self):
        currentDir = os.path.dirname(os.path.abspath(__file__))
        list_of_files = glob.glob(currentDir + '/' + self.RECORD_FOLDER_GOOD + '/*')
        full_path = ["{0}".format(x) for x in list_of_files]

        while len(list_of_files) > 5:
            oldest_file = min(full_path, key=os.path.getctime)
            list_of_files.remove(oldest_file)
            os.remove(oldest_file)