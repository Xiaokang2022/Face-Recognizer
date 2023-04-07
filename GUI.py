""" 主界面 """

import os
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

import cv2
from PIL import Image, ImageTk

from constants import CASCADE, PATH
from main import __version__
from model import collect


def display_video(key: int = 0) -> None:
    """ 播放视频 """
    global cap
    Application.loading()
    clock = 0

    if Application.model:
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.read('trainner/%s.yml' % Application.model)
        face_cascade = cv2.CascadeClassifier(CASCADE)

    cap = cv2.VideoCapture(key, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    Application.camera = True
    Application.curve_update()
    Application.toplevel.destroy()
    Application.change_info(
        '正在使用模型 %s 进行人脸识别' % Application.model.split('_')[1] if Application.model else '当前未使用任何模型')

    def update(key: int = 1) -> None:
        """ 更新帧 """
        global img_main, img_head
        nonlocal clock
        if Application.camera is False:
            return Application.default_gui()
        ret, frame = cap.read()
        now = time.time()
        Application.change_fps(round(1/(now-clock)))
        clock = now
        if ret:
            frame = cv2.resize(frame, (768, 432))
            img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA))

            if Application.model:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(
                    gray, scaleFactor=1.2, minNeighbors=5)

                if len(faces):
                    x, y, w, h = faces[0]
                    _, confidence = recognizer.predict(gray[y:y+h, x:x+w])
                    confidence = 100-confidence
                    Application.canvas_main.itemconfigure(
                        'text', text='%.2f%%' % confidence if confidence > 0 else 'Unknow')
                    Application.change_ans(confidence/100)
                    Application.canvas_main.coords('rect', x, y, x+w, y+h)
                    Application.canvas_main.coords('text', x+w/2, y+h+10)
                    key = 2*228/(w+h)
                    Application.canvas_head.coords('head', -x*key, -y*key)

                img_head = ImageTk.PhotoImage(
                    img.resize((round(768*key), round(432*key))))
                Application.canvas_head.itemconfigure('head', image=img_head)

            img_main = ImageTk.PhotoImage(img)
            Application.canvas_main.itemconfigure('main', image=img_main)
            Application.canvas_main.after(10, update)
        else:
            messagebox.showerror('调用摄像头失败', '未能打开并调用摄像头数据！\n请检查是否正常！')
            Application.close_camera()
            Application.root.quit()

    update()


class ToolTip:
    """ 提示窗口 """

    def __init__(self, widget, text=''):
        self.text = text
        widget.bind('<Enter>', self.enter)
        widget.bind('<Leave>', lambda _: self.toplevel.destroy())

    def enter(self, event):
        """ 进入控件 """
        self.toplevel = tk.Toplevel()
        self.toplevel.geometry('+%d+%d' % (event.x_root+12, event.y_root+24))
        self.toplevel.overrideredirect(True)
        tk.Label(self.toplevel, text=self.text, bg='lightyellow', font=(
            '微软雅黑', 15), highlightthickness=1, highlightbackground='grey').pack()


