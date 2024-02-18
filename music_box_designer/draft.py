import math
import re
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from itertools import pairwise
from pathlib import Path
from typing import Any, Literal, Self, overload

import mido
import yaml
from PIL import Image, ImageColor, ImageDraw, ImageFont
from mido import MidiFile
from pydantic import BaseModel, FilePath, FiniteFloat, NonNegativeFloat, PositiveInt, field_serializer, field_validator
from pydantic_extra_types.color import Color

from .emid import EMID_PITCHES, EMID_TICKS_PER_BEAT, EmidFile
from .fmp import FmpFile
from .log import logger
from .mcode import DEFAULT_PPQ, MCodeFile, MCodeNote, get_arranged_notes
from .presets import MusicBox, music_box_30_notes, music_box_presets

DEFAULT_BPM: float = 120


@dataclass(frozen=True)
class Note:
    pitch: int
    '''音高'''
    time: float
    '''节拍数'''


class DraftSettings(BaseModel, arbitrary_types_allowed=True):
    # 页面设置
    anti_alias: Literal['off', 'fast', 'accurate'] = 'fast'
    '''抗锯齿等级（仅对音符生效），可选值`'off', 'fast', 'accurate'`'''
    ppi: float = 300
    '''图片分辨率，单位像素/英寸'''
    paper_size: tuple[float, float] | None = (210, 297)
    '''页面大小（宽，高），单位毫米，设置为`None`则会使得图片只有一栏并且自动调整大小'''
    margins: tuple[float, float, float, float] = (8.0, 8.0, 0, 0)
    '''页面边距（上，下，左，右），单位毫米'''
    background: Color | Image.Image = Color('white')
    '''背景颜色或图片，可传入`PIL.Image.Image`对象'''
    font_path: FilePath = Path('fonts/SourceHanSans.otf')
    '''字体文件路径'''
    heading: str = '打谱软件：https://github.com/BiologyHazard/MusicBoxDesigner'
    '''页面顶部文字'''
    heading_size: NonNegativeFloat = 3.5
    '''页面顶部文字大小，单位毫米，将以`round(heading_size * ppi / MM_PER_INCH)`转变为像素大小'''
    heading_color: Color = Color('black')
    '''页面顶部文字颜色'''
    separating_line_color: Color = Color('black')
    '''分隔线颜色'''

    # 标题设置
    show_info: bool = True
    '''信息显示总开关'''

    show_title: bool = True
    '''是否显示标题'''
    title_align: Literal['left', 'center', 'right'] = 'center'
    '''标题对齐方式'''
    title_height: FiniteFloat | None = None
    '''标题到页面上边的距离，单位毫米，设置为`None`则自动'''
    title_size: NonNegativeFloat = 4.5
    '''标题文字大小，单位毫米，将以`round(title_size * ppi / MM_PER_INCH)`转变为像素大小'''
    title_color: Color = Color('black')
    '''标题颜色'''

    show_subtitle: bool = True
    '''是否显示副标题'''
    subtitle_align: Literal['left', 'center', 'right'] = 'center'
    '''副标题对齐方式'''
    subtitle_height: FiniteFloat | None = None
    '''副标题到页面上边的距离，单位毫米，设置为`None`则自动'''
    subtitle_size: NonNegativeFloat = 3.0
    '''副标题文字大小，单位毫米，将以`round(subtitle_size * ppi / MM_PER_INCH)`转变为像素大小'''
    subtitle_color: Color = Color('black')
    '''副标题颜色'''

    show_tempo: bool = True
    '''是否显示乐曲速度信息'''
    tempo_format: str = '{bpm:.0f}bpm'
    '''乐曲速度信息的格式化字符串，支持参数`bpm`'''
    show_note_count: bool = True
    '''是否显示音符数量和纸带长度信息'''
    note_count_format: str = '{note_count} notes / {meter:.2f}m'
    '''音符数量和纸带长度信息的格式化字符串，支持参数`note_count`, `meter`, `centimeter`和`millimeter`'''
    tempo_note_count_size: NonNegativeFloat = 3.0
    '''乐曲速度信息、音符数量和纸带长度信息文字大小，单位毫米，将以`round(tempo_note_count_size * ppi / MM_PER_INCH)`转变为像素大小'''
    tempo_note_count_color: Color = Color('black')
    '''乐曲速度信息、音符数量和纸带长度信息颜色'''

    # 谱面设置
    body_height: FiniteFloat | None = None
    '''谱面到页面上边的距离，单位毫米，设置为`None`则自动'''

    note_color: Color = Color('black')
    '''音符颜色'''
    note_radius: NonNegativeFloat = 1.04
    '''音符半径，单位毫米'''

    show_column_info: bool = True
    '''是否在每栏右上角显示`music_info`以及栏号'''
    column_info_size: NonNegativeFloat = 6.0
    '''栏信息文字大小，单位毫米，将以`round(column_info_size * ppi / MM_PER_INCH)`转变为像素大小'''
    column_info_color: Color = Color('#00000080')
    '''栏信息颜色'''

    show_column_num: bool = True
    '''是否显示栏下方页码'''
    column_num_size: NonNegativeFloat = 3.0
    '''栏下方页码文字大小，单位毫米，将以`round(column_num_size * ppi / MM_PER_INCH)`转变为像素大小'''
    column_num_color: Color = Color('black')
    '''栏下方页码颜色'''

    show_bar_num: bool = True
    '''是否显示小节号'''
    beats_per_bar: PositiveInt | None = None
    '''每小节多少拍，设置为`None`则从文件中读取，读取不到则认为每小节4拍'''
    bar_num_start: int = 1
    '''小节号从几开始'''
    bar_num_size: NonNegativeFloat = 3.0
    '''小节号文字大小，单位毫米，将以`round(bar_num_size * ppi / MM_PER_INCH)`转变为像素大小'''
    bar_num_color: Color = Color('black')
    '''小节号颜色'''

    show_custom_watermark: bool = False
    '''是否显示自定义水印'''
    custom_watermark: str = '自定义水印'
    '''自定义水印内容'''
    custom_watermark_size: NonNegativeFloat = 6.0
    '''自定义水印文字大小，单位毫米，将以`round(custom_watermark_size * ppi / MM_PER_INCH)`转变为像素大小'''
    custom_watermark_color: Color = Color('#00000060')
    '''自定义水印颜色'''

    show_note_path: bool = False
    '''是否显示打孔路径'''
    note_path_color: Color = Color('red')
    '''打孔路径颜色'''
    note_path_width: NonNegativeFloat = 0.5
    '''打孔路径宽度，单位毫米，将以`round(note_path_width * ppi / MM_PER_INCH)`转变为像素大小'''

    whole_beat_line_color: Color = Color('black')
    '''整拍线条颜色'''
    half_beat_line_type: Literal['solid', 'dashed'] = 'solid'
    '''半拍线条类型，`'solid'`表示实线，`'dashed'`表示虚线'''
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
        except ValueError:
            return Image.open(value)

    @field_serializer('background')
    def serializer(self, value):
        if isinstance(value, Color):
            return value.original()
        try:
            return value.filename
        except AttributeError:
            raise Exception(f'Failed to serialize background of value {value}')

    def model_dump_yaml(self, **kwargs) -> str:
        return yaml.dump(self.model_dump(mode='json'),
                         default_flow_style=True,
                         allow_unicode=True,
                         sort_keys=False,
                         **kwargs)

    @classmethod
    def model_validate_yaml(cls, yaml_data) -> Self:
        return cls.model_validate(yaml.safe_load(yaml_data))


