from picamera.array import PiRGBArray
from picamera import PiCamera
import time
import cv2
import argparse
import imutils
import datetime
from threading import Thread
import time

class PiVideoStream:
    def __init__(self, resolution=(320, 240), framerate=60):
        # initialize the camera and stream
        self.camera = PiCamera()
        self.camera.resolution = resolution
        self.camera.framerate = framerate

        # Set ISO to the desired value
        self.camera.iso = 400
        # Wait for the automatic gain control to settle
        time.sleep(2)
        # Now fix the values
        self.camera.shutter_speed = self.camera.exposure_speed
        self.camera.exposure_mode = 'off'
        g = self.camera.awb_gains
        self.camera.awb_mode = 'off'
        self.camera.awb_gains = g

        self.rawCapture = PiRGBArray(self.camera, size=resolution)
        self.stream = self.camera.capture_continuous(self.rawCapture,
            format="bgr", use_video_port=True)

        # initialize the frame and the variable used to indicate
        # if the thread should be stopped
        self.frame = None
        self.stopped = False

    def start(self):
        # start the thread to read frames from the video stream
        Thread(target=self.update, args=()).start()
        return self

    def update(self):
        # keep looping infinitely until the thread is stopped
        for f in self.stream:
            # grab the frame from the stream and clear the stream in
            # preparation for the next frame
            self.frame = f.array
            self.rawCapture.truncate(0)

            # if the thread indicator variable is set, stop the thread
            # and resource camera resources
            if self.stopped:
                self.stream.close()
                self.rawCapture.close()
                self.camera.close()
                return

    def read(self):
        # return the frame most recently read
        return self.frame

    def stop(self):
        # indicate that the thread should be stopped
        self.stopped = True

# construct the argument parser and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("-a", "--min-area", type=int, default=500, help="minimum area size")
args = vars(ap.parse_args())

# initialize the first frame in the video stream
firstFrame = None

vs = PiVideoStream().start()
time.sleep(2.0)

score = 0
start = None
rank = []
rate = 0

# capture frames from the camera
while True:
    image = vs.read()

    rate += 1

    # process raw image
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (21, 21), 0)

    # if the first frame is None, initialize it
    if firstFrame is None:
        firstFrame = gray
        continue

    # compute the absolute difference between the current frame and first frame
    frameDelta = cv2.absdiff(firstFrame, gray)
    thresh = cv2.threshold(frameDelta, 25, 255, cv2.THRESH_BINARY)[1]

    # dilate the thresholded image to fill in holes, then find contours on thresholded image
    thresh = cv2.dilate(thresh, None, iterations=2)
    (_, cnts, _) = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # state
    max = 0
    contour = None

    # loop over the contours
    for c in cnts:
        area = cv2.contourArea(c)

        # skip small areas
        if area < args["min_area"]:
            continue

        # get biggest area
        if max < area:
            contour = c

    # draw contour
    if contour is not None:
        (x, y, w, h) = cv2.boundingRect(contour)
        cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)
        s = 480 - (y + h)
        if s > score:
            score = s

        if start is None and score > 0:
            start = time.time()

    elif start is not None:
        if time.time() - start > 5:
            print("done")
            start = None
            name = input("Great score " + str(score) + "! What is your name?\n")

            if name != "":
                rank.append((score, name))

                rank.sort(key=lambda tup: tup[0], reverse=True)
                rank = rank[:10]

            score = 0

    # drawing
    if score > 0:
        cv2.putText(image, "Rankin  ({})".format(score), (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255))
    else:
        cv2.putText(image, "Ranking", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255))

    for i in range(len(rank)):
        cv2.putText(image, "{} - {} ({})".format(i + 1, rank[i][1], rank[i][0]), (10, 40 + 20 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255))

    cv2.putText(image, str(rate), (10, image.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)

    # show the frame and record if the user presses a key
    cv2.imshow("Main", image)
    #cv2.imshow("Thresh", thresh)
    #cv2.imshow("Frame Delta", frameDelta)

    # if the `q` key was pressed, break from the loop
    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
        break

# cleanup
cv2.destroyAllWindows()
vs.stop()
