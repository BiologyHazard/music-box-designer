import json
import struct
from collections import defaultdict
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Annotated, Any, BinaryIO, ClassVar, Literal, NamedTuple, Self

import mido.midifiles.tracks
from mido import Message, MetaMessage, MidiFile, MidiTrack
from pydantic import BaseModel, Field, PlainSerializer

from .consts import MIDI_DEFAULT_TICKS_PER_BEAT
from .log import logger

FMP_DEFAULT_TICKS_PER_BEAT = 96


class TimeSignature(NamedTuple):
    numerator: int = 4
    denominator: int = 4


@dataclass(frozen=True)
class FmpNote:
    pitch: int
    '''音高'''
    tick: int
    '''音符起始位置的刻数'''
    duration: int
    '''音符持续时间的刻数'''
    velocity: int
    '''音符的力度'''

    def copy(self, **kwargs) -> Self:
        return self.__class__(**(self.__dict__ | kwargs))


@dataclass
class FmpTrack:
    name: str = ''
    channel: int = 0
    index: int = 0
    color: int = 7
    muted: bool = False
    notes: list[FmpNote] = field(default_factory=lambda: [])

    def transpose(self, transposition: int) -> None:
        self.notes = [note.__class__(note.pitch + transposition, note.tick, note.duration, note.velocity)
                      for note in self.notes
                      if note.pitch + transposition in range(128)]

    def set_velocity(self, velocity: int) -> None:
        if not 0 <= velocity <= 255:
            raise ValueError('velocity must be a int between 0 and 255.')
        self.notes = [note.__class__(note.pitch, note.tick, note.duration, velocity)
                      for note in self.notes]


@dataclass
class FmpTimeMark:
    tick: int = 0


@dataclass
class FmpBpmTimeSignatureMark(FmpTimeMark):
    change_tempo: bool = False
    tempo: int = 500000
    change_time_signature: bool = False
    time_signature: TimeSignature = TimeSignature(4, 4)


@dataclass
class FmpCommentMark(FmpTimeMark):
    comment: str = ''


@dataclass
class FmpEndMark(FmpTimeMark):
    pass


# type EffectorName = Literal['Effect_Reverb', 'Effect_Equalizer', 'Effect_Compressor', 'Effect_Limiter']

def to_str(x):
    return str(x)


type FloatSerializeToStr = Annotated[float, PlainSerializer(to_str)]


class FmpEffectorValue(BaseModel):
    pass


class FmpReverbEffectorValue(FmpEffectorValue):
    mix: FloatSerializeToStr = Field(0.2, alias='_mix')
    room_size: FloatSerializeToStr = 0.75
    damping: FloatSerializeToStr = 0.7
    width: FloatSerializeToStr = 1.0


class FmpEqualizerEffectorValue(FmpEffectorValue):
    values: list[FloatSerializeToStr] = Field(default_factory=lambda: [0.0] * 10)


class FmpCompressorEffectorValue(FmpEffectorValue):
    threshold: FloatSerializeToStr = -10.0
    ratio: FloatSerializeToStr = 10.0
    gain: FloatSerializeToStr = 0.0
    attack: FloatSerializeToStr = 0.01
    release: FloatSerializeToStr = 0.2
    knee_width: FloatSerializeToStr = 1.0


class FmpLimiterEffectorValue(FmpEffectorValue):
    threshold: FloatSerializeToStr = 0.0
    ceiling: FloatSerializeToStr = 0.0
    release: FloatSerializeToStr = 0.5


@dataclass
class FmpEffector:
    effector_name: ClassVar[str]
    enabled: bool = True
    mix_level: float = 1.0
    effect_values: FmpEffectorValue = field(default_factory=FmpEffectorValue)


@dataclass
class FmpReverbEffector(FmpEffector):
    effector_name: ClassVar[Literal['Effect_Reverb']] = 'Effect_Reverb'


@dataclass
class FmpEqualizerEffector(FmpEffector):
    effector_name: ClassVar[Literal['Effect_Equalizer']] = 'Effect_Equalizer'


@dataclass
class FmpCompressorEffector(FmpEffector):
    effector_name: ClassVar[Literal['Effect_Compressor']] = 'Effect_Compressor'


@dataclass
class FmpLimiterEffector(FmpEffector):
    effector_name: ClassVar[Literal['Effect_Limiter']] = 'Effect_Limiter'


@dataclass
class FmpChannel:
    index: int = 0
    volume: int = 1000
    pan: int = 500
    solo: bool = False
    muted: bool = False
    soundfont_name: str = ''
    soundfont_index: int = 0
    participate_generate: bool | None = None
    transposition: int | None = None
    note_trigger_mode: int | None = None
    inherit: bool | None = None
    range: list[int] | None = None
    effectors: list[FmpEffector] = field(default_factory=list)


# @dataclass
# class FmpMasterChannel(FmpChannel):
#     pass


# @dataclass
# class FmpNormalChannel(FmpChannel):
#     participate_generate: bool = True
#     transposition: int = 0
#     note_trigger_mode: int = 0
#     inherit: bool = True
#     range: list[int] = field(default_factory=lambda: list(range(128)))