class ImageList(list[Image.Image]):
    file_name: str
    title: str
    paper_size: tuple[float, float]

    def save(self, file_name: str | None = None, format: str | None = None, overwrite: bool = False) -> None:
        """
        保存图片或 PDF 文档到文件，文件格式由参数 `file_name` 推断，也可以用参数 `format` 指定。

        参数：
        - `file_name`:
            对于图片格式，是文件保存路径的格式化字符串，例如 `'output/pic_{}.png'`。若不指定，则取 `'<self.file_name>_{}.png'`
            对于 PDF 格式，是文件保存路径，例如 `'output/music_box.pdf'`。若不指定，则取 `'<self.file_name>.pdf'`
        - `format`: 保存文件的格式，可以是 `'PDF'`，或一种 Pillow 支持的图片格式。若不指定，则由 `file_name` 推断。
        - `overwrite`: 是否允许覆盖同名文件，默认为 `False`
        """
        if format is None and file_name is not None:
            format = Path(file_name).suffix.lstrip('.').upper()
        if format is not None and format.upper() == 'PDF':
            return self.save_pdf(file_name, overwrite)
        else:
            return self.save_image(file_name, format, overwrite)

    def save_image(self, file_name: str | None = None, format: str | None = None, overwrite: bool = False) -> None:
        """
        保存图片到文件，文件格式由参数 `file_name` 推断。

        参数：
        - `file_name`: 文件保存路径的格式化字符串，例如 `'output/pic_{}.png'`。若不指定，则取 `'<self.file_name>_{}.png'`
        - `format`: 保存文件的格式，可以是一种 Pillow 支持的图片格式。若不指定，则由 `file_name` 推断。
        - `overwrite`: 是否允许覆盖同名文件，默认为 `False`
        """
        if file_name is None:
            file_name = f'{self.file_name}_{{}}.png'
        for i, image in enumerate(self):
            path_to_save: Path = find_available_filename(file_name.format(i + 1), overwrite=overwrite)
            logger.info(f'Saving image {i + 1} of {len(self)} to {path_to_save.as_posix()}...')
            image.save(path_to_save, format=format)

    def save_pdf(self, file_name: str | None = None, overwrite: bool = True) -> None:
        """
        由图片生成 PDF 文档，并保存到文件。

        参数：
        - `file_name`: 文件保存路径的格式化字符串，例如 `'output/music_box.pdf'`。若不指定，则取 `'<self.file_name>.pdf'`
        - `overwrite`: 是否允许覆盖同名文件，默认为 `False`
        """
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas

        if file_name is None:
            file_name = f'{self.file_name}.pdf'

        logger.info('Combining images to PDF...')
        path_to_save: Path = find_available_filename(file_name, overwrite=overwrite)
        width, height = self.paper_size
        pdf_page_size: tuple[float, float] = (width * mm, height * mm)
        c = canvas.Canvas(path_to_save.as_posix(), pagesize=pdf_page_size)
        c.setAuthor('BioHazard')
        c.setTitle(getattr(self, 'title', 'Music Box'))
        c.setSubject('Music Box')
        c.setKeywords(('Music Box', 'Music Box Designer'))
        c.setCreator('Music Box Designer')
        # c.setProducer('Music Box Designer')
        for image in self:
            c.drawInlineImage(image, 0, 0, *pdf_page_size)
            c.showPage()
        logger.info(f'Saving PDF to {path_to_save.as_posix()}...')
        c.save()


