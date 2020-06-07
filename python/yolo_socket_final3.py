#!python3

'''
##############################
### Receive Video stream #####
### from Android client #######
### Use yolo to do detect ####
## (Display camera frames) ##
##############################
'''
from ctypes import *
import math
import random
import os
import socket
import time
import cv2
import numpy as np
from PIL import Image
import sys
import pickle
import struct
import timeit
import threading
import Queue

#f = open('/home/nvidia/Desktop/haoxin/whx.txt','w+')
#f2 = open('/home/nvidia/Desktop/haoxin/whx1.txt','w+')
os.environ['GLOG_minloglevel'] = '2' 

HOST=''
PORT=8820

working_dir = "/db"
output_dir = os.path.join(working_dir, "output")
car_output_dir = os.path.join(output_dir, "car_output")

def sample(probs):
    s = sum(probs)
    probs = [a/s for a in probs]
    r = random.uniform(0, 1)
    for i in range(len(probs)):
        r = r - probs[i]
        if r <= 0:
            return i
    return len(probs)-1

def c_array(ctype, values):
    arr = (ctype*len(values))()
    arr[:] = values
    return arr

class BOX(Structure):
    _fields_ = [("x", c_float),
                ("y", c_float),
                ("w", c_float),
                ("h", c_float)]

class DETECTION(Structure):
    _fields_ = [("bbox", BOX),
                ("classes", c_int),
                ("prob", POINTER(c_float)),
                ("mask", POINTER(c_float)),
                ("objectness", c_float),
                ("sort_class", c_int)]


class IMAGE(Structure):
    _fields_ = [("w", c_int),
                ("h", c_int),
                ("c", c_int),
                ("data", POINTER(c_float))]

class METADATA(Structure):
    _fields_ = [("classes", c_int),
                ("names", POINTER(c_char_p))]

    
lib = CDLL("/home/nvidia/darknet/libdarknet.so", RTLD_GLOBAL)
lib.network_width.argtypes = [c_void_p]
lib.network_width.restype = c_int
lib.network_height.argtypes = [c_void_p]
lib.network_height.restype = c_int

predict = lib.network_predict
predict.argtypes = [c_void_p, POINTER(c_float)]
predict.restype = POINTER(c_float)

set_gpu = lib.cuda_set_device
set_gpu.argtypes = [c_int]

make_image = lib.make_image
make_image.argtypes = [c_int, c_int, c_int]
make_image.restype = IMAGE

get_network_boxes = lib.get_network_boxes
get_network_boxes.argtypes = [c_void_p, c_int, c_int, c_float, c_float, POINTER(c_int), c_int, POINTER(c_int)]
get_network_boxes.restype = POINTER(DETECTION)

make_network_boxes = lib.make_network_boxes
make_network_boxes.argtypes = [c_void_p]
make_network_boxes.restype = POINTER(DETECTION)

free_detections = lib.free_detections
free_detections.argtypes = [POINTER(DETECTION), c_int]

free_ptrs = lib.free_ptrs
free_ptrs.argtypes = [POINTER(c_void_p), c_int]

network_predict = lib.network_predict
network_predict.argtypes = [c_void_p, POINTER(c_float)]

reset_rnn = lib.reset_rnn
reset_rnn.argtypes = [c_void_p]

load_net = lib.load_network
load_net.argtypes = [c_char_p, c_char_p, c_int]
load_net.restype = c_void_p

do_nms_obj = lib.do_nms_obj
do_nms_obj.argtypes = [POINTER(DETECTION), c_int, c_int, c_float]

do_nms_sort = lib.do_nms_sort
do_nms_sort.argtypes = [POINTER(DETECTION), c_int, c_int, c_float]

free_image = lib.free_image
free_image.argtypes = [IMAGE]

letterbox_image = lib.letterbox_image
letterbox_image.argtypes = [IMAGE, c_int, c_int]
letterbox_image.restype = IMAGE

load_meta = lib.get_metadata
lib.get_metadata.argtypes = [c_char_p]
lib.get_metadata.restype = METADATA

load_image = lib.load_image_color
load_image.argtypes = [c_char_p, c_int, c_int]
load_image.restype = IMAGE

rgbgr_image = lib.rgbgr_image
rgbgr_image.argtypes = [IMAGE]

predict_image = lib.network_predict_image
predict_image.argtypes = [c_void_p, IMAGE]
predict_image.restype = POINTER(c_float)

#def classify(net, meta, im):
#    out = predict_image(net, im)
#    res = []
#    for i in range(meta.classes):
#        res.append((meta.names[i], out[i]))
#    res = sorted(res, key=lambda x: -x[1])
#    return res