class Application:
    """ 窗口 """

    root = tk.Tk()
    root.title('人脸识别系统 - v%s' % __version__)
    root.resizable(False, False)
    root.iconbitmap('icon.ico')
    canvas = tk.Canvas(root, width=1230, height=720, highlightthickness=0)
    canvas.pack()

    model: str = ''  # 识别模型
    camera: bool = False  # 摄像头是否打开
    select: list = []  # 表格选中的id
    name: tk.StringVar = tk.StringVar(value='test')  # 数据名称的输入值
    num: tk.IntVar = tk.IntVar(value=100)  # 数据数量的输入值
    answer: list = [0., 1.]  # 分析结果 [real百分比，fake百分比]

    INTERVAL: int = 500  # 分析图像刷新间隔 100/250/500/1000 (ms)
    DENSITY: int = 3  # 图线密集度 1/3/9/27 (px)

    def __init__(self) -> None:
        if sys.platform == 'win32':
            """ 判定是否为Windows系统 """
            from ctypes import OleDLL
            OleDLL('shcore').SetProcessDpiAwareness(1)

        style = ttk.Style()
        style.configure('.', font=('微软雅黑', 15))
        style.configure('Treeview.Heading', font=('微软雅黑', 15))
        style.configure('Treeview', font=('微软雅黑', 12))
        style.configure('my.TButton', font=('微软雅黑', 12))

        self.base_init()
        self.detail_init()
        self.load_data()
        self.root.protocol('WM_DELETE_WINDOW', self.shutdown)
        self.root.mainloop()

    @classmethod
    def loading(cls):
        """ 调用摄像头加载 """
        x, y = map(int, cls.root.geometry().split('+')[-2:])
        cls.toplevel = tk.Toplevel(cls.root)
        cls.toplevel.overrideredirect(True)
        cls.toplevel.geometry('400x120+%d+%d' % (x+615-200, y+360-60+30))
        cls.toplevel.resizable(False, False)
        cls.toplevel.focus_set()
        cls.toplevel.grab_set()
        cls.toplevel['highlightthickness'] = 1
        label = tk.Label(cls.toplevel, text='正在调用摄像头…', font=('微软雅黑', 20))
        label.place(width=400-2, y=20)
        bar = ttk.Progressbar(cls.toplevel, mode='indeterminate')
        bar.place(width=300, height=30, x=50, y=70)

        def update(ind=0):
            """ 更新进度条 """
            if cls.camera is True:
                return
            bar.configure(value=ind)
            cls.root.after(15, update, ind+1 if ind < 100 else 0)

        update()

    @classmethod
    def curve_update(cls, last=[0., 1.], lines=[]):
        """ 曲线更新 """
        if cls.camera is False or not cls.model:
            cls.canvas_curve.itemconfigure('real', text='')
            cls.canvas_curve.itemconfigure('fake', text='')
            return cls.canvas_curve.delete(*lines)
        if len(lines) >= 32*cls.DENSITY:
            cls.canvas_curve.delete(lines.pop(0))
            cls.canvas_curve.delete(lines.pop(0))
        next = cls.answer.copy()
        lines.append(cls.canvas_curve.create_line(
            433, last[1]*432+1, 433+27/cls.DENSITY, next[1]*432+1, fill='#F00', width=2))
        lines.append(cls.canvas_curve.create_line(
            433, last[0]*432+1, 433+27/cls.DENSITY, next[0]*432+1, fill='#0C0', width=2))
        cls.canvas_curve.itemconfigure(
            'real', text='Real(R) %.2f%%' % (next[0]*100))
        cls.canvas_curve.itemconfigure(
            'fake', text='Fake(G) %.2f%%' % (next[1]*100))
        for item in lines:
            cls.canvas_curve.move(item, -27/cls.DENSITY, 0)
        cls.canvas_curve.lift('real')
        cls.canvas_curve.lift('fake')
        cls.canvas_curve.lift('xy')
        cls.canvas_curve.after(cls.INTERVAL, cls.curve_update, next, lines)

    @classmethod
    def default_gui(cls) -> None:
        """ 界面恢复默认 """
        cls.canvas_head.coords('head', 1, 1)
        cls.canvas_head.itemconfigure('head', image=cls.head)
        cls.canvas_main.itemconfigure('main', image=cls.main)
        cls.canvas_main.itemconfigure('text', text='')
        cls.canvas_main.coords('rect', -1, -1, -1, -1)
        cls.change_info('摄像头未开启')
        cls.change_fps(0)

    @classmethod
    def shutdown(cls):
        """ 退出前询问 """
        if messagebox.askyesno('退出程序', '是否要退出人脸识别系统？'):
            cls.close_camera()
            cls.root.quit()

    @classmethod
    def base_init(cls):
        """ 界面框架 """
        cls.canvas.create_rectangle(-1, 690, 1281, 721, fill='#DDD', width=0)

        cls.canvas_main = tk.Canvas(
            cls.canvas, width=768, height=432, highlightthickness=1, highlightbackground='grey')
        cls.canvas_main.place(x=10, y=10)
        cls.canvas_curve = tk.Canvas(
            cls.canvas, width=432, height=432, highlightthickness=1, highlightbackground='grey')
        cls.canvas_curve.place(x=788, y=10)
        cls.canvas_head = tk.Canvas(
            cls.canvas, width=228, height=228, highlightthickness=1, highlightbackground='grey')
        cls.canvas_head.place(x=992, y=452)

        cls.notebook = ttk.Notebook(cls.canvas)
        cls.notebook.place(width=300, height=228, x=10, y=452)

        scrollbar_y = ttk.Scrollbar(cls.canvas)
        cls.treeview = ttk.Treeview(
            cls.canvas, columns=('1', '2', '3', '4'), show='headings', yscrollcommand=scrollbar_y.set, selectmode='extended')
        scrollbar_y['command'] = cls.treeview.yview
        scrollbar_y.place(height=228, x=954, y=452)
        cls.treeview.place(width=634, height=228, x=320, y=452)

    @classmethod
    def change_ans(cls, real: float = 1) -> None:
        """ 改变分析结果（当前时刻） """
        real = 0 if real < 0 else 1 if real > 1 else real
        cls.answer = [real, 1-real]

    @classmethod
    def change_fps(cls, fps: int) -> None:
        """ 改变FPS值 """
        cls.canvas_main.itemconfigure('fps', text='FPS %d' % fps)

    @classmethod
    def change_info(cls, text):
        """ 改变状态栏左侧提示文本 """
        cls.canvas.itemconfigure('info', text=text)

    @classmethod
    def treeview_add(cls, name: str) -> None:
        """ 添加 """
        num, name, now = name.split('_')
        num, now = int(num), now.replace("'", ':')
        id = str(len(cls.treeview.get_children())+1)
        cls.treeview.insert('', 'end', id=id, values=(id, now, num, name))
        cls.treeview.see(id)

    @classmethod
    def treeview_AC(cls):
        """ 清空表格 """
        if cls.camera:
            return messagebox.showwarning('清除全部', '请先关闭摄像头后再对模型进行管理')
        if messagebox.askokcancel('清除全部', '您确定清除所有模型及其源文件吗？'):
            for item in cls.treeview.get_children():
                cls.treeview.delete(item)
            for trainner in os.listdir(PATH+'/trainner'):
                os.remove(PATH+'/trainner/'+trainner)

    @classmethod
    def treeview_delete(cls, *id):
        """ 删除指定项或者选中项 """
        if cls.camera:
            return messagebox.showwarning('删除', '请先关闭摄像头后再对模型进行管理')
        try:
            if not cls.select:
                raise RuntimeError
            cls.treeview.delete(*id if id else cls.select)
        except:
            messagebox.showerror('删除失败', '未找到对应删除的项或未选中任何项！')

    @classmethod
    def curve_coords_bind(cls, event):
        """ 曲线图鼠标坐标显示 """
        text = 'X:%.1f, Y:%.1f' % (event.x/4.33, (432+1-event.y)/4.33)
        cls.canvas_curve.itemconfigure('xy', text=text)

    @classmethod
    def treeview_select_bind(cls):
        """ 表格点击事件绑定 """
        cls.select.clear()
        cls.model = ''
        for item in cls.treeview.selection():
            cls.select.append(cls.treeview.item(item, 'values')[0])
        if len(cls.select):
            now, num, name = cls.treeview.item(cls.select[0], 'values')[1:]
            cls.model = '_'.join([num, name, now]).replace(':', "'")

    @classmethod
    def switch_density(cls):
        """ 切换线条密度 """
        if cls.DENSITY == 1:
            cls.DENSITY = 3
        elif cls.DENSITY == 3:
            cls.DENSITY = 9
        elif cls.DENSITY == 9:
            cls.DENSITY = 27
        else:
            cls.DENSITY = 1
        cls.density.configure(text='线条密度 %dpx' % (27//cls.DENSITY))

    @classmethod
    def switch_interval(cls):
        """ 切换刷新间隔 """
        if cls.INTERVAL == 100:
            cls.INTERVAL = 250
        elif cls.INTERVAL == 250:
            cls.INTERVAL = 500
        elif cls.INTERVAL == 500:
            cls.INTERVAL = 1000
        else:
            cls.INTERVAL = 100
        cls.interval.configure(text='刷新间隔 %dms' % cls.INTERVAL)

    @classmethod
    def collect_and_train(cls) -> None:
        """ 收集并训练 """
        if cls.camera is True:
            return messagebox.showwarning('录入', '请先关闭摄像头后再进行数据的录入！')
        if not messagebox.askokcancel(
                '录入', '录入数据分为收集数据和训练模型两个阶段，\n请您在收集数据阶段正视摄像头'):
            return
        cls.button_save.configure(state='disabled')
        try:
            name = cls.name.get()
            num = cls.num.get()
            if not name or num < 1:
                raise RuntimeError
        except:
            messagebox.showerror('参数错误', '请检查参数设置是否正确！\n数据名称不可为空；\n数据数量必须为正数；')
            return cls.button_save.configure(state='normal')
        threading.Thread(target=collect, args=(
            name, num, cls.pb, cls.info, cls.button_save, cls.treeview_add), daemon=True).start()

    @classmethod
    def open_camera(cls) -> None:
        """ 打开摄像头 """
        cls.treeview.configure(selectmode='none')
        cls.button_opencam.configure(state='disabled')
        cls.button_closecam.configure(state='normal')
        cls.button_set.configure(state='normal')
        threading.Thread(target=display_video, daemon=True).start()

    @classmethod
    def close_camera(cls) -> None:
        """ 关闭摄像头 """
        cls.treeview.configure(selectmode='extended')
        cls.button_opencam.configure(state='normal')
        cls.button_closecam.configure(state='disabled')
        cls.button_set.configure(state='disabled')
        if cls.camera:
            cls.camera = False
            cap.release()
            cv2.destroyAllWindows()

    @classmethod
    def detail_init(cls):
        """ 界面细节 """
        # 状态栏
        cls.canvas.create_text(
            5, 705, anchor='w', font='微软雅黑', text='摄像头未开启', tags='info')
        cls.density = ttk.Button(
            cls.root, text='线条密度 9px', style='my.TButton', cursor='hand2', command=cls.switch_density)
        cls.density.place(width=120, height=30, y=690, x=1110)
        ToolTip(cls.density, '点击更换线条密度')
        cls.interval = ttk.Button(
            cls.root, text='刷新间隔 500ms', style='my.TButton', cursor='hand2', command=cls.switch_interval)
        cls.interval.place(width=140, height=30, y=690, x=970+1)
        ToolTip(cls.interval, '点击更换刷新间隔')

        # 主画布
        ToolTip(cls.canvas_main, '当前摄像头输出画面')
        cls.main = tk.PhotoImage(file='main.png')
        cls.canvas_main.create_image(384+1, 216+1, image=cls.main, tags='main')
        cls.canvas_main.create_rectangle(
            -1, -1, -1, -1, outline='springgreen', width=2, tags='rect')
        cls.canvas_main.create_text(
            -1, -1, fill='#F00', font=('微软雅黑', 15), tags='text')
        cls.canvas_main.create_text(
            10, 10, anchor='nw', font='微软雅黑', text='FPS 0', fill='springgreen', tags='fps')

        # 曲线画布
        cls.canvas_curve.bind('<Motion>', cls.curve_coords_bind)
        for i in range(1, 16):
            cls.canvas_curve.create_line(0, i*27, 432+1, i*27, fill='#CCC')
            cls.canvas_curve.create_line(i*27, 0, i*27, 432+1, fill='#CCC')
        cls.canvas_curve.create_text(
            10, 10, anchor='nw', font='微软雅黑', tags='real')
        cls.canvas_curve.create_text(
            10, 40, anchor='nw', font='微软雅黑', tags='fake')
        cls.canvas_curve.create_text(
            430, 430, anchor='se', font='微软雅黑', tags='xy')

        # 头像画布
        ToolTip(cls.canvas_head, '当前识别头像')
        cls.head = tk.PhotoImage(file='head.png')
        cls.canvas_head.create_image(
            1, 1, image=cls.head, tags='head', anchor='nw')
        cls.canvas_head.create_text(
            10, 10, anchor='nw', font='微软雅黑', text='Head', fill='springgreen')

        # 笔记本
        notebook_1 = tk.Frame(cls.notebook, highlightthickness=1,
                              highlightbackground='grey')
        notebook_2 = tk.Frame(cls.notebook, highlightthickness=1,
                              highlightbackground='grey')
        notebook_3 = tk.Frame(cls.notebook, highlightthickness=1,
                              highlightbackground='grey')
        cls.notebook.add(notebook_1, text=' 录入数据 ')
        cls.notebook.add(notebook_2, text=' 管理模型 ')
        cls.notebook.add(notebook_3, text=' 人脸识别 ')

        tk.Label(notebook_1, text='模型名称', font=('微软雅黑', 15)
                 ).place(width=80, height=30, x=10, y=10)
        tk.Label(notebook_1, text='数据数量', font=('微软雅黑', 15)
                 ).place(width=80, height=30, x=10, y=45)
        entry_name = tk.Entry(notebook_1, highlightthickness=1, highlightbackground='grey',
                              highlightcolor='#288CDB', relief='flat', font=('微软雅黑', 12), textvariable=cls.name)
        entry_name.place(width=180, height=30, x=100, y=10)
        ToolTip(entry_name, '输入录入数据的名称')
        spinbox_num = ttk.Spinbox(
            notebook_1, textvariable=cls.num, font=('微软雅黑', 12), from_=10, to=10000)
        spinbox_num.place(width=180, height=30, x=100, y=45)
        ToolTip(spinbox_num, '输入录入数据的数量')
        cls.pb = ttk.Progressbar(notebook_1, maximum=1.)
        cls.pb.place(width=270, height=25, x=10, y=80)
        cls.info = tk.Label(notebook_1, text='点击“录入”以收集数据', font='微软雅黑')
        cls.info.place(width=290, height=30, y=110)
        cls.button_save = ttk.Button(
            notebook_1, text='录  入', cursor='hand2', command=cls.collect_and_train)
        cls.button_save.place(width=150, height=40, x=70, y=145)
        ToolTip(cls.button_save, '录入当前数据')

        button_delete = ttk.Button(
            notebook_2, text='删  除', cursor='hand2', command=cls.treeview_delete)
        button_delete.pack(pady=(20, 10))
        ToolTip(button_delete, '删除当前选中的模型')
        button_AC = ttk.Button(notebook_2, text='清除全部',
                               cursor='hand2', command=cls.treeview_AC)
        button_AC.pack(pady=(0, 10))
        ToolTip(button_AC, '清除所有模型的数据')
        button_opendir = ttk.Button(
            notebook_2, text='打开模型文件夹', cursor='hand2', command=lambda: os.startfile(PATH+'/trainner'))
        button_opendir.pack()
        ToolTip(button_opendir, '打开模型文件所在的文件夹')
        tk.Label(notebook_2, text='小提示：按住Ctrl键可选中多项',
                 font=('微软雅黑', 13)).pack(side='bottom')

        cls.button_opencam = ttk.Button(
            notebook_3, text='打开摄像头', cursor='hand2', command=cls.open_camera)
        cls.button_opencam.place(width=200, height=40, x=45, y=20)
        ToolTip(cls.button_opencam, '调用并打开摄像头\n若选中了模型，则会选取对应模型进行识别')
        cls.button_closecam = ttk.Button(
            notebook_3, text='关闭摄像头', cursor='hand2', command=cls.close_camera, state='disabled')
        cls.button_closecam.place(width=200, height=40, x=45, y=70)
        ToolTip(cls.button_closecam, '关闭摄像头并释放内存')
        cls.button_set = ttk.Button(
            notebook_3, text='摄像头设置', cursor='hand2', command=lambda: cap.set(37, 0), state='disabled')
        cls.button_set.place(width=200, height=40, x=45, y=120)
        ToolTip(cls.button_set, '设置摄像头的相关属性')
        tk.Label(notebook_3, text='小提示：关闭摄像头时方可选择模型', font=(
            '微软雅黑', 12)).place(width=290, height=20, y=165)

        # 表格
        cls.treeview.bind('<ButtonRelease-1>',
                          lambda _: cls.treeview_select_bind())
        cls.treeview.column('1', anchor='center', minwidth=60, width=60)
        cls.treeview.column('2', anchor='center', minwidth=240, width=240)
        cls.treeview.column('3', anchor='center', minwidth=100, width=100)
        cls.treeview.column('4', anchor='center', minwidth=230)
        cls.treeview.heading('1', text='序号')
        cls.treeview.heading('2', text='录入时间')
        cls.treeview.heading('3', text='数据数量')
        cls.treeview.heading('4', text='模型名称')

    @classmethod
    def load_data(cls) -> None:
        """ 读取训练信息 """
        datas = os.listdir(PATH+'/trainner')
        for data in datas:
            cls.treeview_add(data[:-4])
