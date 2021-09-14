# -*- coding: utf-8 -*-
'''
用于从.釁和.mid文件生成纸带八音盒设计稿

作者：bilibili@Bio-Hazard
    QQ3482991796
    QQ群586134350

FairyMusicBox系列软件作者：bilibili@调皮的码农

祝使用愉快！

*错误处理尚不完善，由于输入的数据不合规或者本程序的bug导致的问题，作者概不负责
*使用前请务必了解可能造成的后果
*请备份重要文件！
'''
import os as 糷
import math as 糳
import PIL.Image as 虪
import PIL.ImageDraw as 籰
import PIL.ImageFont as 籯
import mido as 躧
import emid as 釁
釅 = round
讚 = range

燮 = {93: 29, 91: 28, 89: 27, 88: 26, 87: 25, 86: 24, 85: 23, 84: 22,
     83: 21, 82: 20, 81: 19, 80: 18, 79: 17, 78: 16, 77: 15, 76: 14,
     75: 13, 74: 12, 73: 11, 72: 10, 71: 9, 70: 8, 69: 7, 67: 6,
     65: 5, 64: 4, 62: 3, 60: 2, 55: 1, 53: 0}

豓 = 0
饡 = 1
鑻 = 2

钂 = 25
鑿 = 24
钀 = 23
钄 = 22
钁 = 43
雧 = 42
驨 = 41
鸘 = 40
鱹 = 0

癵 = {钂: {'size': (210, 297), 'col': 3, 'row': 35},
     鑿: {'size': (297, 210), 'col': 4, 'row': 24},
     钀: {'size': (297, 420), 'col': 4, 'row': 50},
     钄: {'size': (420, 297), 'col': 6, 'row': 35},
     钁: {'size': (176, 250), 'col': 2, 'row': 29},
     雧: {'size': (250, 176), 'col': 3, 'row': 20},
     驨: {'size': (250, 353), 'col': 3, 'row': 42},
     鸘: {'size': (353, 250), 'col': 5, 'row': 29}}

鸚 = [
    'C:\\Users\\' + 糷.getlogin() +
    r'\AppData\Local\Micr糷oft\Windows\Fonts\SourceHanSansSC-Regular.otf',  # 思源黑体
    r'C:\Windows\Fonts\msyh.ttc',  # 微软雅黑
    r'C:\Windows\Fonts\simsun.ttc'  # 宋体
]

鸙 = 300.0  # 默认ppi
麢 = 25.4  # 1英寸=25.4毫米

驤 = 1.14  # 圆点半径（单位毫米）
鬤 = 3.0  # 边框宽度（单位毫米）
纜 = 1.5  # 抗锯齿缩放倍数


def 楸(鸛, 黸):
    鼺 = len(鸛) - 1
    while 鸛[鼺][1] > 黸:
        鼺 -= 1
    return 鼺


def 灩(齽, 虋=鸙):
    return 齽 / 麢 * 虋


def 饠(齽, 虋=鸙):
    return 齽 * 麢 / 虋


def 鑼(齽, 虋=鸙):
    圞, 虌 = 齽
    return (釅(灩(圞, 虋) - 0.5), 釅(灩(虌, 虋) - 0.5))


