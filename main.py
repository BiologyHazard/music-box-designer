from exportpics import A4_VERTICAL, AUTO_SIZE, CENTER_ALIGN, export_pics

if __name__ == '__main__':
    export_pics('example.mid',
                output_pic_name='Example (page %d)',
                music_info='EXAMPLE',
                # scale=1,
                overwrite=True,
                # interpret_bpm=114,
                # remove_blank=False,
                # save_pic=True,
                # transposition=5,
                # papersize=A4_VERTICAL,
                # papersize=AUTO_SIZE,
                # ppi=300,
                # font='fonts/SourceHanSans.otf',
                heading=('打谱软件: github.com/BiologyHazard/MusicBoxDesigner', CENTER_ALIGN),
                # notemark_beat=None,
                # barcount_numerator=None,
                # barcount_startfrom=0,
                )
