import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Self
from bisect import bisect_left, bisect_right

from mido import MidiFile, tick2second
from PIL import Image, ImageDraw, ImageFont
from pydantic import (BaseModel, FilePath, FiniteFloat, NonNegativeFloat,
                      PositiveFloat, PositiveInt, field_serializer,
                      field_validator)
from pydantic_extra_types.color import Color

from .consts import (COL_WIDTH, GRID_WIDTH, LEFT_BORDER, LENGTH_MM_PER_BEAT,
                     MIN_TRIGGER_SPACING, MUSIC_BOX_30_NOTES_PITCH, NOTES,
                     RIGHT_BORDER)
from .emid import EmidFile
from .fmp import FmpBpmTimeSignatureMark, FmpCommentMark, FmpEndMark, FmpFile
from .utils import (draw_circle, get_text_height, mm_to_pixel, pixel_to_mm,
                    pos_mm_to_pixel)

default_format: str = '{asctime} [{levelname}] {module} | {message}'
default_date_format: str = '%Y-%m-%d %H:%M:%S'
logging.basicConfig(level=logging.DEBUG, format=default_format, datefmt=default_date_format, style='{')

DEFAULT_BPM: float = 120


@dataclass(frozen=True)
class Note:
    pitch: int
    '''音高'''
    time: float
    '''节拍数'''


# class Notes(list[Note]):
#     @classmethod
#     def load_from_file(cls,
#                        file: str | Path,
#                        *,
#                        transposition: int = 0,
#                        interpret_bpm: float | None = None,
#                        remove_blank: bool = False,
#                        ) -> Self:
#         if isinstance(file, str):
#             file = Path(file)
#         if file.suffix == '.emid':
#             return cls.load_from_emid(EmidFile.load_from_file(file))
#         elif file.suffix == '.fmp':
#             return cls.load_from_fmp(FmpFile.load_from_file(file))
#         elif file.suffix == '.mid':
#             return cls.load_from_midi(MidiFile(file))

#     @staticmethod
#     def _get_notes_from_emid(emid_file: EmidFile) -> list[tuple[int, float]]:
#         return [(note.pitch, note.time)
#                 for track in emid_file.tracks
#                 for note in track.notes]

#     @staticmethod
#     def _get_notes_from_fmp(fmp_file: FmpFile) -> list[tuple[int, float]]:
#         return [(note.pitch, note.time)
#                 for track in fmp_file.tracks
#                 for note in track.notes]

#     @classmethod
#     def load_from_emid(cls, emid_file: EmidFile) -> Self:
#         self: Self = cls()
#         for track in emid_file.tracks:
#             for note in track.notes:
#                 if note in MUSIC_BOX_30_NOTES_PITCH:
#                     self.append(Note(MUSIC_BOX_30_NOTES_PITCH.index(note.pitch)))
#         return self

#     @classmethod
#     def load_from_fmp(cls, fmp_file: FmpFile) -> Self:
#         ...

#     @classmethod
#     def load_from_midi(cls, midi_File: MidiFile) -> Self:
#         ...