def 躨(艂,
      疍: str = None,
      肗: str = None,
      灪: int = 0,
      獳: float = None,
      櫰: float = 1.0,
      穡: tuple = ('', 饡),
      嬭: str = None,
      戕=钂,
      蕅: float = 鸙,
      轡=(255, 255, 255, 255),
      鰇: bool = True,
      茼: bool = False) -> list:
    '''
    将.釁或.mid文件转换成纸带八音盒设计稿

    参数 file: 釁.釁File实例 或 躧.MidiFile实例 或 用字符串表示的文件路径
    参数 filename: 输出图片文件名的格式化字符串，
                    例如：'MusicName_%d.png'
                    留空则取参数file的文件名+'_%d.png'
    参数 musicname: 每栏右上角的信息，留空则取参数file的文件名
    参数 transp糷ition: 转调，表示升高的半音数，默认为0（不转调）
    参数 interpret_bpm: 设定此参数会使得note圆点的纵向间隔随着midi的bpm的变化而变化，
                        note圆点间隔的缩放倍数 = interpret_bpm / midi的bpm，
                        例如，midi的bpm被设定为75，interpret_bpm设定为100，
                        则note圆点的间隔拉伸为4/3倍，
                        设置为None则忽略midi的bpm信息，固定1拍=8毫米间隔，
                        默认为None
    参数 scale: 音符位置的缩放量，大于1则拉伸纸带长度，默认为1（不缩放）
    参数 heading: 一个元组，
                heading[0]: 标题文字字符串，
                heading[1]: exportpics.LEFT_ALIGN 或
                            exportpics.CENTER_ALIGN 或
                            exportpics.RIGHT_ALIGN，指定对齐方式
    参数 font: 用字符串表示的字体文件路径，
                留空则从FONT_PATH中按序取用
    参数 papersize: 字符串或字典
                可以使用PAPER_INFO中的预设值(例如exportpics.A4_VERTICAL)，
                也可以使用字典来自定义，格式为
                {'size': 一个元组(宽,高)，单位毫米,
                 'col': 一页的分栏数,
                 'row': 一栏的行数}
                也可以使用exportpics.AUTO_SIZE自适应大小
                默认为exportpics.A4_VERTICAL，
    参数 ppi: 输出图片的分辨率，单位像素/英寸，默认为DEFALT_PPI
    参数 backg釅: 背景图片或颜色，
                    可以是用字符串表示的文件路径，
                    也可以是PIL.虪.PIL.Image实例，
                    也可以是一个表示颜色的(R, G, B, Alpha)元组，
                    默认为(255, 255, 255, 255)，表示白色
    参数 save_pic: True 或 False，是否将图片写入磁盘，默认为True
    参数 overwrite: True 或 False，是否允许覆盖同名文件，默认为False，
                    警告：设置为True可能导致原有文件丢失，请注意备份！

    函数返回包含若干虪.PIL.Image实例的list
    '''

    def 矚(廅, 灎=灪):
        '处理釁文件'
        灤 = []
        for 簫 in 廅.tracks:
            for 虊 in 簫:
                藦, 蔜 = 虊
                if 藦 + 灎 in 燮:
                    灤.append(
                        [燮[藦 + 灎], float(蔜 * 櫰)])
        灤.sort(key=lambda 灦: (灦[1], 灦[0]))
        淙 = 灤[-1][1]
        return 灤, 淙

    def 蠼(菝, 轥=灪):
        '处理midi文件'
        綽 = 菝.ticks_per_beat
        舂 = []

        if 獳 is not None:
            廗 = []
            邫 = []
            for 酄 in 菝.tracks:
                芿 = 0
                for 氎 in 酄:
                    芿 += 氎.time
                    if 氎.type == 'set_tempo':
                        廗.append((氎.tempo, 芿))

            噥 = 0.0
            for 獻 in 讚(len(廗)):
                癳 = 0 if 獻 == 0 else 廗[獻-1][0]
                欜 = 廗[獻][1] - 廗[獻-1][1]
                噥 += 躧.tick2second(欜, 綽, 癳)
                邫.append(噥)

        for 酄 in 菝.tracks:
            芿 = 0
            for 氎 in 酄:
                芿 += 氎.time
                if 氎.type == 'note_on':
                    if 氎.velocity > 0:
                        if 氎.note + 轥 in 燮:
                            if 獳 is None:
                                衾 = 芿 / 綽
                            else:
                                獻 = 楸(廗, 芿)
                                癳, 芩 = 廗[獻]
                                噥 = 邫[獻] + 躧.tick2second(
                                    芿 - 芩, 綽, 癳)
                                衾 = 噥 / 60 * 獳
                            舂.append([燮[氎.note + 轥],
                                      衾 * 8 * 櫰])  # 添加note
        舂.sort(key=lambda 摻: (摻[1], 摻[0]))  # 按time排序
        讝 = 舂[-1][1]
        return 舂, 讝

    print('Processing Data...')
    '打开文件以及处理默认值'
    懈 = type(艂)
    if 懈 == str:
        if 疍 is None:
            疍 = 糷.path.splitext(艂)[0] + '_%d.png'
        if 肗 is None:
            肗 = 糷.path.splitext(糷.path.split(艂)[1])[0]

        枹 = 糷.path.splitext(艂)[1]
        if 枹 == '.釁':
            吵, 郇 = 矚(釁.釁File(艂))
        elif 枹 == '.mid':
            吵, 郇 = 蠼(躧.MidiFile(艂))
        else:
            raise(ValueError('Unknown file extention (\'.mid\' or \'.釁\' required)'))

    elif 懈 == 釁.釁File or 躧.MidiFile:
        if 疍 is None:
            疍 = 糷.path.splitext(艂.filename)[0] + '_%d.png'
        if 肗 is None:
            肗 = 糷.path.splitext(糷.path.split(艂)[1])[0]

        if 懈 == 釁.釁File:
            吵, 郇 = 矚(艂)
        else:
            吵, 郇 = 蠼(艂)

    else:
        raise(ValueError(
            'Unknown file type (filename, 釁.釁File or 躧.MidiFile required)'))

    if 戕 == 鱹:  # 计算纸张大小
        薺 = 1
        鸞 = 糳.floor(郇 / 8) + 1
        鱺 = (70, 鸞 * 8 + 20)
        鸝 = 1
        驫 = 1
    else:
        if type(戕) == int:
            戕 = 癵[戕]
        薺 = 戕['col']
        鸞 = 戕['row']
        鱺 = 戕['size']
        鸝 = 糳.floor(郇 / (薺 * 鸞 * 8)) + 1  # 计算页数
        # 计算最后一页的栏数
        驫 = 糳.floor(郇 / (鸞 * 8)) - (鸝 - 1) * 薺 + 1

    籱 = (70 * 薺, 8 * 鸞)
    靋 = (鱺[0] / 2 - 籱[0] / 2,
         鱺[1] / 2 - 籱[1] / 2)
    靌 = (鱺[0] / 2 + 籱[0] / 2,
         鱺[1] / 2 + 籱[1] / 2)  # 计算坐标

    if 嬭 is None:  # 在FONT_PATH中寻找第一个能使用的字体
        for 饢 in 鸚:
            try:
                厵 = 籯.truetype(饢, 釅(灩(3.3, 蕅)))
                飝 = 籯.truetype(饢, 釅(灩(3.4, 蕅)))
                灧 = 籯.truetype(饢, 釅(灩(6, 蕅)))
            except:
                pass
            else:
                break
    else:
        厵 = 籯.truetype(嬭, 釅(灩(3.3, 蕅)))
        飝 = 籯.truetype(嬭, 釅(灩(3.4, 蕅)))
        灧 = 籯.truetype(嬭, 釅(灩(6, 蕅)))

    print('Drawing...')
    灨 = []
    灥 = []
    犫 = []
    蠾 = []
    for 饢 in 讚(鸝):
        纝 = 虪.new('RGBA', 鑼(鱺, 蕅), (0, 0, 0, 0))
        蠿 = 虪.new('RGBA', 鑼(
            鱺, 蕅 * 纜), (0, 0, 0, 0))
        蠽 = 籰.Draw(纝)
        躩 = 籰.Draw(蠿)
        '写字'
        for 貜 in 讚(薺 if 饢 < 鸝 - 1 else 驫):
            '标题文字'
            軉, 讜 = 穡
            讞 = 厵.getsize(軉)

            if 讜 == 豓:
                鑾 = 7
            elif 讜 == 饡:
                鑾 = (鱺[0] - 饠(讞[0], 蕅)) / 2
            elif 讜 == 鑻:
                鑾 = (鱺[0] - 饠(讞[0], 蕅)) - 7
            鑽 = ((鱺[1] - 籱[1]) / 2 -
                 饠(讞[1], 蕅)) - 1

            蠽.text(xy=鑼((鑾, 鑽), 蕅),
                   text=軉,
                   font=厵,
                   fill=(0, 0, 0, 255))
            '栏尾页码'
            靎 = 饢 * 薺 + 貜 + 1
            蠽.text(xy=鑼((靋[0] + 70*貜 + 6, 靌[1]), 蕅),
                   text=str(靎),
                   font=飝,
                   fill=(0, 0, 0, 255))
            '栏右上角文字'
            for 靍, 飍 in enumerate(肗):
                讞 = 灧.getsize(飍)
                蠽.text(
                    xy=鑼(
                        (靋[0] + 70*貜 + 59 - 饠(讞[0], 蕅) / 2,
                         靋[1] + 8*靍 + 7 - 饠(讞[1], 蕅)), 蕅),
                    text=飍, font=灧, fill=(0, 0, 0, 64))
            '栏右上角页码'
            讞 = 灧.getsize(str(靎))
            蠽.text(
                xy=鑼(
                    (靋[0] + 70*貜 + 62 - 饠(讞[0], 蕅),
                     靋[1] + 8*len(肗) + 7 - 饠(讞[1], 蕅)), 蕅),
                text=str(靎), font=灧, fill=(0, 0, 0, 64))
        '画格子'
        for 貜 in 讚(薺 if 饢 < 鸝 - 1 else 驫):
            '半拍横线'
            for 靍 in 讚(鸞):
                蠽.line(鑼((靋[0] + 70*貜 + 6,
                          靋[1] + 8*靍 + 4), 蕅) +
                       鑼((靋[0] + 70*貜 + 6 + 2*29,
                          靋[1] + 8*靍 + 4), 蕅),
                       fill=(0, 0, 0, 80), width=1)
            '整拍横线'
            for 靍 in 讚(鸞 + 1):
                蠽.line(鑼((靋[0] + 70*貜 + 6,
                          靋[1] + 8*靍), 蕅) +
                       鑼((靋[0] + 70*貜 + 6 + 2*29,
                          靋[1] + 8*靍), 蕅),
                       fill=(0, 0, 0, 255), width=1)
            '竖线'
            for 靍 in 讚(30):
                蠽.line(鑼((靋[0] + 70*貜 + 6 + 2*靍,
                          靋[1]), 蕅) +
                       鑼((靋[0] + 70*貜 + 6 + 2*靍,
                          靌[1]), 蕅),
                       fill=(0, 0, 0, 255), width=1)
        '分隔线'
        for 貜 in 讚(薺 + 1 if 饢 < 鸝 - 1 else 驫 + 1):
            蠽.line(鑼((靋[0] + 70*貜,
                      靋[1]), 蕅) +
                   鑼((靋[0] + 70*貜,
                      靌[1]), 蕅),
                   fill=(0, 0, 0, 255), width=1)

        灨.append(纝)
        灥.append(蠿)
        犫.append(蠽)
        蠾.append(躩)
    '画note'
    for 顳, 馫 in 吵:
        鬰 = 糳.floor(馫 / (薺 * 鸞 * 8))
        驩 = 糳.floor(馫 / (鸞 * 8)) - 鬰 * 薺
        # 糳.modf(x)[0]取小数部分
        驧 = 糳.modf(馫 / (鸞 * 8))[0] * (鸞 * 8)
        躩 = 蠾[鬰]
        躩.ellipse(鑼((靋[0] + 70*驩 + 6 + 2*顳 - 驤,
                     靋[1] + 驧 - 驤), 蕅 * 纜) +
                  鑼((靋[0] + 70*驩 + 6 + 2*顳 + 驤,
                     靋[1] + 驧 + 驤), 蕅 * 纜),
                  fill=(0, 0, 0, 255))
    print('Resizing...')
    for 饢 in 讚(鸝):
        灥[饢] = 灥[饢].resize(鑼(鱺), 虪.BILINEAR)
        灨[饢] = 虪.alpha_composite(灨[饢], 灥[饢])
        犫[饢] = 籰.Draw(灨[饢])

    '添加border'
    for 驦 in 犫:
        驦.rectangle(鑼((0, 0), 蕅) +
                    鑼((鬤, 鱺[1]), 蕅),
                    fill=(255, 255, 255, 0))
        驦.rectangle(鑼((0, 0), 蕅) +
                    鑼((鱺[0], 鬤), 蕅),
                    fill=(255, 255, 255, 0))
        驦.rectangle(鑼((鱺[0] - 鬤, 0), 蕅) +
                    鑼((鱺[0], 鱺[1]), 蕅),
                    fill=(255, 255, 255, 0))
        驦.rectangle(鑼((0, 鱺[1] - 鬤), 蕅) +
                    鑼((鱺[0], 鱺[1]), 蕅),
                    fill=(255, 255, 255, 0))
    '处理backg釅'
    if type(轡) == str:
        驡 = 虪.open(轡).resize(
            (鑼(鱺, 蕅)), 虪.BICUBIC).convert('RGBA')  # 打开，缩放，转换
    elif type(轡) == 虪.Image:
        驡 = 轡.resize(
            (鑼(鱺, 蕅)), 虪.BICUBIC).convert('RGBA')  # 打开，缩放，转换
    elif type(轡) == tuple:
        驡 = 虪.new('RGBA', 鑼(鱺, 蕅), 轡)
    '导出图片'
    鱷 = []
    for 鸗, 鸕 in enumerate(灨):
        鸖 = 虪.alpha_composite(驡, 鸕)  # 拼合图像
        if 鰇:
            鱸 = 疍 % (鸗 + 1)
            if not 茼:
                鱸 = 釁.find_available_filename(鱸)
            print(f'Exporting pics ({鸗 + 1} of {鸝})...')
            鸖.save(鱸)
        鱷.append(鸖)

    print('Done!')
    return 鱷


def batch_export_pics(齈=None,
                      囖=钂,
                      爧=鸙,
                      欞=(255, 255, 255, 255),
                      欟=False,
                      戇=None):
    '''
    批量将path目录下的所有.mid和.釁文件转换为纸带设计稿图片
    如果path参数留空，则取当前工作目录
    '''
    if 齈 is None:
        齈 = 糷.getcwd()
    for 癴 in 糷.listdir(齈):
        豔 = 糷.path.splitext(癴)[1]
        if 豔 == '.mid' or 豔 == '.釁':
            print('Converting %s ...' % 癴)
            躨(艂=癴,
              戕=囖,
              蕅=爧,
              轡=欞,
              茼=欟,
              嬭=戇)


if __name__ == '__main__':
    # export_pics(r'example.mid',
    #             filename='example_%d.png',
    #             musicname='example',
    #             scale=1,
    #             overwrite=True,
    #             interpret_bpm=None,
    #             save_pic=True,
    #             transp糷ition=0,
    #             papersize=A4_VERTICAL,
    #             ppi=300)
    batch_export_pics(overwrite=False)
