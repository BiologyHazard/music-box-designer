import logging
import math
from bisect import bisect_left
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Self

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
    heading_size: NonNegativeFloat = 3.0
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
    '''标题文字大小，单位毫米，将以`round(title_size * ppi / MM_PER_INCH)`转变为像素大小'''
    show_subtitle: bool = True
    '''是否显示副标题'''
    subtitle_align: Literal['left', 'center', 'right'] = 'center'
    '''副标题对齐方式'''
    subtitle_height: FiniteFloat | None = None
    '''副标题到页面上边的距离，单位毫米，设置为`None`则自动'''
    subtitle_size: NonNegativeFloat = 3.0
    '''副标题文字大小，单位毫米，将以`round(subtitle_size * ppi / MM_PER_INCH)`转变为像素大小'''
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
    show_column_info: bool = True
    '''是否在每栏右上角显示`music_info`以及栏号'''
    show_bar_num: bool = True
    '''是否显示小节号'''
    beats_per_bar_override: PositiveInt | None = None
    '''每小节多少拍，设置为`None`则从文件中读取，读取不到则认为每小节4拍'''
    bar_num_start: int = 1
    '''小节号从几开始'''
    show_custom_watermark: bool = False
    '''是否显示自定义水印'''
    custom_watermark: str = '自定义水印'
    '''自定义水印内容'''
    whole_beat_line_color: Color = Color('black')
    '''整拍线条颜色'''
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
        try:
            return value.filename
        except Exception:
            raise Exception(f'Failed to serialize background of value {value}')


class ImageList(list[Image.Image]):
    file_name: str

    def save(self, file_name: str | None = None) -> None:
        if file_name is None:
            file_name = self.file_name
        for i, image in enumerate(self):
            logging.info(f'Saving image {i+1} of {len(self)}...')
            image.save(file_name.format(i+1))