class DraftSettings(BaseModel, arbitrary_types_allowed=True):
    # 页面设置
    anti_alias_rate: PositiveFloat = 1
    '''抗锯齿比例，设置为`1`以关闭抗锯齿，该数值越大，抗锯齿效果越好，但是算力消耗也越大'''
    ppi: float = 300
    '''图片分辨率，单位像素/英寸'''
    paper_size: tuple[float, float] | None = (210, 297)
    '''页面大小（宽，高），单位毫米，设置为`None`则会使得图片只有一栏并且自动调整大小'''
    margins: tuple[float, float, float, float] = (6.0, 6.0, 0, 0)
    '''页面边距（上，下，左，右），单位毫米'''
    background: Color | Image.Image = Color('white')
    '''背景颜色或图片，可传入`PIL.Image.Image`对象'''
    font_path: FilePath = Path('fonts/SourceHanSans.otf')
    '''字体文件路径'''
    heading: str = ''
    '''页面顶部文字'''
    heading_anchor: str = 'ms'
    '''页面顶部文字对齐方式，见https://pillow.readthedocs.io/en/stable/handbook/text-anchors.html'''
    heading_size: NonNegativeFloat = 2.0
    '''页面顶部文字大小，单位毫米，将以`round(heading_size * ppi / MM_PER_INCH)`转变为像素大小'''

    # 标题设置
    show_info: bool = True
    '''信息显示总开关'''
    show_title: bool = True
    '''是否显示标题'''
    title_align: Literal['left', 'center', 'right'] = 'center'
    '''标题对齐方式'''
    title_height: FiniteFloat | None = None
    '''标题到页面上边的距离，单位毫米，设置为`None`则自动'''
    title_size: NonNegativeFloat = 4.0
    '''标题文字大小，单位毫米，将以`round(heading_size * ppi / MM_PER_INCH)`转变为像素大小'''
    show_subtitle: bool = True
    '''是否显示副标题'''
    subtitle_align: Literal['left', 'center', 'right'] = 'center'
    '''副标题对齐方式'''
    subtitle_height: FiniteFloat | None = None
    '''副标题到页面上边的距离，单位毫米，设置为`None`则自动'''
    subtitle_size: NonNegativeFloat = 3.0
    '''副标题文字大小，单位毫米，将以`round(heading_size * ppi / MM_PER_INCH)`转变为像素大小'''
    show_tempo: bool = True
    '''是否显示乐曲速度信息'''
    tempo_format: str = '{bpm:.0f}bpm'
    '''乐曲速度信息的格式化字符串，支持参数`bpm`'''
    show_note_count: bool = True
    '''是否显示音符数量和纸带长度信息'''
    note_count_format: str = '{note_count} notes / {meter:.2f}m'
    '''音符数量和纸带长度信息的格式化字符串，支持参数`note_count`, `meter`, `centimeter`和`milimeter`'''
    tempo_note_count_size: NonNegativeFloat = 3.0
    '''乐曲速度信息、音符数量和纸带长度信息文字大小，单位毫米，将以`round(tempo_note_count_size * ppi / MM_PER_INCH)`转变为像素大小'''

    # 谱面设置
    body_height: FiniteFloat | None = None
    '''谱面到页面上边的距离，单位毫米，设置为`None`则自动'''
    note_color: Color = Color('black')
    '''音符颜色'''
    note_radius: NonNegativeFloat = 1.14
    '''音符半径，单位毫米'''
    show_column_num: bool = True
    '''是否在每栏右上角显示`music_info`以及栏号'''
    show_bar_num: bool = True
    '''是否显示小节号'''
    time_signature_numerator_override: PositiveInt | None = None
    '''每小节多少拍，设置为`None`则从文件中读取，读取不到则认为每小节4拍'''
    bar_num_start: int = 1
    '''小节号从几开始'''
    show_custom_watermark: bool = False
    '''是否显示自定义水印'''
    custom_watermark: str = '自定义水印'
    '''自定义水印内容'''
    horizonal_line_color: Color = Color('black')
    '''横向线条颜色'''
    half_beat_line_type: Literal['solid', 'dashed'] = 'solid'
    '''半拍线条类型，`'solid'`表示实线，`dashed`表示虚线'''
    half_beat_line_color: Color = Color('gray')
    '''半拍线条颜色'''
    vertical_line_color: Color = Color('black')
    '''竖向线条颜色'''

    @field_validator('background')
    @classmethod
    def validator(cls, value) -> Color | Image.Image:
        if isinstance(value, Image.Image):
            return value
        try:
            return Color(value)
        except Exception:
            return Image.open(value)

    @field_serializer('background')
    @classmethod
    def serializer(cls, value):
        if isinstance(value, Color):
            return value.original()
        return value.filename

    # def calc_page_info(self) -> None:
    #     (self.up_margin,
    #      self.down_margin,
    #      self.left_margin,
    #      self.right_margin
    #      ) = self.margins
    #     if self.paper_size is None:
    #         ...
    #     else:
    #         self.page_width, self.page_height = self.paper_size
    #         self.cols_per_page = math.floor(
    #             (self.page_width - self.left_margin - self.right_margin) / COL_WIDTH)
    #         self.first_col_x = self.left_margin + (self.page_width - self.left_margin) / 2 - self.cols_per_page * COL_WIDTH / 2


