from exportpics import *
from emid import *
if __name__ == '__main__':
    export_pics(r"D:\ChenXu\Musics\纸带八音盒\铃儿响叮当\铃儿响叮当.mid",
                # filename=r"D:\ChenXu\Musics\纸带八音盒\碎月\碎月\碎月_%d.png",
                # musicname=r"樱树街道",
                scale=1,
                overwrite=True,
                # interpret_bpm=115,
                # save_pic=True,
                # transposition=0,
                # papersize=A4_VERTICAL,
                # papersize=AUTO_SIZE,
                # ppi=300,
                # font='simsun.ttc',
                heading=(
                    '作者: Bio-Hazard (B站同名)  请勿用于商业用途  打谱软件: github.com/BiologyHazard/MusicBoxDesigner', CENTER_ALIGN)
                )
    # emid.emid2midi("D:\ChenXu\Musics\纸带八音盒\Flower Dance\花之舞 短-汪汪.emid")
