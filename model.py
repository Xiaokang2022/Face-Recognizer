""" 模型数据的收集及训练 """

import os
import time
from tkinter import Label, ttk

import cv2
import numpy as np
from PIL import Image

from constants import CASCADE, PATH


def collect(name: str, maxm: int, bar: ttk.Progressbar, info: Label, bt: ttk.Button, t_add) -> None:
    """ 数据收集 """
    info.configure(text='正在收集数据…')
    cap = cv2.VideoCapture(0)
    face_detector = cv2.CascadeClassifier(CASCADE)
    count = 0

    while True:
        success, img = cap.read()
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 其中gray为要检测的灰度图像，1.3为每次图像尺寸减小的比例，5为minNeighbors
        faces = face_detector.detectMultiScale(gray, 1.3, 5)

        for x, y, w, h in faces:
            count += 1
            bar.configure(value=count/maxm)
            cv2.imwrite("data/%d.jpg" % count, gray[y:y+h, x:x+w])

        if cv2.waitKey(1) == '27' or count >= maxm:
            break

    cap.release()
    cv2.destroyAllWindows()
    info.configure(text='正在训练模型…')
    t_add(train(name, maxm, bar))
    bt.configure(state='normal')
    bar.configure(value=0.)
    info.configure(text='点击“录入”以训练数据')


def train(name: str, maxm: int, bar: ttk.Progressbar) -> str:
    """ 训练 """
    now = time.strftime("%Y-%m-%d %H'%M'%S", time.localtime())
    face_samples, ids = [], []
    recog = cv2.face.LBPHFaceRecognizer_create()
    detector = cv2.CascadeClassifier(CASCADE)
    count = 0

    for path in os.listdir(PATH+'/data'):
        path = PATH+'/data/'+path
        img_np = np.array(Image.open(path).convert('L'), 'uint8')
        id = int(path.split('.')[0].split('/')[-1])
        os.remove(path)

        for x, y, w, h in detector.detectMultiScale(img_np):
            face_samples.append(img_np[y:y+h, x:x+w])
            ids.append(id)
            count += 1
            bar.configure(value=count/maxm)

    recog.train(face_samples, np.array(ids))
    name = '%d_%s_%s.yml' % (maxm, name, now)
    recog.save('trainner/'+name)
    return name[:-4]