instrument_presets: dict[str, dict[str, str]] = {
    'Instrument_Preset_PaperStripMusicBox_30Note': {
        'class': 'Instrument_PaperStripMusicBox',
        'effective_trigger_spacing': '7',
        'quarter_note_unit_lenght': '8',
        'default_timbre': 'WangMusicBox,0',
        'note_trigger_mode': 'Pizzicato',
        'transpose': '5',
        'range': '48,50,55,57,59,60,62,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,86,88',
    },
    'Instrument_Preset_PaperStripMusicBox_20Note': {
        'class': 'Instrument_PaperStripMusicBox',
        'effective_trigger_spacing': '7',
        'quarter_note_unit_lenght': '8',
        'default_timbre': 'WangMusicBox,0',
        'note_trigger_mode': 'Pizzicato',
        'transpose': '0',
        'range': '60,62,64,65,67,69,71,72,74,76,77,79,81,83,84,86,88,89,91,93',
    },
    'Instrument_Preset_PaperStripMusicBox_15Note': {
        'class': 'Instrument_PaperStripMusicBox',
        'effective_trigger_spacing': '7',
        'quarter_note_unit_lenght': '8',
        'default_timbre': 'WangMusicBox,0',
        'note_trigger_mode': 'Pizzicato',
        'transpose': '8',
        'range': '60,62,64,65,67,69,71,72,74,76,77,79,81,83,84',
    },
}

default_instrument_cfgs: dict[str, dict[str, str]] = {
    'Instrument': {
        'default_timbre': '233PopRockBank,0',
        'note_trigger_mode': 'Sustain',
        'transpose': '0',
        'range': '0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,'
                 '36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,'
                 '69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95,96,97,98,99,100,'
                 '101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,123,124,'
                 '125,126,127',
    },
    'Instrument_PaperStripMusicBox': {
        'class': 'Instrument_PaperStripMusicBox',
        'effective_trigger_spacing': '7',
        'quarter_note_unit_lenght': '8',
        'default_timbre': 'WangMusicBox,0',
        'note_trigger_mode': 'Pizzicato',
        'transpose': '0',
        'range': '0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,'
                 '36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,'
                 '69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95,96,97,98,99,100,'
                 '101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,123,124,'
                 '125,126,127',
    }
}

default_dgprogram_cfg: dict[str, Any] = {
    'class': 'GP_PaperStripMusicBox_PDFProgram',
    'title': None,
    'subtitle': None,
}

default_dgstyle_cfg: dict[str, str] = {
    'class': 'GS_PaperStripMusicBox_Style',
    'note_color': 'Black',
    'note_size': '1.8',
    'grid_spacing': '2',
    'big_header': 'true',
    'header_height': '48',
    'title_offset': '16',
    'header_cut_line_margin': '16',
    'title_color': 'Black',
    'subtitle_color': 'Black',
    'interior_title': 'Without',
    'interior_title_color': 'rgba32(0.00,0.00,0.00,0.40)',
    'interior_subtitle_color': 'rgba32(0.00,0.00,0.00,0.40)',
    'notename_color': 'Black',
    'header_info_color': 'Black',
    'page_size': '210,297',
    'auto_size': 'false',
    'page_margin': '0.00,0.00,0.00,0.00',
    'strip_top_bottom_margin': '8',
    'strip_left_right_margin': '6',
    'background_color': 'White',
    'include_big_page_number': 'false',
    'big_page_number_color': 'rgba32(0.00,0.00,0.00,0.25)',
    'include_section_line': 'true',
    'section_line_font_color': 'Black',
    'group': '6',
    'splicing_type': 'Flat',
    'overlap_height_grid': '8',
    'custom_watermark_enabled': 'false',
    'custom_watermark': '自定义水印',
    'h_line_thickness': '0.15',
    'h_line_color': 'rgba32(0.35,0.35,0.35,1.00)',
    'half_beat_line_thickness': '0.15',
    'half_beat_line_color': 'rgba32(0.35,0.35,0.35,1.00)',
    'half_beat_line_style': 'Dashed',
    'v_line_thickness': '0.15',
    'v_line_color': 'rgba32(0.35,0.35,0.35,1.00)',
    'group_line_thickness': '0.35',
    'group_line_color': 'Gray',
    'section_line_thickness': '0.35',
    'section_line_color': 'rgba32(0.00,0.71,1.00,1.00)', 'bpm_and_time_signature_thickness': '0.35',
    'bpm_and_time_signature_color': 'rgba32(1.00,0.52,0.00,1.00)',
    'comment_thickness': '0.35',
    'comment_color': 'DarkGreen',
    'cut_line_thickness': '0.15',
    'cut_line_color': 'Black',
}


