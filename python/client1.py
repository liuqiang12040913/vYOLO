#!python3

'''
##############################
### Receive Video stream #####
### from Android client #######
### Use yolo to do detect ####
## (return a message to the mobile device) ##
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
import time
import threading
import ctypes


HOST=''
PORT=9001
BUFFER_SIZE = 256


if __name__ == "__main__":

    sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    sock.connect((HOST,PORT))
    img = cv2.imread('data/dog.jpg')
    while True:
        start_time = time.time()
        img_data = cv2.imencode('.jpg', img)[1]
        print("img data: ", len(img_data), type(img_data))
        buffers = struct.pack("!i",len(img_data))
        print("img size: ", len(buffers), type(buffers))
        send_data = buffers + img_data.tostring()
        print("send data: ", len(send_data), type(send_data))
        sock.sendall(send_data)
        sock.recv(BUFFER_SIZE)
        print(str(time.time() - start_time))
        