class Draft:
    INFO_SPACING: float = 1.0
    COLUMN_INFO_SIZE: float = 6.0

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
            self.title = self.music_info = file.stem
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
        self.title = self.music_info = fmp_file.title
        self.subtitle = fmp_file.subtitle
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
                    self.title = self.music_info = stem
                except Exception:
                    self.title = self.music_info = str(midi_file.filename)
            else:
                try:
                    self.title = self.music_info = str(midi_file.filename)
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

        up_margin, down_margin, left_margin, right_margin = settings.margins
        y: float = up_margin
        if settings.show_info:
            if settings.show_title:
                if settings.title_height is not None:
                    y = up_margin + settings.title_height
                title_y: float = y
                title_font: ImageFont.FreeTypeFont = ImageFont.truetype(
                    str(settings.font_path), round(mm_to_pixel(settings.title_size, settings.ppi)))
                y += pixel_to_mm(get_text_height(title, title_font), settings.ppi)

            if settings.show_subtitle:
                if settings.subtitle_height is not None:
                    y = up_margin + settings.subtitle_height
                subtitle_y: float = y
                subtitle_font: ImageFont.FreeTypeFont = ImageFont.truetype(
                    str(settings.font_path), round(mm_to_pixel(settings.subtitle_size, settings.ppi)))
                y += pixel_to_mm(get_text_height(subtitle, subtitle_font), settings.ppi)

            if settings.show_tempo or settings.show_note_count:
                tempo_note_count_font: ImageFont.FreeTypeFont = ImageFont.truetype(
                    str(settings.font_path), round(mm_to_pixel(settings.tempo_note_count_size, settings.ppi)))
                if settings.show_tempo:
                    try:
                        tempo_text: str = settings.tempo_format.format(bpm=self.bpm)
                    except Exception:
                        tempo_text = '{bpm:.0f}bpm'.format(bpm=self.bpm)
                else:
                    tempo_text = ''

                if settings.show_note_count:
                    try:
                        note_count_text: str = settings.note_count_format.format(
                            note_count=len(self.notes),
                            meter=length / 1000,
                            centimeter=length / 100,
                            milimeter=length
                        )
                    except Exception:
                        note_count_text = '{note_count} notes / {meter:.2f}m'.format(
                            note_count=len(self.notes),
                            meter=length / 1000,
                            centimeter=length / 100,
                            milimeter=length
                        )
                else:
                    note_count_text = ''

                combined_text: str = f'{tempo_text}{note_count_text}'
                if settings.body_height is None:
                    y += pixel_to_mm(get_text_height(combined_text, tempo_note_count_font), settings.ppi)

            if settings.show_title or settings.show_subtitle or settings.show_tempo or settings.show_note_count:
                y += Draft.INFO_SPACING

        if settings.body_height is not None:
            body_y: float = up_margin + settings.body_height
        else:
            body_y = y

        # 计算纸张大小
        rows: int = math.floor(length / LENGTH_MM_PER_BEAT) + 1
        if settings.paper_size is not None:
            page_width, page_height = settings.paper_size
            rows_per_col: int = math.floor((page_height - up_margin - down_margin) / LENGTH_MM_PER_BEAT)
            cols_per_page: int = math.floor((page_width - left_margin - right_margin) / COL_WIDTH)
            first_col_rows: int = max(math.floor((page_height - down_margin - body_y) / LENGTH_MM_PER_BEAT), 0)
            cols: int = (rows + rows_per_col - first_col_rows) // rows_per_col + 1
            pages: int = math.ceil(cols / cols_per_page)
            last_page_cols: int = cols - (pages - 1) * cols_per_page
        else:
            cols = last_page_cols = cols_per_page = pages = 1
            rows_per_col = first_col_rows = rows
            page_width: float = left_margin + COL_WIDTH + right_margin
            page_height: float = body_y + rows * LENGTH_MM_PER_BEAT + down_margin
        first_col_x: float = page_width / 2 - cols_per_page * COL_WIDTH / 2
        first_row_y: float = page_height / 2 - rows_per_col * LENGTH_MM_PER_BEAT / 2
        next_body_y: float = first_row_y + math.ceil((body_y - first_row_y) / LENGTH_MM_PER_BEAT) * LENGTH_MM_PER_BEAT
        if next_body_y + first_col_rows * LENGTH_MM_PER_BEAT + down_margin <= page_height:
            body_y = next_body_y

        logging.info(f'Notes: {len(self.notes)}')
        logging.info(f'Length: {length / 1000:.2f}m')
        logging.info(f'Cols: {cols}')
        logging.info(f'Pages: {pages}')

        # 构建图片列表
        image_size: tuple[int, int] = pos_mm_to_pixel((page_width, page_height), settings.ppi)
        images: list[Image.Image] = [Image.new('RGBA', image_size, '#00000000') for _ in range(pages)]
        draws: list[ImageDraw.ImageDraw] = [ImageDraw.Draw(image) for image in images]
        # images_anti_alias: list[Image.Image] = [Image.new('RGBA', image_size, '#00000000') for _ in range(pages)]
        # draws_anti_alias: list[ImageDraw.ImageDraw] = [ImageDraw.Draw(image) for image in images_anti_alias]

        # 自定义水印
        if settings.show_custom_watermark:
            logging.debug('Drawing custom watermark...')
            raise NotImplementedError

        # 分隔线
        logging.debug('Drawing separating lines...')
        for i, draw in enumerate(draws):
            num: int = cols_per_page if i != pages - 1 else last_page_cols
            for j in range(num + 1):
                draw.line((pos_mm_to_pixel((first_col_x + j * COL_WIDTH, up_margin), settings.ppi),
                           pos_mm_to_pixel((first_col_x + j * COL_WIDTH, page_height - down_margin), settings.ppi)),
                          'black', 1)

        # 页眉
        if settings.heading:
            logging.debug('Drawing heading...')
            heading_font: ImageFont.FreeTypeFont = ImageFont.truetype(
                str(settings.font_path), round(mm_to_pixel(settings.heading_size, settings.ppi)))
            for draw in draws:
                draw.text(pos_mm_to_pixel((page_width / 2, up_margin), settings.ppi),
                          settings.heading, 'black', heading_font, 'md')

        if settings.show_info:
            logging.debug('Drawing info...')
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

                draws[0].text(pos_mm_to_pixel((title_x, title_y), settings.ppi),  # type: ignore
                              title, 'black', title_font, title_anchor, align=settings.title_align)  # type: ignore

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

                draws[0].text(pos_mm_to_pixel((subtitle_x, subtitle_y), settings.ppi),  # type: ignore
                              subtitle, 'black', subtitle_font, subtitle_anchor,  # type: ignore
                              align=settings.subtitle_align)

            # 乐曲速度信息 & 音符数量和纸带长度信息
            if settings.show_tempo or settings.show_note_count:
                if settings.show_tempo:
                    draws[0].text(pos_mm_to_pixel((first_col_x + LEFT_BORDER,
                                                   body_y - Draft.INFO_SPACING),
                                                  settings.ppi),
                                  tempo_text, 'black', tempo_note_count_font, 'ld')  # type: ignore

                if settings.show_note_count:
                    draws[0].text(pos_mm_to_pixel((first_col_x + COL_WIDTH - RIGHT_BORDER,
                                                   body_y - Draft.INFO_SPACING),
                                                  settings.ppi),
                                  note_count_text, 'black', tempo_note_count_font, 'rd')  # type: ignore

        logging.debug('Drawing lines...')
        for page, draw in enumerate(draws):
            for col in range(cols_per_page):
                if page == pages - 1 and col >= last_page_cols:
                    continue
                if page == 0 and col == 0:
                    current_col_y: float = body_y
                    current_col_rows: int = first_col_rows
                else:
                    current_col_y = first_row_y
                    current_col_rows = rows_per_col
                # 整拍横线
                for row in range(current_col_rows + 1):
                    draw.line(
                        (pos_mm_to_pixel((first_col_x + col * COL_WIDTH + LEFT_BORDER,
                                          current_col_y + row * LENGTH_MM_PER_BEAT),
                                         settings.ppi),
                         pos_mm_to_pixel((first_col_x + col * COL_WIDTH + COL_WIDTH - RIGHT_BORDER,
                                          current_col_y + row * LENGTH_MM_PER_BEAT),
                                         settings.ppi)),
                        settings.whole_beat_line_color.as_hex(), 1,
                    )
                # 半拍横线
                for row in range(current_col_rows + 1):
                    if settings.half_beat_line_type == 'solid':
                        draw.line(
                            (pos_mm_to_pixel((first_col_x + col * COL_WIDTH + LEFT_BORDER,
                                              current_col_y + (row + 1/2) * LENGTH_MM_PER_BEAT),
                                             settings.ppi),
                             pos_mm_to_pixel((first_col_x + col * COL_WIDTH + COL_WIDTH - RIGHT_BORDER,
                                              current_col_y + (row + 1/2) * LENGTH_MM_PER_BEAT),
                                             settings.ppi)),
                            settings.half_beat_line_color.as_hex(), 1,
                        )
                    else:
                        raise NotImplementedError
                # 竖线
                for line in range(NOTES):
                    draw.line(
                        (pos_mm_to_pixel((first_col_x + col * COL_WIDTH + LEFT_BORDER + line * GRID_WIDTH,
                                          current_col_y),
                                         settings.ppi),
                         pos_mm_to_pixel((first_col_x + col * COL_WIDTH + LEFT_BORDER + line * GRID_WIDTH,
                                          current_col_y + current_col_rows * LENGTH_MM_PER_BEAT),
                                         settings.ppi)),
                        settings.vertical_line_color.as_hex(), 1,
                    )

        # music_info以及栏号
        if settings.show_column_info:
            logging.debug('Drawing column info...')
            column_info_font: ImageFont.FreeTypeFont = ImageFont.truetype(
                str(settings.font_path), round(mm_to_pixel(Draft.COLUMN_INFO_SIZE, settings.ppi)))
            for page, draw in enumerate(draws):
                for col in range(cols_per_page):
                    if page == pages - 1 and col >= last_page_cols:
                        continue
                    current_col_y = body_y if page == 0 and col == 0 else first_row_y
                    for i, char in enumerate(f'{music_info}{page * cols_per_page + col + 1}'):
                        draw.text(pos_mm_to_pixel(
                            (first_col_x + (col + 1) * COL_WIDTH - RIGHT_BORDER - LENGTH_MM_PER_BEAT / 2,
                             current_col_y + (i + 1/2) * LENGTH_MM_PER_BEAT),
                            settings.ppi,
                        ), char, '#00000080', column_info_font, 'mm')

        if settings.show_bar_num:
            logging.debug('Drawing bar nums...')
            raise NotImplementedError

        logging.debug('Drawing notes...')
        for note in self.notes:
            try:
                index: int = MUSIC_BOX_30_NOTES_PITCH.index(note.pitch)
            except:
                logging.warn(f'{note} out of range, SKIPPING!')
                continue
            col: int = math.floor((note.time * scale - first_col_rows + rows_per_col) / rows_per_col)
            page: int = col // cols_per_page
            col_in_page: int = col % cols_per_page
            current_col_y: float = body_y if col == 0 else first_row_y
            row_in_col: float = (note.time * scale) % rows_per_col
            draw_circle(
                draws[page],
                pos_mm_to_pixel(
                    (first_col_x + col_in_page * COL_WIDTH + LEFT_BORDER + index * GRID_WIDTH,
                     current_col_y + row_in_col * LENGTH_MM_PER_BEAT),
                    settings.ppi * settings.anti_alias_rate),
                mm_to_pixel(settings.note_radius, settings.ppi * settings.anti_alias_rate),
                settings.note_color.as_hex(),
            )

        if isinstance(settings.background, Image.Image):
            backgrond_image: Image.Image = settings.background.convert('RGBA').resize(image_size)
        else:
            backgrond_image = Image.new('RGBA', image_size, settings.background.as_hex())

        logging.info('Compositing images...')
        image_list = ImageList(Image.alpha_composite(backgrond_image, image) for image in images)
        image_list.file_name = f'{title}_{{}}.png'
        return image_list