@dataclass
class FmpFile:
    """
    You should not initialize an FmpFile instance directly.
    Use `FmpFile.new(...)` to create one.
    """
    file_format = 1
    version: tuple[int, int, int] = (3, 1, 0)
    compatible_version: tuple[int, int, int] = (3, 1, 0)
    tempo: int = 500000
    time_signature: TimeSignature = TimeSignature(4, 4)
    scale: int = 100000
    ticks_per_beat: int = FMP_DEFAULT_TICKS_PER_BEAT
    instrument: str = 'Instrument_Preset_PaperStripMusicBox_30Note'
    note: str | None = None
    '''`' [ **** This file created by FairyMusicBox - www.fairymusicbox.com **** ] '`by default'''
    show_info_on_open: bool | None = None
    title: str | None = None
    subtitle: str | None = None
    comment: str | None = None
    tracks: list[FmpTrack] = field(default_factory=list)
    time_marks: list[FmpTimeMark] = field(default_factory=list)
    channels: list[FmpChannel] = field(default_factory=list)
    ignore_issues: str | None = ''
    instrument_cfg: dict[str, str] | None = None
    dgprogram_cfg: dict[str, Any] | None = None
    dgstyle_cfg: dict[str, str] | None = None

    file_path: Path | None = None

    @classmethod
    def new(cls,
            instrument: str = 'Instrument_Preset_PaperStripMusicBox_30Note',
            instrument_cfg: dict[str, str] | None = None,
            title: str = '',
            subtitle: str = '',
            comment: str = '',
            add_channel: bool = True,
            add_empty_track: bool = True) -> Self:
        # I'm not sure whether changing the fmp_file.ticks_per_beat attribute to a value other than
        # FMP_DEFAULT_TICKS_PER_BEAT (=96) is a good behavior. So by now the parameter is not added to this function.
        fmp_file: Self = cls(title=title,
                             subtitle=subtitle,
                             comment=comment,
                             instrument=instrument)
        if instrument not in instrument_presets | default_instrument_cfgs:
            logger.error(f'Unrecognized instrument: {instrument}. File may fail to be opened by FairyMusicBox 3.0.0.')

        if instrument_cfg is not None:
            fmp_file.instrument_cfg = instrument_cfg
            if instrument in instrument_presets:
                logger.error(f'{instrument} is a preset, instrument_cfg SHOULD NOT be customized.')
        else:
            if instrument in default_instrument_cfgs:
                fmp_file.instrument_cfg = default_instrument_cfgs[instrument]
            if instrument in instrument_presets | default_instrument_cfgs:
                instrument_cfg = (instrument_presets | default_instrument_cfgs)[instrument]

        if 'PaperStripMusicBox' in instrument:
            fmp_file.dgprogram_cfg = default_dgprogram_cfg
            fmp_file.dgstyle_cfg = default_dgstyle_cfg

        if (add_channel
                and instrument_cfg is not None
                and 'default_timbre' in instrument_cfg):
            soundfont_name, soundfont_index = instrument_cfg['default_timbre'].rsplit(',', 1)
            channel = FmpChannel(soundfont_name=soundfont_name,
                                 soundfont_index=int(soundfont_index))
            fmp_file.channels.append(channel)

        if add_empty_track:
            fmp_file.tracks.append(FmpTrack())

        return fmp_file

    def get_instrument_cfg(self) -> dict[str, str]:
        if self.instrument_cfg is not None:
            return self.instrument_cfg
        if self.instrument in instrument_presets:
            return instrument_presets[self.instrument]
        if self.instrument in default_instrument_cfgs:
            return default_instrument_cfgs[self.instrument]
        raise ValueError(f'{self.instrument} is not in presets, and has no default instrument_cfg.')

    @classmethod
    def open(cls, file: str | Path | BinaryIO) -> Self:
        if isinstance(file, (str, Path)):
            with open(file, 'rb') as fp:
                self: Self = cls._load_from_file(fp)
            self.file_path = Path(file)
        else:
            self = cls._load_from_file(file)
            self.file_path = None
        return self

    @classmethod
    def _load_from_file(cls, file: BinaryIO) -> Self:
        fmp_file: Self = cls()

        # 头部数据
        assert file.read(3) == b'FMP'
        fmp_file.file_format = read_int(file, 2)

        fmp_file.version = (read_int(file, 2, signed=True),
                            read_int(file, 2, signed=True),
                            read_int(file, 2, signed=True))
        fmp_file.compatible_version = (read_int(file, 2, signed=True),
                                       read_int(file, 2, signed=True),
                                       read_int(file, 2, signed=True))

        _: int = read_int(file, 4)
        assert file.read(4) == bytes(4)

        fmp_file.tempo = read_int(file, 4)
        numerator: int = read_int(file, 2)
        denominator: int = read_int(file, 2)
        fmp_file.time_signature = TimeSignature(numerator, denominator)
        fmp_file.scale = read_int(file, 4)
        fmp_file.ticks_per_beat = read_int(file, 2)

        assert file.read(4) == bytes(4)

        instrument_length: int = read_int(file, 2)
        fmp_file.instrument = file.read(instrument_length).decode()

        assert file.read(4) == b'\x03\x00\x00\x00'

        # 工程信息
        num: int = read_int(file, 4)
        for _ in range(num):
            type_length: int = read_int(file, 1)
            info_length: int = read_int(file, 3)
            info_type: str = file.read(type_length).decode()
            match info_type:
                case 'note':
                    fmp_file.note = file.read(info_length).decode()
                case 'sio':
                    fmp_file.show_info_on_open = read_bool(file)
                case 'ti':
                    fmp_file.title = file.read(info_length - 1).decode()
                    assert file.read(1) == bytes(1)
                case 'sti':
                    fmp_file.subtitle = file.read(info_length - 1).decode()
                    assert file.read(1) == bytes(1)
                case 'cmt':
                    fmp_file.comment = file.read(info_length - 1).decode()
                    assert file.read(1) == bytes(1)
                case _:
                    raise ValueError

        # 轨道
        assert file.read(3) == b'TRK'
        file_magic_num: int = read_int(file, 4)  # file_magic_num = 总音符数*12 + track_name总字节数 + 轨道数*40 + 8
        track_count: int = read_int(file, 4)
        for _ in range(track_count):
            track = FmpTrack()

            assert file.read(1) == b'\x01'
            track_magic_num: int = read_int(file, 4)  # track_magic_num = 音符数*12 + track_name字节数 + 39
            track_name_length_add_19: int = read_int(file, 4)
            track_name_length: int = read_int(file, 2)
            assert track_name_length_add_19 == track_name_length + 19

            track.name = file.read(track_name_length).decode()
            track.channel = read_int(file, 4, signed=True)
            track.index = read_int(file, 4)
            track.color = read_int(file, 4)
            track.muted = read_bool(file)
            assert file.read(4) == bytes(4)
            note_count_mul_12_add_12: int = read_int(file, 4)
            note_count: int = read_int(file, 4)
            assert note_count_mul_12_add_12 == note_count * 12 + 12
            assert track_magic_num == note_count * 12 + track_name_length + 39
            assert file.read(4) == b'\x01\x00\x01\x0A'

            # 音符
            for _ in range(note_count):
                assert file.read(2) == b'\x10\x00'
                tick: int = read_int(file, 4)
                pitch: int = read_int(file, 1)
                duration: int = read_int(file, 4)
                velocity: int = read_int(file, 1)
                note = FmpNote(pitch, tick, duration, velocity)
                track.notes.append(note)

            fmp_file.tracks.append(track)

        # 时间标记
        assert file.read(3) == b'TMK'
        time_mark_length: int = read_int(file, 4)
        # time_mark_length = bpm/节拍标记个数*17 + 注释个数*9 + 注释总字节数 + 结束标记*7 + 8，也等于直到 'CNL' 的总字节数
        time_mark_count: int = read_int(file, 4)
        for _ in range(time_mark_count):
            mark_type: int = read_int(file, 1)
            match mark_type:
                case 1:  # bpm / 节拍标记
                    time_mark = FmpBpmTimeSignatureMark()
                    assert file.read(2) == b'\x0E\x00'
                    time_mark.tick = read_int(file, 4)
                    time_mark.change_tempo = read_bool(file)
                    time_mark.tempo = read_int(file, 4)
                    time_mark.change_time_signature = read_bool(file)
                    numerator = read_int(file, 2)
                    denominator = read_int(file, 2)
                    time_mark.time_signature = TimeSignature(numerator, denominator)
                case 2:  # 注释
                    time_mark = FmpCommentMark()
                    comment_length_add_6: int = read_int(file, 2)
                    time_mark.tick = read_int(file, 4)
                    comment_length: int = read_int(file, 2)
                    assert comment_length_add_6 == comment_length + 6
                    time_mark.comment = file.read(comment_length).decode()
                case 3:  # 结束标记
                    time_mark = FmpEndMark()
                    assert file.read(2) == b'\x04\x00'
                    time_mark.tick = read_int(file, 4)
                case _:
                    raise ValueError
            fmp_file.time_marks.append(time_mark)

        # 通道
        assert file.read(3) == b'CNL'
        _: int = read_int(file, 4)
        channel_count: int = read_int(file, 4)
        for i in range(channel_count):
            # if i == 0:
            #     channel = FmpMasterChannel()
            # else:
            #     channel = FmpNormalChannel()
            channel = FmpChannel()
            soundfont_name_length_add_22: int = read_int(file, 4)
            assert file.read(2) == bytes(2)
            channel.index = read_int(file, 4)
            channel.volume = read_int(file, 2)
            channel.pan = read_int(file, 2)
            channel.solo = read_bool(file)
            channel.muted = read_bool(file)
            soundfont_name_length: int = read_int(file, 2)
            assert soundfont_name_length_add_22 == soundfont_name_length + 22
            channel.soundfont_name = file.read(soundfont_name_length).decode()
            channel.soundfont_index = read_int(file, 4)
            num: int = read_int(file, 4)
            # assert num == 0 or isinstance(channel, FmpNormalChannel)
            # if isinstance(channel, FmpNormalChannel):
            if True:
                for _ in range(num):
                    key_length: int = read_int(file, 1)
                    value_length: int = read_int(file, 3)
                    key: str = file.read(key_length).decode()
                    match key:
                        case 'pg':
                            assert value_length == 1
                            channel.participate_generate = read_bool(file)
                        case 'tp':
                            assert value_length == 4
                            channel.transposition = read_int(file, value_length)
                        case 'ntm':
                            assert value_length == 1
                            channel.note_trigger_mode = read_int(file, value_length)
                        case 'ir':
                            assert value_length == 1
                            channel.inherit = read_bool(file)
                        case 'rg':
                            channel.range = [read_int(file, 1) for _ in range(value_length)]
                        case _:
                            raise ValueError

            _ = read_int(file, 4)
            effector_num = read_int(file, 4)
            for _ in range(effector_num):
                effector_name_length = read_int(file, 2)
                effector_name = file.read(effector_name_length).decode()
                match effector_name:
                    case 'Effect_Reverb':
                        effector = FmpReverbEffector()
                        value_class = FmpReverbEffectorValue
                    case 'Effect_Equalizer':
                        effector = FmpEqualizerEffector()
                        value_class = FmpEqualizerEffectorValue
                    case 'Effect_Compressor':
                        effector = FmpCompressorEffector()
                        value_class = FmpCompressorEffectorValue
                    case 'Effect_Limiter':
                        effector = FmpLimiterEffector()
                        value_class = FmpLimiterEffectorValue
                    case _:
                        raise ValueError
                effector.enabled = read_bool(file)
                effector.mix_level = read_float(file, 4)
                num = read_int(file, 4)
                effect_values_str = file.read(num).decode()
                effector.effect_values = value_class.model_validate_json(effect_values_str)
                channel.effectors.append(effector)

            fmp_file.channels.append(channel)

        num: int = read_int(file, 4)
        for _ in range(num):
            key_length: int = read_int(file, 1)
            value_length: int = read_int(file, 3)
            key: str = file.read(key_length).decode()
            match key:
                case 'ignore_issues':
                    fmp_file.ignore_issues = file.read(value_length).decode()
                case 'instrument_cfg':
                    fmp_file.instrument_cfg = json.loads(file.read(value_length - 1).decode().replace('\n', '\\n'))
                    assert file.read(1) == bytes(1)
                case 'dgprogram_cfg':
                    fmp_file.dgprogram_cfg = json.loads(file.read(value_length - 1).decode().replace('\n', '\\n'))
                    assert file.read(1) == bytes(1)
                case 'dgstyle_cfg':
                    fmp_file.dgstyle_cfg = json.loads(file.read(value_length - 1).decode().replace('\n', '\\n'))
                    assert file.read(1) == bytes(1)
                case _:
                    raise ValueError
        assert not file.read()

        return fmp_file

    def transpose(self, transposition: int) -> None:
        for track in self.tracks:
            track.transpose(transposition)

    def set_velocity(self, velocity: int) -> None:
        for track in self.tracks:
            track.set_velocity(velocity)

    def save(self, file: str | Path | BinaryIO) -> None:
        data = self.to_bytes()
        if isinstance(file, (str, Path)):
            with open(file, 'wb') as fp:
                fp.write(data)
        else:
            file.write(data)

    def _save_to_file(self, file: BinaryIO) -> None:
        file.write(b'FMP')
        write_int(file, self.file_format, 2)
        for version_part in self.version:
            write_int(file, version_part, 2)
        for compatible_version_part in self.compatible_version:
            write_int(file, compatible_version_part, 2)

        with LengthWriter(file, 0, 4):
            file.write(bytes(4))
            write_int(file, self.tempo, 4)
            write_int(file, self.time_signature.numerator, 2)
            write_int(file, self.time_signature.denominator, 2)
            write_int(file, self.scale, 4)
            write_int(file, self.ticks_per_beat, 2)
            file.write(bytes(4))
            write_int(file, len(self.instrument.encode()), 2)
            file.write(self.instrument.encode())
            file.write(b'\x03\x00\x00\x00')

        num: int = (self.note is not None) + (self.show_info_on_open is not None) + (self.title is not None) + (self.subtitle is not None) + (self.comment is not None)
        write_int(file, num, 4)
        if self.note is not None:
            write_int(file, 4, 1)
            write_int(file, len(self.note.encode()), 3)
            file.write(b'note')
            file.write(self.note.encode())
        if self.show_info_on_open is not None:
            write_int(file, 3, 1)
            write_int(file, 1, 3)
            file.write(b'sio')
            write_bool(file, self.show_info_on_open)
        if self.title is not None:
            write_int(file, 2, 1)
            write_int(file, len(self.title.encode()) + 1, 3)
            file.write(b'ti')
            file.write(self.title.encode())
            file.write(bytes(1))
        if self.subtitle is not None:
            write_int(file, 3, 1)
            write_int(file, len(self.subtitle.encode()) + 1, 3)
            file.write(b'sti')
            file.write(self.subtitle.encode())
            file.write(bytes(1))
        if self.comment is not None:
            write_int(file, 3, 1)
            write_int(file, len(self.comment.encode()) + 1, 3)
            file.write(b'cmt')
            file.write(self.comment.encode())
            file.write(bytes(1))

        file.write(b'TRK')
        with LengthWriter(file, 0, 4):
            write_int(file, len(self.tracks), 4)
            for track in self.tracks:
                file.write(b'\x01')
                write_int(file, len(track.notes) * 12 + len(track.name) + 39, 4)
                write_int(file, len(track.name.encode()) + 19, 4)
                write_int(file, len(track.name.encode()), 2)
                file.write(track.name.encode())
                write_int(file, track.channel, 4)
                write_int(file, track.index, 4)
                write_int(file, track.color, 4)
                write_bool(file, track.muted)
                file.write(bytes(4))
                write_int(file, len(track.notes) * 12 + 12, 4)
                write_int(file, len(track.notes), 4)
                file.write(b'\x01\x00\x01\x0A')
                for note in track.notes:
                    file.write(b'\x10\x00')
                    write_int(file, note.tick, 4)
                    write_int(file, note.pitch, 1)
                    write_int(file, note.duration, 4)
                    write_int(file, note.velocity, 1)

        file.write(b'TMK')
        with LengthWriter(file, 0, 4):
            write_int(file, len(self.time_marks), 4)
            for time_mark in self.time_marks:
                if isinstance(time_mark, FmpBpmTimeSignatureMark):
                    write_int(file, 1, 1)
                    write_int(file, 14, 2)
                    write_int(file, time_mark.tick, 4)
                    write_bool(file, time_mark.change_tempo)
                    write_int(file, time_mark.tempo, 4)
                    write_bool(file, time_mark.change_time_signature)
                    write_int(file, time_mark.time_signature.numerator, 2)
                    write_int(file, time_mark.time_signature.denominator, 2)
                elif isinstance(time_mark, FmpCommentMark):
                    write_int(file, 2, 1)
                    write_int(file, len(time_mark.comment.encode()) + 6, 2)
                    write_int(file, time_mark.tick, 4)
                    write_int(file, len(time_mark.comment.encode()), 2)
                    file.write(time_mark.comment.encode())
                elif isinstance(time_mark, FmpEndMark):
                    write_int(file, 3, 1)
                    write_int(file, 4, 2)
                    write_int(file, time_mark.tick, 4)
                else:
                    raise TypeError

        file.write(b'CNL')
        with LengthWriter(file, 0, 4):
            write_int(file, len(self.channels), 4)
            for channel in self.channels:
                # # 我实在是不知道为什么 soundfont_name == 'WangMusicBox' 的时候会报“通道元信息读取失败”，汪汪怎么你了
                # if channel.soundfont_name == 'WangMusicBox':
                #     soundfont_name = ''
                # else:
                #     soundfont_name = channel.soundfont_name
                with LengthWriter(file, 0, 4):
                    file.write(bytes(2))
                    write_int(file, channel.index, 4)
                    write_int(file, channel.volume, 2)
                    write_int(file, channel.pan, 2)
                    write_bool(file, channel.solo)
                    write_bool(file, channel.muted)
                    write_int(file, len(channel.soundfont_name.encode()), 2)
                    # write_int(file, len(soundfont_name.encode()), 2)
                    file.write(channel.soundfont_name.encode())
                    # file.write(soundfont_name.encode())
                    write_int(file, channel.soundfont_index, 4)

                num = (channel.participate_generate is not None) + (channel.transposition is not None) + (channel.note_trigger_mode is not None) + (channel.inherit is not None) + (channel.range is not None)
                write_int(file, num, 4)
                if channel.participate_generate is not None:
                    write_int(file, 2, 1)
                    write_int(file, 1, 3)
                    file.write(b'pg')
                    write_bool(file, channel.participate_generate)
                if channel.transposition is not None:
                    write_int(file, 2, 1)
                    write_int(file, 4, 3)
                    file.write(b'tp')
                    write_int(file, channel.transposition, 4)
                if channel.note_trigger_mode is not None:
                    write_int(file, 3, 1)
                    write_int(file, 1, 3)
                    file.write(b'ntm')
                    write_int(file, channel.note_trigger_mode, 1)
                if channel.inherit is not None:
                    write_int(file, 2, 1)
                    write_int(file, 1, 3)
                    file.write(b'ir')
                    write_bool(file, channel.inherit)
                if channel.range is not None:
                    write_int(file, 2, 1)
                    write_int(file, len(channel.range), 3)
                    file.write(b'rg')
                    file.write(bytes(channel.range))

                with LengthWriter(file, 0, 4):
                    write_int(file, len(channel.effectors), 4)
                    for effector in channel.effectors:
                        write_int(file, len(effector.effector_name.encode()), 2)
                        file.write(effector.effector_name.encode())
                        write_bool(file, effector.enabled)
                        write_float(file, effector.mix_level, 4)
                        bytes_data = json.dumps(effector.effect_values.model_dump(), separators=(',', ': ')).encode()
                        write_int(file, len(bytes_data), 4)
                        file.write(bytes_data)

        num = (self.ignore_issues is not None) + (self.instrument_cfg is not None) + (self.dgprogram_cfg is not None) + (self.dgstyle_cfg is not None)
        write_int(file, num, 4)
        if self.ignore_issues is not None:
            write_int(file, 13, 1)
            write_int(file, len(self.ignore_issues.encode()), 3)
            file.write(b'ignore_issues')
            file.write(self.ignore_issues.encode())
        if self.instrument_cfg is not None:
            write_int(file, 14, 1)
            bytes_data: bytes = json.dumps(self.instrument_cfg, ensure_ascii=False, separators=(',', ': ')).encode()
            write_int(file, len(bytes_data) + 1, 3)
            file.write(b'instrument_cfg')
            file.write(bytes_data)
            file.write(bytes(1))
        if self.dgprogram_cfg is not None:
            write_int(file, 13, 1)
            bytes_data: bytes = json.dumps(self.dgprogram_cfg, ensure_ascii=False, separators=(',', ': ')).encode()
            write_int(file, len(bytes_data) + 1, 3)
            file.write(b'dgprogram_cfg')
            file.write(bytes_data)
            file.write(bytes(1))
        if self.dgstyle_cfg is not None:
            write_int(file, 11, 1)
            bytes_data: bytes = json.dumps(self.dgstyle_cfg, ensure_ascii=False, separators=(',', ': ')).encode()
            write_int(file, len(bytes_data) + 1, 3)
            file.write(b'dgstyle_cfg')
            file.write(bytes_data)
            file.write(bytes(1))

    def to_bytes(self) -> bytes:
        with BytesIO() as bytes_io:
            self._save_to_file(bytes_io)
            return bytes_io.getvalue()

    def import_midi(self,
                    midi_file: MidiFile,
                    override: bool = True,
                    transposition: int = 0,
                    offset_global_transpose_config: bool = True,  # 抵消全局移调配置
                    merge_tracks: bool = False,  # TODO
                    ) -> Self:
        """
        This is not a classmethod.
        Use `FmpFile.new(...)` to firstly create an fmp file and then call this method.
        """
        # load title from midi_file.filename
        if override and midi_file.filename is not None:
            try:
                file_path = Path(midi_file.filename)
                self.title = file_path.stem
                self.file_path = file_path
            except TypeError:
                self.title = str(midi_file.filename)

        new_tracks: list[FmpTrack] = []
        new_time_marks: list[FmpTimeMark] = []
        for midi_track in midi_file.tracks:
            fmp_track = FmpTrack()
            unclosed_notes: defaultdict[int, list[FmpNote]] = defaultdict(list)

            midi_tick: int = 0
            for message in midi_track:
                midi_tick += message.time
                time: float = midi_tick / midi_file.ticks_per_beat
                try:
                    match message.type:
                        case 'note_on' | 'note_off':
                            if offset_global_transpose_config:
                                pitch: int = message.note + transposition - int(self.get_instrument_cfg()['transpose'])
                            else:
                                pitch = message.note + transposition

                            if message.type == 'note_on' and message.velocity > 0:
                                if pitch not in range(128):
                                    logger.warning(f'Note {pitch} out of range(128), SKIPPING!')
                                    continue
                                unclosed_notes[pitch].append(FmpNote(pitch,
                                                                     round(time * self.ticks_per_beat),
                                                                     0,  # or any other value
                                                                     message.velocity * 2))

                            else:  # note_off or zero velocity note_on
                                if pitch not in range(128):
                                    continue
                                try:
                                    note: FmpNote = unclosed_notes[pitch].pop()
                                except IndexError:
                                    logger.warning(f'No note_on message found to match with {message!r}.')
                                    continue
                                fmp_track.notes.append(note.copy(
                                    duration=round(time * self.ticks_per_beat - note.tick)))

                        case 'track_name':
                            if not fmp_track.name:
                                fmp_track.name = message.name

                        case 'time_signature':
                            # The first message (if midi_tick == 0) will change the fmp_file.time_signature
                            # attribute, and others will be added as FmpBpmTimeSignatureMark.
                            if midi_tick == 0 and 'set_time_signature' not in locals():  # on first change
                                set_time_signature = True  # or any other value. This variable is just a marker.
                                self.time_signature = TimeSignature(message.numerator, message.denominator)
                            else:
                                new_time_marks.append(FmpBpmTimeSignatureMark(
                                    round(time * self.ticks_per_beat),
                                    change_time_signature=True,
                                    time_signature=TimeSignature(message.numerator, message.denominator),
                                ))

                        case 'set_tempo':
                            # The first message (if midi_tick == 0) will change the fmp_file.tempo attribute,
                            # and others will be added as FmpBpmTimeSignatureMark.
                            if midi_tick == 0 and 'set_tempo' not in locals():  # on first change
                                set_tempo = True  # or any other value. This variable is just a marker.
                                self.tempo = message.tempo
                            else:
                                new_time_marks.append(FmpBpmTimeSignatureMark(
                                    round(time * self.ticks_per_beat),
                                    change_tempo=True,
                                    tempo=message.tempo,
                                ))

                        case _:
                            logger.debug(f'Unrecognized message {message!r}, IGNORING!')

                except Exception as e:
                    logger.exception(e)

            # close all notes
            for key, stack in unclosed_notes.items():
                for note in reversed(stack):
                    logger.warning(f'No note_off message found to match with {note!r}.')
                    fmp_track.notes.append(note.copy(
                        duration=round(midi_tick / midi_file.ticks_per_beat * self.ticks_per_beat - note.tick)))

            if fmp_track.notes:
                fmp_track.notes.sort(key=lambda note: note.tick)
                fmp_track.index = len(new_tracks)
                new_tracks.append(fmp_track)

        if override:
            self.tracks = new_tracks
            self.time_marks = new_time_marks
        else:
            self.tracks.extend(new_tracks)
            self.time_marks.extend(new_time_marks)
        self.time_marks.sort(key=lambda time_mark: time_mark.tick)

        if merge_tracks:
            raise NotImplementedError

        return self

    def export_midi(self,
                    transposition: int = 0,
                    apply_instrument_transposition: bool = True,
                    ticks_per_beat: int = MIDI_DEFAULT_TICKS_PER_BEAT,
                    ) -> MidiFile:
        midi_file = MidiFile(charset='gbk')
        midi_file.ticks_per_beat = ticks_per_beat

        time_signature_track = MidiTrack()
        tempo_track = MidiTrack()
        time_signature_track.append(MetaMessage(
            type='time_signature',
            numerator=self.time_signature.numerator,
            denominator=self.time_signature.denominator,
            time=0,
        ))
        tempo_track.append(MetaMessage(
            type='set_tempo',
            tempo=self.tempo,
            time=0,
        ))
        for time_mark in self.time_marks:
            if isinstance(time_mark, FmpBpmTimeSignatureMark):
                if time_mark.change_time_signature:
                    time_signature_track.append(MetaMessage(
                        type='time_signature',
                        numerator=time_mark.time_signature.numerator,
                        denominator=time_mark.time_signature.denominator,
                        time=round(time_mark.tick / self.ticks_per_beat * ticks_per_beat),
                    ))
                if time_mark.change_tempo:
                    tempo_track.append(MetaMessage(
                        type='set_tempo',
                        tempo=time_mark.tempo,
                        time=round(time_mark.tick / self.ticks_per_beat * ticks_per_beat),
                    ))
            else:
                logger.debug(f'Skipped {time_mark!r} when exporting to midi.')

        midi_file.tracks.append(MidiTrack(mido.midifiles.tracks._to_reltime(time_signature_track)))
        midi_file.tracks.append(MidiTrack(mido.midifiles.tracks._to_reltime(tempo_track)))

        for track in self.tracks:
            midi_track = MidiTrack()
            midi_track.name = track.name
            # midi_track.append(MetaMessage(type='track_name', name=track.name, time=0))
            midi_track.append(Message(type='program_change', program=10, time=0))

            for note in sorted(track.notes, key=lambda note: note.tick):
                if apply_instrument_transposition:
                    pitch: int = note.pitch + transposition + int(self.get_instrument_cfg()['transpose'])
                else:
                    pitch = note.pitch + transposition
                if pitch not in range(128):
                    logger.warning(f'Note {note.pitch} out of range(128), SKIPPING!')
                    continue
                midi_track.append(Message(
                    type='note_on',
                    note=pitch,
                    velocity=round(note.velocity / 255 * 127),
                    time=round(note.tick / self.ticks_per_beat * ticks_per_beat),
                ))
                midi_track.append(Message(
                    type='note_off',
                    note=pitch,
                    time=round((note.tick + note.duration) / self.ticks_per_beat * ticks_per_beat),
                ))
            midi_track.sort(key=lambda msg: msg.time)
            midi_file.tracks.append(MidiTrack(mido.midifiles.tracks._to_reltime(midi_track)))

        for midi_track in midi_file.tracks:
            midi_track.append(MetaMessage(type='end_of_track', time=0))

        return midi_file