@dataclass
class Draft:
    notes: list[Note] = field(default_factory=list)
    preset: MusicBox = music_box_30_notes
    title: str = ''
    subtitle: str = ''
    music_info: str = ''
    file_path: Path | None = None
    bpm: float | None = None
    time_signature: tuple[int, int] | None = None

    INFO_SPACING: float = 1.0

    @classmethod
    def load_from_file(cls,
                       file_path: str | Path,
                       preset: MusicBox | None = None,
                       transposition: int = 0,
                       remove_blank: bool = True,
                       skip_near_notes: bool = True,
                       bpm: float | None = None,
                       ) -> Self:
        logger.info(f'Loading from {file_path!r}...')
        try:
            file_path = Path(file_path)
        except TypeError:
            raise TypeError(f"Parameter 'file' must be a path-like object, but got {type(file_path)}.")
        match file_path.suffix:
            case '.emid':
                return cls.load_from_emid(EmidFile.load_from_file(file_path),
                                          preset=preset,
                                          transposition=transposition,
                                          remove_blank=remove_blank,
                                          skip_near_notes=skip_near_notes,
                                          bpm=bpm)
            case '.fmp':
                return cls.load_from_fmp(FmpFile.load_from_file(file_path),
                                         preset=preset,
                                         transposition=transposition,
                                         remove_blank=remove_blank,
                                         skip_near_notes=skip_near_notes,
                                         bpm=bpm)
            case '.mid':
                return cls.load_from_midi(MidiFile(file_path),
                                          preset=preset,
                                          transposition=transposition,
                                          remove_blank=remove_blank,
                                          skip_near_notes=skip_near_notes,
                                          bpm=bpm)
            case '.mcode':  # 先偷个懒
                return cls.load_from_midi(MCodeFile.open(file_path).export_midi(),
                                          preset=preset,
                                          transposition=transposition,
                                          remove_blank=remove_blank,
                                          skip_near_notes=skip_near_notes,
                                          bpm=bpm)
            case other:
                raise ValueError(f"The file extension must be '.emid', '.fmp', '.mid' or '.mcode', but got {repr(other)}.")

    @classmethod
    def load_from_emid(cls,
                       emid_file: EmidFile,
                       preset: MusicBox | None = None,
                       transposition: int = 0,
                       remove_blank: bool = True,
                       skip_near_notes: bool = True,
                       bpm: float | None = None,
                       ) -> Self:
        self: Self = cls()
        if preset is not None:
            self.preset = preset
        if emid_file.file_path is not None:
            self.title = self.music_info = emid_file.file_path.stem
            self.file_path = emid_file.file_path
        self.bpm = bpm

        for track in emid_file.tracks:
            for note in track.notes:
                self.notes.append(Note(pitch=EMID_PITCHES[note.emid_pitch] + transposition,
                                       time=note.tick / EMID_TICKS_PER_BEAT))

        self.remove_out_of_range_notes()
        if remove_blank:
            self.remove_blank()
        if skip_near_notes:
            self.remove_near_notes()
        return self

    @classmethod
    def load_from_fmp(cls,
                      fmp_file: FmpFile,
                      preset: MusicBox | None = None,
                      transposition: int = 0,
                      remove_blank: bool = True,
                      skip_near_notes: bool = True,
                      bpm: float | None = None,
                      ) -> Self:
        self: Self = cls()
        # TODO: Use fmp_file.instrument and fmp_file.instrument_cfg
        if preset is None:
            preset = music_box_presets.get(
                {
                    'Instrument_Preset_PaperStripMusicBox_30Note': 30,
                    'Instrument_Preset_PaperStripMusicBox_20Note': 20,
                    'Instrument_Preset_PaperStripMusicBox_15Note': 15,
                }.get(fmp_file.instrument, 30),
                music_box_30_notes,
            )
        self.preset = preset
        self.title = self.music_info = fmp_file.title
        self.subtitle = fmp_file.subtitle
        self.file_path = fmp_file.file_path
        self.bpm = bpm if bpm is not None else mido.tempo2bpm(fmp_file.tempo)
        self.time_signature = fmp_file.time_signature

        for track in fmp_file.tracks:
            for note in track.notes:
                if note.velocity == 0:
                    continue
                self.notes.append(Note(pitch=note.pitch + transposition,
                                       time=note.tick / fmp_file.ticks_per_beat))

        self.remove_out_of_range_notes()
        if remove_blank:
            self.remove_blank()
        if skip_near_notes:
            self.remove_near_notes()
        return self

    @classmethod
    def load_from_midi(cls,
                       midi_file: MidiFile,
                       preset: MusicBox | None = None,
                       transposition: int = 0,
                       remove_blank: bool = True,
                       skip_near_notes: bool = True,
                       bpm: float | None = None) -> Self:
        self: Self = cls()
        if preset is not None:
            self.preset = preset
        if midi_file.filename is not None:
            try:
                file_path = Path(midi_file.filename)
                self.title = self.music_info = file_path.stem
                self.file_path = file_path
            except TypeError:
                self.title = self.music_info = str(midi_file.filename)

        ticks_per_beat: int = midi_file.ticks_per_beat

        if bpm is not None:
            self.bpm = bpm
            tempo_events: list[TempoEvent] = get_tempo_events(midi_file, bpm, ticks_per_beat)
        else:
            if (temp := get_midi_bpm(midi_file)) is not None:
                self.bpm = temp

        for track in midi_file.tracks:
            midi_tick: int = 0
            for message in track:
                midi_tick += message.time
                if message.type != 'note_on':
                    continue
                if message.velocity == 0:
                    continue
                if bpm is None:
                    time: float = midi_tick / ticks_per_beat
                else:
                    i: int = bisect_right(tempo_events, midi_tick, key=lambda x: x.midi_tick) - 1  # type: ignore
                    tempo: float = tempo_events[i].tempo  # type: ignore
                    tick: int = tempo_events[i].midi_tick  # type: ignore
                    real_time: float = (tempo_events[i].time_passed  # type: ignore
                                        + mido.tick2second(midi_tick - tick, ticks_per_beat, tempo))
                    time = real_time / 60 * bpm
                self.notes.append(Note(pitch=message.note + transposition,
                                       time=time))

        self.notes.sort(key=lambda note: note.time)
        self.remove_out_of_range_notes()
        if remove_blank:
            self.remove_blank()
        if skip_near_notes:
            self.remove_near_notes()
        return self

    def remove_out_of_range_notes(self) -> None:
        new_notes: list[Note] = []
        for note in self.notes:
            if note.pitch not in self.preset.range:
                logger.warning(f'Note {note.pitch} in bar {math.floor(note.time / 4) + 1} is out of range.')
                continue
            new_notes.append(note)
        self.notes = new_notes

    def remove_blank(self) -> None:
        if not self.notes:
            return
        self.notes.sort(key=lambda note: note.time)
        blank: int = math.floor(self.notes[0].time)
        self.notes = [Note(note.pitch, note.time - blank) for note in self.notes]

    def remove_near_notes(self) -> None:
        self.notes.sort(key=lambda note: note.time)
        latest_time: defaultdict[int, float] = defaultdict(
            lambda: -self.preset.min_trigger_spacing / self.preset.length_mm_per_beat)
        new_notes: list[Note] = []
        for note in self.notes:
            if (note.time < latest_time[note.pitch]
                    + self.preset.min_trigger_spacing / self.preset.length_mm_per_beat):
                logger.warning(f'Too Near! Note {note.pitch} in bar {math.floor(note.time / 4) + 1}, SKIPPING!')
                continue
            new_notes.append(note)
            latest_time[note.pitch] = note.time
        self.notes = new_notes

    def export_pics(self,
                    settings: DraftSettings | None = None,
                    title: str | None = None,
                    subtitle: str | None = None,
                    music_info: str | None = None,
                    show_bpm: float | None = None,
                    scale: float = 1,
                    ) -> ImageList:
        # 由于在一拍当中插入时间标记会导致网格的错乱，故暂时不支持在乐曲中间更改时间标记。
        # TODO: 寻找更好的解决办法。
        if title is None:
            title = self.title
        if subtitle is None:
            subtitle = self.subtitle
        if music_info is None:
            music_info = self.music_info
        if show_bpm is None:
            show_bpm = self.bpm if self.bpm is not None else 120
        if settings is None:
            settings = DraftSettings()

        self.notes.sort(key=lambda note: note.time)
        if self.notes:
            length_mm: float = self.notes[-1].time * self.preset.length_mm_per_beat * scale
        else:
            length_mm = 0

        # 计算各元素坐标
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
                        tempo_text: str = settings.tempo_format.format(bpm=show_bpm)
                    except Exception as e:
                        logger.warning(f'Cannot format tempo: {e!r}')
                        logger.warning("Falling back to default tempo format '{bpm:.0f}bpm'.")
                        tempo_text = '{bpm:.0f}bpm'.format(bpm=show_bpm)
                else:
                    tempo_text = ''

                if settings.show_note_count:
                    format_dict = dict(
                        note_count=len(self.notes),
                        meter=length_mm / 1000,
                        centimeter=length_mm / 100,
                        millimeter=length_mm,
                    )
                    try:
                        note_count_text: str = settings.note_count_format.format(**format_dict)
                    except Exception as e:
                        logger.warning(f'Cannot format note count: {e!r}')
                        logger.warning("Falling back to default note count format '{note_count} notes / {meter:.2f}m'.")
                        note_count_text = '{note_count} notes / {meter:.2f}m'.format(**format_dict)
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
        rows: int = math.floor(length_mm / self.preset.length_mm_per_beat) + 1
        if settings.paper_size is not None:
            page_width, page_height = settings.paper_size
            rows_per_col: int = math.floor((page_height - up_margin - down_margin) / self.preset.length_mm_per_beat)
            cols_per_page: int = math.floor((page_width - left_margin - right_margin) / self.preset.col_width)
            first_col_rows: int = max(math.floor((page_height - down_margin - body_y) / self.preset.length_mm_per_beat),
                                      0)
            cols: int = math.ceil((rows + rows_per_col - first_col_rows) / rows_per_col)
            pages: int = math.ceil(cols / cols_per_page)
            last_page_cols: int = cols - (pages - 1) * cols_per_page
        else:
            cols = last_page_cols = cols_per_page = pages = 1
            rows_per_col = first_col_rows = rows
            page_width: float = left_margin + self.preset.col_width + right_margin
            page_height: float = body_y + rows * self.preset.length_mm_per_beat + down_margin
        first_col_x: float = page_width / 2 - cols_per_page * self.preset.col_width / 2
        first_row_y: float = page_height / 2 - rows_per_col * self.preset.length_mm_per_beat / 2
        next_body_y: float = (first_row_y
                              + math.ceil((body_y - first_row_y) / self.preset.length_mm_per_beat)
                              * self.preset.length_mm_per_beat)
        if next_body_y + first_col_rows * self.preset.length_mm_per_beat + down_margin <= page_height:
            body_y = next_body_y

        logger.debug(f'rows: {rows}')
        logger.debug(f'rows_per_col: {rows_per_col}')
        logger.debug(f'cols_per_page: {cols_per_page}')
        logger.debug(f'first_col_rows: {first_col_rows}')
        logger.debug(f'last_page_cols: {last_page_cols}')
        logger.debug(f'first_col_x: {first_col_x}')
        logger.debug(f'first_row_y: {first_row_y}')
        logger.debug(f'body_y: {body_y}')

        logger.info(f'Notes: {len(self.notes)}')
        logger.info(f'Length: {length_mm / 1000:.2f}m')
        logger.info(f'Cols: {cols}')
        logger.info(f'Pages: {pages}')

        # 构建图片列表
        image_size: tuple[int, int] = pos_mm_to_pixel((page_width, page_height), settings.ppi, 'round')
        images: list[Image.Image] = [Image.new('RGBA', image_size, '#00000000') for _ in range(pages)]
        draws: list[ImageDraw.ImageDraw] = [ImageDraw.Draw(image) for image in images]

        # 自定义水印
        if settings.show_custom_watermark:
            logger.debug('Drawing custom watermark...')
            custom_watermark_font: ImageFont.FreeTypeFont = ImageFont.truetype(
                str(settings.font_path), round(mm_to_pixel(settings.custom_watermark_size, settings.ppi)))

            for row in range(0, rows, 10):
                col: int = math.floor((row - first_col_rows + rows_per_col) / rows_per_col)
                page: int = col // cols_per_page
                col_in_page: int = col % cols_per_page
                current_col_y: float = body_y if col == 0 else first_row_y
                row_in_col: float = (row if col == 0 else (row - first_col_rows + rows_per_col) % rows_per_col)
                draws[page].text(
                    pos_mm_to_pixel((first_col_x + (col_in_page + 1 / 2) * self.preset.col_width,
                                     current_col_y + row_in_col * self.preset.length_mm_per_beat),
                                    settings.ppi),
                    settings.custom_watermark,
                    settings.custom_watermark_color.as_hex(),
                    custom_watermark_font,
                    'mm',
                    align='center',
                )

        # 分隔线
        logger.debug('Drawing separating lines...')
        for i, draw in enumerate(draws):
            num: int = cols_per_page if i != pages - 1 else last_page_cols
            for j in range(num + 1):
                x: float = first_col_x + j * self.preset.col_width
                if x < 1 / 4 or x > page_width - 1 / 4:  # 避免线条过于靠近边缘
                    continue
                draw.line((pos_mm_to_pixel((x, up_margin),
                                           settings.ppi, 'floor'),
                           pos_mm_to_pixel((x, page_height - down_margin),
                                           settings.ppi, 'floor')),
                          settings.separating_line_color.as_hex(), 1)

        # 页面顶部文字
        if settings.heading:
            logger.debug('Drawing heading...')
            heading_font: ImageFont.FreeTypeFont = ImageFont.truetype(
                str(settings.font_path), round(mm_to_pixel(settings.heading_size, settings.ppi)))
            for draw in draws:
                draw.text(pos_mm_to_pixel((page_width / 2, up_margin - Draft.INFO_SPACING), settings.ppi),
                          settings.heading, 'black', heading_font, 'md')

        if settings.show_info:
            logger.debug('Drawing info...')
            # 标题
            if settings.show_title:
                if settings.title_align == 'left':
                    title_x: float = first_col_x + self.preset.left_border
                    title_anchor: str = 'la'
                elif settings.title_align == 'center':
                    title_x = first_col_x + self.preset.col_width / 2
                    title_anchor = 'ma'
                elif settings.title_align == 'right':
                    title_x = first_col_x + self.preset.col_width - self.preset.right_border
                    title_anchor = 'ra'
                else:
                    raise ValueError

                draws[0].text(pos_mm_to_pixel((title_x, title_y), settings.ppi),  # type: ignore
                              title, 'black', title_font, title_anchor, align=settings.title_align)  # type: ignore

            # 副标题
            if settings.show_subtitle:
                if settings.subtitle_align == 'left':
                    subtitle_x: float = first_col_x + self.preset.left_border
                    subtitle_anchor: str = 'la'
                elif settings.subtitle_align == 'center':
                    subtitle_x = first_col_x + self.preset.col_width / 2
                    subtitle_anchor = 'ma'
                elif settings.subtitle_align == 'right':
                    subtitle_x = first_col_x + self.preset.col_width - self.preset.right_border
                    subtitle_anchor = 'ra'
                else:
                    raise ValueError

                draws[0].text(
                    pos_mm_to_pixel((subtitle_x, subtitle_y), settings.ppi),  # type: ignore
                    subtitle, 'black', subtitle_font, subtitle_anchor,  # type: ignore
                    align=settings.subtitle_align,
                )

            # 乐曲速度信息 & 音符数量和纸带长度信息
            if settings.show_tempo or settings.show_note_count:
                if settings.show_tempo:
                    draws[0].text(
                        pos_mm_to_pixel((first_col_x + self.preset.left_border,
                                         body_y - Draft.INFO_SPACING),
                                        settings.ppi),
                        tempo_text, 'black', tempo_note_count_font, 'ld',  # type: ignore
                    )

                if settings.show_note_count:
                    draws[0].text(
                        pos_mm_to_pixel(
                            (first_col_x + self.preset.col_width - self.preset.right_border,
                             body_y - Draft.INFO_SPACING),
                            settings.ppi,
                        ),
                        note_count_text, 'black', tempo_note_count_font, 'rd',  # type: ignore
                    )

        # music_info以及栏号
        if settings.show_column_info:
            logger.debug('Drawing column info...')
            column_info_font: ImageFont.FreeTypeFont = ImageFont.truetype(
                str(settings.font_path), round(mm_to_pixel(settings.column_info_size, settings.ppi)))
            for page, draw in enumerate(draws):
                for col_in_page in range(cols_per_page):
                    if page == pages - 1 and col_in_page >= last_page_cols:
                        continue
                    current_col_y = body_y if page == 0 and col_in_page == 0 else first_row_y
                    for i, char in enumerate(f'{music_info}{page * cols_per_page + col_in_page + 1}'):
                        draw.text(
                            pos_mm_to_pixel(
                                (first_col_x + (col_in_page + 1) * self.preset.col_width
                                 - self.preset.right_border - self.preset.length_mm_per_beat / 2,
                                 current_col_y + (i + 1 / 2) * self.preset.length_mm_per_beat),
                                settings.ppi,
                            ),
                            char, settings.column_info_color.as_hex(), column_info_font, 'mm',
                        )

        # 栏下方页码
        if settings.show_column_num:
            logger.debug('Drawing column nums...')
            page_num_font: ImageFont.FreeTypeFont = ImageFont.truetype(
                str(settings.font_path), round(mm_to_pixel(settings.column_num_size, settings.ppi)))
            for page, draw in enumerate(draws):
                for col_in_page in range(cols_per_page):
                    col = page * cols_per_page + col_in_page
                    if col >= cols:
                        continue
                    if col == 0:
                        current_col_top_y: float = body_y
                        current_col_rows: int = first_col_rows
                    else:
                        current_col_top_y = first_row_y
                        current_col_rows = rows_per_col
                    current_col_bottom_y: float = (
                        current_col_top_y + current_col_rows * self.preset.length_mm_per_beat)
                    draw.text(
                        pos_mm_to_pixel((first_col_x + col_in_page * self.preset.col_width + self.preset.left_border,
                                         current_col_bottom_y),
                                        settings.ppi),
                        f'{col + 1}', settings.column_num_color.as_hex(), page_num_font, 'la')

        logger.debug('Drawing lines...')
        for page, draw in enumerate(draws):
            for col_in_page in range(cols_per_page):
                if page == pages - 1 and col_in_page >= last_page_cols:
                    continue
                if page == 0 and col_in_page == 0:
                    current_col_y: float = body_y
                    current_col_rows: int = first_col_rows
                else:
                    current_col_y = first_row_y
                    current_col_rows = rows_per_col
                # 整拍横线
                for row in range(current_col_rows + 1):
                    draw.line(
                        (pos_mm_to_pixel(
                            (first_col_x + col_in_page * self.preset.col_width + self.preset.left_border,
                             current_col_y + row * self.preset.length_mm_per_beat),
                            settings.ppi, 'floor'),
                         pos_mm_to_pixel(
                             (first_col_x + col_in_page * self.preset.col_width
                              + self.preset.col_width - self.preset.right_border,
                              current_col_y + row * self.preset.length_mm_per_beat),
                             settings.ppi, 'floor')),
                        settings.whole_beat_line_color.as_hex(), 1,
                    )
                # 半拍横线
                for row in range(current_col_rows):
                    match settings.half_beat_line_type:
                        case 'solid':
                            draw.line(
                                (pos_mm_to_pixel(
                                    (first_col_x + col_in_page * self.preset.col_width + self.preset.left_border,
                                     current_col_y + (row + 1 / 2) * self.preset.length_mm_per_beat),
                                    settings.ppi, 'floor'),
                                 pos_mm_to_pixel(
                                     (first_col_x + col_in_page * self.preset.col_width
                                      + self.preset.col_width - self.preset.right_border,
                                      current_col_y + (row + 1 / 2) * self.preset.length_mm_per_beat),
                                     settings.ppi, 'floor')),
                                settings.half_beat_line_color.as_hex(), 1,
                            )
                        case 'dashed':
                            for part in range(6):
                                draw.line(
                                    (pos_mm_to_pixel(
                                        (first_col_x + col_in_page * self.preset.col_width
                                         + self.preset.left_border + (part * 5) * self.preset.grid_width,
                                         current_col_y + (row + 1 / 2) * self.preset.length_mm_per_beat),
                                        settings.ppi, 'floor'),
                                     pos_mm_to_pixel(
                                         (first_col_x + col_in_page * self.preset.col_width
                                          + self.preset.left_border + (part * 5 + 1 + 1 / 2) * self.preset.grid_width,
                                          current_col_y + (row + 1 / 2) * self.preset.length_mm_per_beat),
                                         settings.ppi, 'floor')),
                                    settings.half_beat_line_color.as_hex(), 1,
                                )
                                draw.line(
                                    (pos_mm_to_pixel(
                                        (first_col_x + col_in_page * self.preset.col_width
                                         + self.preset.left_border + (part * 5 + 2 + 1 / 2) * self.preset.grid_width,
                                         current_col_y + (row + 1 / 2) * self.preset.length_mm_per_beat),
                                        settings.ppi, 'floor'),
                                     pos_mm_to_pixel(
                                         (first_col_x + col_in_page * self.preset.col_width
                                          + self.preset.left_border + (part * 5 + 4) * self.preset.grid_width,
                                          current_col_y + (row + 1 / 2) * self.preset.length_mm_per_beat),
                                         settings.ppi, 'floor')),
                                    settings.half_beat_line_color.as_hex(), 1,
                                )
                        case _:
                            raise ValueError
                # 竖线
                for line in range(self.preset.note_count):
                    draw.line(
                        (pos_mm_to_pixel(
                            (first_col_x + col_in_page * self.preset.col_width
                             + self.preset.left_border + line * self.preset.grid_width,
                             current_col_y),
                            settings.ppi, 'floor'),
                         pos_mm_to_pixel(
                             (first_col_x + col_in_page * self.preset.col_width
                              + self.preset.left_border + line * self.preset.grid_width,
                              current_col_y + current_col_rows * self.preset.length_mm_per_beat),
                             settings.ppi, 'floor')),
                        settings.vertical_line_color.as_hex(), 1,
                    )

        # 小节号
        if settings.show_bar_num:
            logger.debug('Drawing bar nums...')
            bar_num_font: ImageFont.FreeTypeFont = ImageFont.truetype(
                str(settings.font_path), round(mm_to_pixel(settings.bar_num_size, settings.ppi)))

            if settings.beats_per_bar is not None:
                beats_per_bar: int = settings.beats_per_bar
            elif self.time_signature is not None:
                beats_per_bar = self.time_signature[0]
            else:
                beats_per_bar = 4

            for i, row in enumerate(range(0, rows, beats_per_bar)):
                col: int = math.floor((row - first_col_rows + rows_per_col) / rows_per_col)
                page: int = col // cols_per_page
                col_in_page: int = col % cols_per_page
                current_col_y: float = body_y if col == 0 else first_row_y
                row_in_col: float = (row if col == 0 else
                                     (row - first_col_rows + rows_per_col) % rows_per_col)
                draws[page].text(
                    pos_mm_to_pixel(
                        (first_col_x + col_in_page * self.preset.col_width
                         + self.preset.left_border - settings.note_radius,
                         current_col_y + row_in_col * self.preset.length_mm_per_beat),
                        settings.ppi,
                    ),
                    str(i + settings.bar_num_start),
                    settings.bar_num_color.as_hex(),
                    bar_num_font,
                    'rm',
                )

        def calculate_pos(note: Note) -> tuple[int, int, tuple[int, int]]:
            try:
                index: int = self.preset.range.index(note.pitch)
            except ValueError:
                raise ValueError(f'{note} out of range, SKIPPING!')
            col: int = math.floor((note.time * scale - first_col_rows + rows_per_col) / rows_per_col)
            page: int = col // cols_per_page
            col_in_page: int = col % cols_per_page
            current_col_y: float = body_y if col == 0 else first_row_y
            row_in_col: float = (note.time * scale
                                 if col == 0 else
                                 (note.time * scale - first_col_rows + rows_per_col) % rows_per_col)
            xy: tuple[int, int] = pos_mm_to_pixel(
                (first_col_x + col_in_page * self.preset.col_width
                    + self.preset.left_border + index * self.preset.grid_width,
                    current_col_y + row_in_col * self.preset.length_mm_per_beat),
                settings.ppi,
                'floor',
            )
            return page, col, xy

        # 音符路径
        if settings.show_note_path:
            logger.debug('Drawing note paths...')

            mcode_notes: list[MCodeNote] = sorted(
                (MCodeNote(pitch_index=self.preset.range.index(note.pitch) + 1,
                           tick=round(note.time * DEFAULT_PPQ))
                 for note in self.notes),
                key=lambda note: (note.tick, note.pitch_index),
            )
            mcode_notes = get_arranged_notes(mcode_notes)
            notes: list[Note] = [Note(pitch=self.preset.range[note.pitch_index - 1],
                                      time=note.tick / DEFAULT_PPQ)
                                 for note in mcode_notes]
            for note0, note1 in pairwise(notes):
                page0, col0, pos0 = calculate_pos(note0)
                page1, col1, pos1 = calculate_pos(note1)
                if col0 != col1:
                    continue
                draw_line(
                    images[page0],
                    (pos0, pos1),
                    mm_to_pixel(settings.note_path_width, settings.ppi),
                    settings.note_path_color.as_hex(),
                    anti_alias='accurate' if settings.anti_alias == 'fast' else settings.anti_alias,
                )

        # 音符
        logger.debug('Drawing notes...')
        for note in self.notes:
            page, col, pos = calculate_pos(note)
            draw_circle(
                images[page],
                pos,
                mm_to_pixel(settings.note_radius, settings.ppi),
                settings.note_color.as_hex(),
                anti_alias=settings.anti_alias,
            )

        if isinstance(settings.background, Image.Image):
            background_image: Image.Image = settings.background.convert('RGBA').resize(image_size)
        else:
            background_image = Image.new('RGBA', image_size, settings.background.as_hex())

        logger.info('Compositing images...')
        image_list = ImageList(Image.alpha_composite(background_image, image) for image in images)
        image_list.title = title
        image_list.paper_size = (page_width, page_height)
        if self.file_path is None:
            image_list.file_name = title
        else:
            image_list.file_name = self.file_path.with_suffix('').as_posix()
        return image_list