class ImageList(list[Image.Image]):
    file_name: str

    def save(self, file_name: str | None = None) -> None:
        if file_name is None:
            file_name = self.file_name
        for i, image in enumerate(self):
            image.save(file_name.format(i))


class Draft:
    def __init__(self,
                 notes: list[Note] | None = None,
                 title: str = '',
                 subtitle: str = '',
                 music_info: str = '',
                 bpm: float = 120,
                 ) -> None:
        self.notes: list[Note] = notes if notes is not None else []
        self.title: str = title
        self.subtitle: str = subtitle
        self.music_info: str = music_info
        self.bpm: float = bpm

    @classmethod
    def load_from_file(cls,
                       file: str | Path,
                       transposition: int = 0,
                       bpm: float | None = None,
                       remove_blank: bool = True,
                       ) -> Self:
        logging.info(f'Loading from {file!r}...')
        if not isinstance(file, Path):
            file = Path(file)
        if file.suffix == '.emid':
            self: Self = cls.load_from_emid(EmidFile.load_from_file(file),
                                            transposition=transposition,
                                            remove_blank=remove_blank,
                                            bpm=bpm if bpm is not None else DEFAULT_BPM)
            self.title = file.stem
        elif file.suffix == '.fmp':
            self = cls.load_from_fmp(FmpFile.load_from_file(file))
        elif file.suffix == '.mid':
            return cls.load_from_midi(MidiFile(file))
        else:
            raise ValueError("The file extension must be '.emid', '.fmp' or '.mid'.")
        return self

    @classmethod
    def load_from_emid(cls,
                       emid_file: EmidFile,
                       transposition: int = 0,
                       remove_blank: bool = True,
                       bpm: float = DEFAULT_BPM,
                       ) -> Self:
        self: Self = cls(bpm=bpm)
        for track in emid_file.tracks:
            for note in track.notes:
                if note.pitch + transposition in MUSIC_BOX_30_NOTES_PITCH:
                    self.notes.append(Note(note.pitch + transposition, note.time))
                else:
                    logging.warning(f'Note {note.pitch + transposition} in bar {math.floor(note.time / 4) + 1} is out of range')
        if remove_blank:
            self.remove_blank()
        return self

    @classmethod
    def load_from_fmp(cls,
                      fmp_file: FmpFile,
                      transposition: int = 0,
                      remove_blank: bool = True,
                      bpm: float | None = None,
                      ) -> Self:
        self: Self = cls()
        for track in fmp_file.tracks:
            for note in track.notes:
                if note.velocity == 0:
                    continue
                if note.pitch + transposition in MUSIC_BOX_30_NOTES_PITCH:
                    self.notes.append(Note(note.pitch + transposition, note.time))
                else:
                    logging.warning(f'Note {note.pitch + transposition} in bar {math.floor(note.time / 4) + 1} is out of range')
        self.bpm = bpm if bpm is not None else fmp_file.bpm
        self.title = fmp_file.title
        self.subtitle = fmp_file.subtitle
        self.music_info = fmp_file.title
        if remove_blank:
            self.remove_blank()
        return self

    @classmethod
    def load_from_midi(cls,
                       midi_file: MidiFile,
                       transposition: int = 0,
                       remove_blank: bool = True,
                       bpm: float | None = None,
                       ) -> Self:
        self: Self = cls()
        if midi_file.filename is not None:
            if isinstance(midi_file.filename, (str, Path)):
                try:
                    path = Path(midi_file.filename)
                    stem: str = path.stem
                    self.title = stem
                except Exception:
                    self.title = str(midi_file.filename)
            else:
                try:
                    self.title = str(midi_file.filename)
                except Exception:
                    pass

        ticks_per_beat: int = midi_file.ticks_per_beat

        tempo_events: list[tuple[int, int]] = []
        time_passed: list[float] = []
        if bpm is not None:
            for track in midi_file.tracks:
                midi_tick: int = 0
                for message in track:
                    midi_tick += message.time
                    if message.type == 'set_tempo':
                        tempo_events.append((message.tempo, midi_tick))

            real_time: float = 0.0
            for i in range(len(tempo_events)):
                tempo: int = 0 if i == 0 else tempo_events[i-1][0]
                delta_midi_tick: int = tempo_events[i][1] - tempo_events[i-1][1]
                real_time += tick2second(delta_midi_tick, ticks_per_beat, tempo)
                time_passed.append(real_time)

        for track in midi_file.tracks:
            midi_tick: int = 0
            for message in track:
                midi_tick += message.time
                if message.type != 'note_on':
                    continue
                if message.velocity == 0:
                    continue
                pitch: int = message.note + transposition
                if pitch in MUSIC_BOX_30_NOTES_PITCH:
                    if bpm is None:
                        time: float = midi_tick / ticks_per_beat
                    else:
                        i: int = bisect_left(tempo_events, midi_tick, key=lambda tempo_event: tempo_event[1])
                        tempo, tick = tempo_events[i]
                        real_time = time_passed[i] + tick2second(
                            midi_tick - tick, ticks_per_beat, tempo)
                        time = real_time / 60 * bpm
                        self.notes.append(Note(MUSIC_BOX_30_NOTES_PITCH.index(pitch), time))  # 添加note
                else:  # 如果超出音域
                    logging.warning(
                        f'Note {pitch} in bar {math.floor(midi_tick / ticks_per_beat / 4) + 1} is out of range')
        self.notes.sort(key=lambda note: note.time)
        if remove_blank:
            self.remove_blank()
        return self

    def remove_blank(self) -> None:
        if not self.notes:
            return
        self.notes.sort(key=lambda note: note.time)
        blank: int = math.floor(self.notes[0].time)
        self.notes = [Note(note.pitch, note.time - blank) for note in self.notes]

    def export_pics(self,
                    title: str | None = None,
                    subtitle: str | None = None,
                    music_info: str | None = None,
                    settings: DraftSettings | None = None,
                    scale: float = 1,
                    ) -> ImageList:
        if title is None:
            title = self.title
        if subtitle is None:
            subtitle = self.subtitle
        if music_info is None:
            music_info = self.music_info
        if settings is None:
            settings = DraftSettings()

        self.notes.sort(key=lambda note: note.time)
        if self.notes:
            length: float = self.notes[-1].time * LENGTH_MM_PER_BEAT * scale
        else:
            length = 0

        logging.info(f'Notes: {len(self.notes)}')
        logging.info(f'Length: {length / 1000:.2f}m')
        logging.info('Drawing...')

        # 计算纸张大小
        up_margin, down_margin, left_margin, right_margin = settings.margins
        rows: int = math.floor(length / LENGTH_MM_PER_BEAT) + 1
        if settings.paper_size is None:
            cols: int = 1
            rows_per_col: int = rows
            cols_per_page: int = cols
            page_width: float = left_margin + COL_WIDTH + right_margin
            page_height: float = up_margin + rows_per_col * LENGTH_MM_PER_BEAT + down_margin
            pages: int = 1
            last_page_cols: int = 1
        else:
            page_width, page_height = settings.paper_size
            rows_per_col = math.floor((page_height - up_margin - down_margin) / LENGTH_MM_PER_BEAT)
            cols_per_page = math.floor((page_width - left_margin - right_margin) / COL_WIDTH)
            cols = math.floor(rows / rows_per_col) + 1
            pages = math.ceil(cols / cols_per_page)
            last_page_cols = cols - (pages - 1) * cols_per_page
        first_col_x: float = page_width / 2 - cols_per_page * COL_WIDTH / 2

        # 构建图片列表
        image_size: tuple[int, int] = pos_mm_to_pixel((page_width, page_height), settings.ppi)
        images: list[Image.Image] = [Image.new('RGBA', image_size, '#00000000') for _ in range(pages)]
        draws: list[ImageDraw.ImageDraw] = [ImageDraw.Draw(image) for image in images]
        images_anti_alias: list[Image.Image] = [Image.new('RGBA', image_size, '#00000000') for _ in range(pages)]
        draws_anti_alias: list[ImageDraw.ImageDraw] = [ImageDraw.Draw(image) for image in images_anti_alias]

        # 分隔线
        for i, draw in enumerate(draws):
            num: int = cols_per_page if i != pages - 1 else last_page_cols
            for j in range(num + 1):
                draw.line((pos_mm_to_pixel((first_col_x + j * COL_WIDTH, up_margin), settings.ppi),
                           pos_mm_to_pixel((first_col_x + j * COL_WIDTH, page_height - down_margin), settings.ppi)),
                          'black', 1)

        y: float = up_margin
        if settings.show_info:
            # 标题
            if settings.show_title:
                if settings.title_align == 'left':
                    title_x: float = first_col_x + LEFT_BORDER
                    title_anchor: str = 'la'
                elif settings.title_align == 'center':
                    title_x = first_col_x + COL_WIDTH / 2
                    title_anchor: str = 'ma'
                elif settings.title_align == 'right':
                    title_x = first_col_x + COL_WIDTH - RIGHT_BORDER
                    title_anchor: str = 'ra'
                else:
                    raise ValueError

                if settings.title_height is not None:
                    y = up_margin + settings.title_height

                title_font: ImageFont.FreeTypeFont = ImageFont.truetype(
                    str(settings.font_path), round(mm_to_pixel(settings.title_size, settings.ppi)))
                logging.debug('Drawing title...')
                draws[0].text(pos_mm_to_pixel((title_x, y), settings.ppi),
                              title, 'black', title_font, title_anchor, align=settings.title_align)
                y += pixel_to_mm(get_text_height(title, title_font), settings.ppi)

            # 副标题
            if settings.show_subtitle:
                if settings.subtitle_align == 'left':
                    subtitle_x: float = first_col_x + LEFT_BORDER
                    subtitle_anchor: str = 'la'
                elif settings.subtitle_align == 'center':
                    subtitle_x = first_col_x + COL_WIDTH / 2
                    subtitle_anchor: str = 'ma'
                elif settings.subtitle_align == 'right':
                    subtitle_x = first_col_x + COL_WIDTH - RIGHT_BORDER
                    subtitle_anchor: str = 'ra'
                else:
                    raise ValueError

                if settings.subtitle_height is not None:
                    y = up_margin + settings.subtitle_height

                subtitle_font: ImageFont.FreeTypeFont = ImageFont.truetype(
                    str(settings.font_path), round(mm_to_pixel(settings.subtitle_size, settings.ppi)))
                logging.debug('Drawing subtitle...')
                draws[0].text(pos_mm_to_pixel((subtitle_x, y), settings.ppi),
                              subtitle, 'black', subtitle_font, subtitle_anchor, align=settings.subtitle_align)
                y += pixel_to_mm(get_text_height(subtitle, subtitle_font), settings.ppi)

            # 乐曲速度信息 & 音符数量和纸带长度信息
            if settings.show_tempo or settings.show_note_count:
                tempo_note_count_font: ImageFont.FreeTypeFont = ImageFont.truetype(
                    str(settings.font_path), round(mm_to_pixel(settings.tempo_note_count_size, settings.ppi)))

                tempo_text: str = settings.tempo_format.format(bpm=self.bpm) if settings.show_tempo else ''
                note_count_text: str = (settings.note_count_format.format(note_count=len(self.notes),
                                                                          meter=length / 1000,
                                                                          centimeter=length / 100,
                                                                          milimeter=length)
                                        if settings.show_note_count else '')
                combined_text: str = f'{tempo_text}{note_count_text}'

                if settings.body_height is not None:
                    y = up_margin + settings.body_height
                else:
                    y += pixel_to_mm(get_text_height(combined_text, tempo_note_count_font), settings.ppi)
                first_col_rows: int = math.floor((page_height - down_margin - y) / LENGTH_MM_PER_BEAT)

                if settings.show_tempo:
                    logging.debug('Drawing tempo...')
                    draws[0].text(pos_mm_to_pixel((first_col_x + LEFT_BORDER, y), settings.ppi),
                                  tempo_text, 'black', tempo_note_count_font, 'ld')

                if settings.show_note_count:
                    logging.debug('Drawing note count...')
                    draws[0].text(pos_mm_to_pixel((first_col_x + COL_WIDTH - RIGHT_BORDER, y), settings.ppi),
                                  note_count_text, 'black', tempo_note_count_font, 'rd')

        first_row_y: float = page_height / 2 - rows_per_col * LENGTH_MM_PER_BEAT / 2
        if settings.body_height is not None:
            y = up_margin + settings.body_height
        else:
            if not (settings.show_info
                    and (settings.show_title
                         or settings.show_subtitle
                         or settings.show_tempo
                         or settings.show_note_count)):
                y = first_row_y

        for i in range(first_col_rows + 1):
            draws[0].line(
                (pos_mm_to_pixel((first_col_x + LEFT_BORDER, y + i * LENGTH_MM_PER_BEAT), settings.ppi),
                 pos_mm_to_pixel((first_col_x + COL_WIDTH - RIGHT_BORDER, y + i * LENGTH_MM_PER_BEAT), settings.ppi)),
                settings.horizonal_line_color.as_rgb(), 1
            )
        for i in range(NOTES):
            draws[0].line(
                (pos_mm_to_pixel((first_col_x + LEFT_BORDER + i * GRID_WIDTH,
                                  y), settings.ppi),
                 pos_mm_to_pixel((first_col_x + LEFT_BORDER + i * GRID_WIDTH,
                                  y + first_col_rows * LENGTH_MM_PER_BEAT), settings.ppi)),
                settings.vertical_line_color.as_rgb(), 1
            )

        for page, draw in enumerate(draws):
            for col in range(cols_per_page):
                if page == 0 and col == 0:
                    continue
                if page == pages - 1 and col >= last_page_cols:
                    continue
                for row in range(rows_per_col + 1):
                    draw.line(
                        (pos_mm_to_pixel((first_col_x + col * COL_WIDTH + LEFT_BORDER,
                                          first_row_y + row * LENGTH_MM_PER_BEAT), settings.ppi),
                         pos_mm_to_pixel((first_col_x + col * COL_WIDTH + COL_WIDTH - RIGHT_BORDER,
                                          first_row_y + row * LENGTH_MM_PER_BEAT), settings.ppi)),
                        settings.horizonal_line_color.as_rgb(), 1
                    )
                for line in range(NOTES):
                    draw.line(
                        (pos_mm_to_pixel((first_col_x + col * COL_WIDTH + LEFT_BORDER + line * GRID_WIDTH,
                                          first_row_y), settings.ppi),
                         pos_mm_to_pixel((first_col_x + col * COL_WIDTH + LEFT_BORDER + line * GRID_WIDTH,
                                          first_row_y + rows_per_col * LENGTH_MM_PER_BEAT), settings.ppi)),
                        settings.vertical_line_color.as_rgb(), 1
                    )

        for note in self.notes:
            col: int = math.floor((note.time * scale - first_col_rows + rows_per_col) / rows_per_col)
            page: int = col // cols_per_page
            col_in_page: int = col % cols_per_page
            row_in_col: float = (note.time * scale - first_col_rows + rows_per_col) % rows_per_col
            try:
                index: int = MUSIC_BOX_30_NOTES_PITCH.index(note.pitch)
            except:
                continue
            draw_circle(
                draws[page],
                pos_mm_to_pixel(
                    (first_col_x + col_in_page * COL_WIDTH + LEFT_BORDER + index * GRID_WIDTH,
                     first_row_y + row_in_col * LENGTH_MM_PER_BEAT),
                    settings.ppi * settings.anti_alias_rate),
                mm_to_pixel(settings.note_radius, settings.ppi * settings.anti_alias_rate),
                'black',
            )

        if isinstance(settings.background, Image.Image):
            backgrond_image: Image.Image = settings.background
        else:
            backgrond_image = Image.new('RGBA', image_size, settings.background.as_rgb())

        return ImageList(Image.alpha_composite(backgrond_image, image) for image in images)