def read_int(file: BinaryIO,
             /,
             byte: int = 1,
             byteorder: Literal['big', 'little'] = 'little',
             signed: bool = False) -> int:
    return int.from_bytes(file.read(byte), byteorder, signed=signed)


def read_bool(file: BinaryIO, /) -> bool:
    b: bytes = file.read(1)
    i: int = int.from_bytes(b)
    if i not in (0, 1):
        raise ValueError(f'Read value {repr(b)} is not a bool.')
    return bool(i)


def read_float(file: BinaryIO, /, byte: Literal[2, 4, 8] = 4, byteorder: Literal['big', 'little'] = 'little') -> float:
    byteorder_flag = {'big': '>', 'little': '<'}[byteorder]
    format_character = {2: 'e', 4: 'f', 8: 'd'}[byte]
    return struct.unpack(f'{byteorder_flag}{format_character}', file.read(byte))[0]


def write_int(file: BinaryIO,
              /,
              value: int,
              byte: int = 1,
              byteorder: Literal['big', 'little'] = 'little') -> None:
    signed: bool = (value < 0)
    file.write(value.to_bytes(byte, byteorder, signed=signed))


def write_bool(file: BinaryIO,
               /,
               value: bool) -> None:
    file.write(value.to_bytes())


def write_float(file: BinaryIO,
                /,
                value: float,
                byte: Literal[2, 4, 8] = 4,
                byteorder: Literal['big', 'little'] = 'little') -> None:
    byteorder_flag = {'big': '>', 'little': '<'}[byteorder]
    format_character = {2: 'e', 4: 'f', 8: 'd'}[byte]
    file.write(struct.pack(f'{byteorder_flag}{format_character}', value))


class LengthWriter:
    def __init__(self, file: BinaryIO, offset: int = 0, byte: int = 4) -> None:
        self.file: BinaryIO = file
        self.offset: int = offset
        self.byte: int = byte

    def __enter__(self) -> None:
        self.pointer: int = self.file.tell()
        self.file.seek(self.byte, 1)

    def __exit__(self, *args) -> None:
        current_pointer: int = self.file.tell()
        self.file.seek(self.pointer)
        write_int(self.file, current_pointer - self.pointer - self.offset, self.byte)
        self.file.seek(current_pointer)