### modified ###
def recImage(client,data,q,result):
    while True:
        buf = ''
        while len(buf)<4:
            buf += client.recv(4-len(buf))
        size = struct.unpack('!i', buf)[0]
        print "receiving %d bytes" % size
        while len(data) < size:
            data += client.recv(4096)
        frame_data = data[:size]
        data = data[size:]
        imgdata = np.fromstring(frame_data, dtype='uint8')
        decimg = cv2.imdecode(imgdata,1)
        q.put(decimg)
        print ("frame finish offloading")
        if len(result):
            print "result not null"
            showPicResult(result,decimg)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        else:
            print "result null"
            #cv2.imshow('Haoxin Detection Window', decimg)
            #if cv2.waitKey(1) & 0xFF == ord('q'):
            #    break


def detect(net, meta, image, thresh=.5, hier_thresh=.5, nms=.45):
    #check if image is an OpenCV frame
    if isinstance(image, np.ndarray):
        # GET C,H,W, and DATA values
        print ('1')
        img = image.transpose(2, 0, 1)
        c, h, w = img.shape[0], img.shape[1], img.shape[2]
        nump_data = img.ravel() / 255.0
        nump_data = np.ascontiguousarray(nump_data, dtype=np.float32)

        # make c_type pointer to numpy array
        ptr_data = nump_data.ctypes.data_as(POINTER(c_float))

        # make IMAGE data type
        im = IMAGE(w=w, h=h, c=c, data=ptr_data)

    else:
        im = load_image(image, 0, 0)
        print ('2')

    stime = time.time()
    num = c_int(0)
    pnum = pointer(num)
    predict_image(net, im)
    dets = get_network_boxes(net, im.w, im.h, thresh, hier_thresh, None, 0, pnum)
    num = pnum[0]
    if (nms): do_nms_obj(dets, num, meta.classes, nms);

    res = []
    for j in range(num):
        for i in range(meta.classes):
            if dets[j].prob[i] > 0:
                b = dets[j].bbox
                calssnamess = meta.names[i].decode('UTF-8')
                res.append((calssnamess, dets[j].prob[i], (b.x, b.y, b.w, b.h)))
    res = sorted(res, key=lambda x: -x[1])
    #free_image(im)
    free_detections(dets, num)
    return res

# display the pic after detecting
def showPicResult(r,im):
    for i in range(len(r)):
        x1=r[i][2][0]-r[i][2][2]/2
        y1=r[i][2][1]-r[i][2][3]/2
        x2=r[i][2][0]+r[i][2][2]/2
        y2=r[i][2][1]+r[i][2][3]/2

        cv2.rectangle(im,(int(x1),int(y1)),(int(x2),int(y2)),(0,255,0),1)
        #putText
        x3 = int(x1+5)
        y3 = int(y1-10)
        font = cv2.FONT_HERSHEY_SIMPLEX
        if ((x3<=im.shape[0]) and (y3>=0)):
            cv2.putText(im, str(r[i][0]), (x3,y3), font, 1, (0,255,0) , 1)
        else:
            cv2.putText(im, str(r[i][0]), (int(x1),int(y1+6)), font, 1, (0,255,0) , 1)
    cv2.imshow('Haoxin Detection Window', im)


if __name__ == "__main__":
    detect_net = load_net("./cfg/yolov3.cfg", "yolov3.weights", 0)
    detect_meta = load_meta("cfg/coco.data")
    
    s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    print ('Socket created')

    s.bind((HOST,PORT))
    print ('Socket bind complete')
    s.listen(10)
    print ('Socket now listening')

    client,addr=s.accept()
    print ("Get new socket")

    #winname1 = "Detection Window"
    #cv2.namedWindow(winname1)

    data = b''
    frameID = 1
    result = []
    starttime = time.time()

    #q = Queue.Queue()
    q = Queue.LifoQueue()
    t = threading.Thread(target = recImage,args=(client,data,q,result))
    t.setDaemon(True)
    t.start()

    while True:
        if not q.empty():
            decimg = q.get()
            result = detect(detect_net, detect_meta, decimg, thresh=0.1)
#            decimg0 = q.get()
#            showPicResult(result,decimg0)
#            if cv2.waitKey(1) & 0xFF == ord('q'):
#                break
            print ("DETECT", result)


#    fr = 0
#    while cap.isOpened():

#        ret, frame = cap.read()
#        
#        #RUN OBJECT DETECTION ON FRAME
#        result = detect(detect_net, detect_meta, frame, thresh=0.5)
#        print ("DETECT", result)
#        draw_results(result, frame)
##        print "frameID: ", fr
##        fr += 1
#        cv2.imshow('frame', frame)
#        if cv2.waitKey(1) & 0xFF == ord('q'):
#            break