def make_valid_filename(s: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', '_', s)


def find_available_filename(path: str | Path, overwrite: bool = False) -> Path:
    path = Path(path)
    name: str = make_valid_filename(path.name)
    path = path.with_name(name)
    if overwrite or not path.exists():
        return path
    i = 1
    while (new_path := path.with_stem(f'{path.stem} ({i})')).exists():
        i += 1
    return new_path


@dataclass
class TempoEvent:
    midi_tick: int
    tempo: float
    time_passed: float


def get_tempo_events(midi_file: MidiFile, bpm: float, ticks_per_beat: int) -> list[TempoEvent]:
    tempo_events: list[TempoEvent] = [TempoEvent(0, mido.bpm2tempo(bpm), 0)]
    for track in midi_file.tracks:
        midi_tick: int = 0
        for message in track:
            midi_tick += message.time
            if message.type == 'set_tempo':
                tempo_events.append(TempoEvent(midi_tick, message.tempo, 0))

    tempo_events.sort(key=lambda x: x.midi_tick)

    time_passed: float = 0.0
    for i in range(1, len(tempo_events)):
        tempo: float = tempo_events[i - 1].tempo
        delta_midi_tick: int = tempo_events[i].midi_tick - tempo_events[i - 1].midi_tick
        time_passed += mido.tick2second(delta_midi_tick, ticks_per_beat, tempo)
        tempo_events[i].time_passed = time_passed
    return tempo_events


def get_midi_bpm(midi_file: MidiFile) -> float | None:
    for track in midi_file.tracks:
        for message in track:
            if message.type == 'set_tempo':
                return mido.tempo2bpm(message.tempo)
    return None


def get_midi_time_signature(midi_file: MidiFile) -> tuple[int, int] | None:
    for track in midi_file.tracks:
        for message in track:
            if message.type == 'time_signature':
                return (message.numerator, message.denominator)
    return None


MM_PER_INCH = 25.4
type Point_T = tuple[float, float]
type Vector_T = Point_T
type XY_T = tuple[Point_T, Point_T]


def mm_to_pixel(x: float, /, ppi: float) -> float:
    return x / MM_PER_INCH * ppi


def pixel_to_mm(x: float, /, ppi: float) -> float:
    return x * MM_PER_INCH / ppi


@overload
def pos_mm_to_pixel(pos: Point_T,
                    ppi: float,
                    method: None = ...) -> tuple[float, float]: ...


@overload
def pos_mm_to_pixel(pos: Point_T,
                    ppi: float,
                    method: Literal['floor', 'round'] = ...) -> tuple[int, int]: ...


def pos_mm_to_pixel(pos: Point_T,
                    ppi: float,
                    method: Literal['floor', 'round', None] = 'round') -> tuple[float, float] | tuple[int, int]:
    x, y = pos
    match method:
        case None:
            return (mm_to_pixel(x, ppi), mm_to_pixel(y, ppi))
        case 'floor':
            return (math.floor(mm_to_pixel(x, ppi)), math.floor(mm_to_pixel(y, ppi)))
        case 'round':
            return (round(mm_to_pixel(x, ppi)), round(mm_to_pixel(y, ppi)))
        case _:
            raise ValueError


@lru_cache
def _get_empty_draw() -> ImageDraw.ImageDraw:
    return ImageDraw.Draw(Image.new('RGBA', (0, 0)))


def get_text_height(text: str, font: ImageFont.FreeTypeFont, **kwargs: Any) -> int:
    return (_get_empty_draw().multiline_textbbox((0, 0), text, font, 'la', **kwargs)[3]
            - _get_empty_draw().multiline_textbbox((0, 0), text, font, 'ld', **kwargs)[3])


def calc_alpha(radius: float, distance: float) -> float:
    if distance <= radius - 1 / 2:
        return 1
    if distance >= radius + 1 / 2:
        return 0
    return radius + 1 / 2 - distance


def mix_number(foreground: float, background: float, alpha: float) -> float:
    return foreground * alpha + background * (1 - alpha)


# type RGBA = tuple[float, float, float, float]

# def mix_tuple(foreground: tuple[float, ...], background: tuple[float, ...], alpha: float) -> tuple[float, ...]:
#     assert len(foreground) == len(background), ValueError('foreground and background must have same length.')
#     return tuple(mix_number(x, y, alpha) for x, y in zip(foreground, background))

# def round_tuple(x: tuple[float, ...], /) -> tuple[int, ...]:
#     return tuple(round(y) for y in x)

# def mix_color_number(foreground_number: float,
#                      foreground_alpha: float,
#                      background_number: float,
#                      background_alpha: float,
#                      alpha: float) -> float:
#     return ((background_number * background_alpha * (1 - alpha * foreground_alpha)
#              + foreground_number * alpha * foreground_alpha)
#             / (background_alpha + alpha * foreground_alpha - background_alpha * alpha * foreground_alpha))

# def mix_color_alpha(foreground_alpha: float, background_alpha: float, alpha: float) -> float:
#     return background_alpha + alpha * foreground_alpha - background_alpha * alpha * foreground_alpha

# def mix_color(foreground: RGBA, background: RGBA, alpha: float) -> RGBA:
#     foreground_color = foreground[:3]
#     foreground_alpha = foreground[3]
#     background_color = background[:3]
#     background_alpha = background[3]
#     if alpha == 0:
#         return background
#     elif alpha == 1:
#         return foreground
#     else:
#         return (tuple(mix_color_number(foreground_number, foreground_alpha, background_number, background_alpha, alpha)
#                       for foreground_number, background_number in zip(foreground_color, background_color))
#                 + (mix_color_alpha(foreground_alpha, background_alpha, alpha),))


def _get_circle_image(center: Point_T,
                      radius: float,
                      color) -> tuple[Image.Image, tuple[int, int]]:
    center_x, center_y = center
    color_rgba: tuple[int, int, int, int] = ImageColor.getcolor(color, 'RGBA')  # type: ignore
    color_rgb: tuple[int, int, int] = color_rgba[:3]
    color_alpha: int = color_rgba[3]
    left_x: int = math.floor(center_x - radius)
    right_x: int = math.ceil(center_x + radius)
    top_y: int = math.floor(center_y - radius)
    bottom_y: int = math.ceil(center_y + radius)
    layer_width: int = right_x - left_x
    layer_height: int = bottom_y - top_y
    layer: Image.Image = Image.new('RGBA', (layer_width, layer_height))
    draw: ImageDraw.ImageDraw = ImageDraw.Draw(layer)
    for x_in_layer in range(layer_width):
        for y_in_layer in range(layer_height):
            x: float = x_in_layer + left_x + 1 / 2
            y: float = y_in_layer + top_y + 1 / 2
            distance: float = math.dist(center, (x, y))
            alpha: float = calc_alpha(radius, distance)
            if alpha == 0:
                continue
            layer_color: tuple[int, int, int, int] = color_rgb + (round(color_alpha * alpha),)
            draw.point((x_in_layer, y_in_layer), layer_color)
    return layer, (left_x, top_y)


@lru_cache
def _get_circle_image_with_cache(center: Point_T,
                                 radius: float,
                                 color: Any) -> tuple[Image.Image, tuple[int, int]]:
    return _get_circle_image(center, radius, color)


def get_circle_image(center: Point_T,
                     radius: float,
                     color) -> tuple[Image.Image, tuple[int, int]]:
    if center == (1 / 2, 1 / 2):
        return _get_circle_image_with_cache(center, radius, color)
    else:
        return _get_circle_image(center, radius, color)


def draw_circle(image: Image.Image,
                center: Point_T,
                radius: float,
                color,
                anti_alias: Literal['off', 'fast', 'accurate'] = 'fast') -> None:
    match anti_alias:
        case 'off':
            draw: ImageDraw.ImageDraw = ImageDraw.Draw(image)
            x, y = center
            xy: tuple[tuple[int, int], tuple[int, int]] = ((round(x - radius), round(y - radius)),
                                                           (round(x + radius), round(y + radius)))
            draw.ellipse(xy, color, width=0)

        case 'fast':
            center_x, center_y = center
            circle_image, destination = get_circle_image((1 / 2, 1 / 2), radius, color)
            delta_x, delta_y = destination
            image.alpha_composite(circle_image, (math.floor(center_x) + delta_x, math.floor(center_y) + delta_y))

        case 'accurate':
            circle_image, destination = get_circle_image(center, radius, color)
            image.alpha_composite(circle_image, destination)

        case _:
            raise ValueError


def dot_product_2d(vector_0: Vector_T, vector_1: Vector_T, /) -> float:
    x0, y0 = vector_0
    x1, y1 = vector_1
    return x0 * x1 + y0 * y1


def distance_point_to_line_ABC(point: Point_T, line_A: float, line_B: float, line_C: float, abs_: bool = True) -> float:
    x, y = point
    distance_with_sign: float = (line_A * x + line_B * y + line_C) / math.hypot(line_A, line_B)
    return abs(distance_with_sign) if abs_ else distance_with_sign


def distance_point_to_line_xy(point: Point_T, line_xy: XY_T) -> float:
    (x0, y0), (x1, y1) = line_xy
    line_A: float = y1 - y0
    line_B: float = x0 - x1
    line_C: float = x1 * y0 - x0 * y1
    return distance_point_to_line_ABC(point, line_A, line_B, line_C)


def distance_point_to_line_segment(point: Point_T, line_xy: XY_T) -> float:
    x, y = point
    (x0, y0), (x1, y1) = line_xy
    vector_AB: Vector_T = (x1 - x0, y1 - y0)
    vector_AP: Vector_T = (x - x0, y - y0)
    vector_BP: Vector_T = (x - x1, y - y1)
    is_in_A_side: bool = dot_product_2d(vector_AB, vector_AP) < 0
    is_in_B_side: bool = dot_product_2d(vector_AB, vector_BP) >= 0  # Vector_BA * Vector_BP < 0
    if is_in_A_side:
        return math.dist(point, line_xy[0])
    elif is_in_B_side:
        return math.dist(point, line_xy[1])
    else:  # middle
        return distance_point_to_line_xy(point, line_xy)


def get_line_image(line_xy: XY_T,
                   color,
                   width: float) -> tuple[Image.Image, tuple[int, int]]:
    (x0, y0), (x1, y1) = line_xy
    delta_x: float = x1 - x0
    delta_y: float = y1 - y0
    if abs(delta_y) > abs(delta_x):  # Avoid ZeroDivisionError or accuracy loss
        image, (destination_y, destination_x) = get_line_image(((y0, x0), (y1, x1)), color, width)
        return image.transpose(Image.Transpose.TRANSVERSE), (destination_x, destination_y)

    slope: float = delta_y / delta_x
    sec_alpha: float = math.hypot(1, slope)

    color_rgba: tuple[int, int, int, int] = ImageColor.getcolor(color, 'RGBA')  # type: ignore
    color_rgb: tuple[int, int, int] = color_rgba[:3]
    color_alpha: int = color_rgba[3]

    left_x: int = math.floor(min(x0, x1) - width / 2)
    right_x: int = math.ceil(max(x0, x1) + width / 2)
    top_y: int = math.floor(min(y0, y1) - width / 2)
    bottom_y: int = math.ceil(max(y0, y1) + width / 2)
    layer_width: int = right_x - left_x
    layer_height: int = bottom_y - top_y
    layer: Image.Image = Image.new('RGBA', (layer_width, layer_height))
    draw: ImageDraw.ImageDraw = ImageDraw.Draw(layer)
    for x_in_layer in range(layer_width):
        x: float = x_in_layer + left_x + 1 / 2
        intersection_y: float = slope * (x - x0) + y0
        down_border: float = intersection_y - (width / 2 + 1 / 2) * sec_alpha
        up_border: float = intersection_y + (width / 2 + 1 / 2) * sec_alpha
        possible_min: int = max(0, round(down_border) - top_y)
        possible_max: int = min(layer_height, round(up_border) - top_y)
        for y_in_layer in range(possible_min, possible_max):
            y: float = y_in_layer + top_y + 1 / 2
            distance: float = distance_point_to_line_segment((x, y), line_xy)
            alpha: float = calc_alpha(width / 2, distance)
            if alpha == 0:
                continue
            layer_color: tuple[int, int, int, int] = color_rgb + (round(color_alpha * alpha),)
            draw.point((x_in_layer, y_in_layer), layer_color)
    return layer, (left_x, top_y)


def draw_line(image: Image.Image,
              line_xy: XY_T,
              width: float,
              color,
              anti_alias: Literal['off', 'accurate'] = 'accurate') -> None:
    (x0, y0), (x1, y1) = line_xy
    match anti_alias:
        case 'off':
            draw: ImageDraw.ImageDraw = ImageDraw.Draw(image)
            line_xy = (math.floor(x0), math.floor(y0)), (math.floor(x1), math.floor(y1))
            draw.line(line_xy, color, round(width))

        case 'accurate':
            line_image, destination = get_line_image(line_xy, color, width)
            image.alpha_composite(line_image, destination)

        case _:
            raise ValueError
