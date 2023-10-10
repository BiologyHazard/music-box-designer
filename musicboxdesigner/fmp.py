import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO, Literal, Self

from mido import Message, MetaMessage, MidiFile, MidiTrack

from .consts import DEFAULT_DURATION, MIDI_DEFAULT_TICKS_PER_BEAT

FMP_DEFAULT_TICKS_PER_BEAT = 96


@dataclass(frozen=True)
class FmpNote:
    pitch: int
    '''midi音高'''
    tick: int
    '''音符起始位置的刻数'''
    duration: int
    '''音符持续时间的刻数'''
    velocity: int
    '''音符的力度'''


@dataclass
class FmpTrack:
    name: str = ''
    channel: int = 0
    index: int = 0
    color: int = 0
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
    change_tempo: bool = True
    tempo: int = 500000
    change_time_signature: bool = True
    time_signature: tuple[int, int] = (4, 4)


@dataclass
class FmpCommentMark(FmpTimeMark):
    comment: str = ''


@dataclass
class FmpEndMark(FmpTimeMark):
    pass


@dataclass
class FmpChannel:
    index: int = 0
    volume: int = 1000
    pan: int = 1000
    solo: bool = False
    muted: bool = False
    soundfont_name: str = ''
    soundfont_index: int = 0
    reverb_mix: int = 0
    reverb_room: int = 750
    reverb_damping: int = 500
    reverb_width: int = 1000
    participate_generate: bool = True
    transposition: int = 0
    note_trigger_mode: int = 0
    inherit: bool = True
    range: list[int] = field(default_factory=list)


@dataclass
class FmpFile:
    version: tuple[int, int, int] = (3, 0, 0)
    compatible_version: tuple[int, int, int] = (0, 0, 0)
    tempo: int = 500000
    time_signature: tuple[int, int] = (4, 4)
    ticks_per_beat: int = FMP_DEFAULT_TICKS_PER_BEAT
    instrument: str = 'Instrument_Preset_PaperStripMusicBox_30Note'
    show_info_on_open: bool = False
    title: str = ''
    subtitle: str = ''
    comment: str = ''
    tracks: list[FmpTrack] = field(default_factory=list)
    time_marks: list[FmpTimeMark] = field(default_factory=list)
    channels: list[FmpChannel] = field(default_factory=list)
    instrument_cfg: dict[str, Any] = field(default_factory=dict)
    dgprogram_cfg: dict[str, Any] = field(default_factory=dict)
    dgstyle_cfg: dict[str, Any] = field(default_factory=dict)

    file_path: Path | None = None

    @classmethod
    def load_from_file(cls, file: str | bytes | Path | BinaryIO) -> Self:
        try:
            file_path = Path(file)  # type: ignore
        except Exception:
            file_path = None
        if file_path is not None:
            with open(file_path, 'rb') as fp:
                self: Self = cls._load_from_file(fp)
        else:
            self = cls._load_from_file(file)  # type: ignore
        self.file_path = file_path
        return self

    @classmethod
    def _load_from_file(cls, file: BinaryIO) -> Self:
        fmp_file: Self = cls()

        # 头部数据
        assert file.read(3) == b'FMP'
        assert file.read(2) == bytes(2)

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
        fmp_file.time_signature = (numerator, denominator)

        fmp_file.ticks_per_beat = read_int(file, 2)

        assert file.read(4) == bytes(4)

        instrument_length: int = read_int(file, 2)
        fmp_file.instrument = file.read(instrument_length).decode()

        assert file.read(4) == b'\x03\x00\x00\x00'

        # 工程信息
        num: int = read_int(file, 4) - 1
        assert file.read(4) == b'\x03\x01\x00\x00'
        assert file.read(3) == b'sio'
        fmp_file.show_info_on_open = read_bool(file)
        for _ in range(num):
            type_length: int = read_int(file, 1)
            info_length: int = read_int(file, 3) - 1
            info_type: str = file.read(type_length).decode()
            match info_type:
                case 'ti':
                    fmp_file.title = file.read(info_length).decode()
                case 'sti':
                    fmp_file.subtitle = file.read(info_length).decode()
                case 'cmt':
                    fmp_file.comment = file.read(info_length).decode()
                case _:
                    raise ValueError
            assert file.read(1) == bytes(1)

        # 轨道
        assert file.read(3) == b'TRK'
        file_magic_num: int = read_int(file, 4)  # file_magic_num = 总音符数*12 + trackname总字节数 + 轨道数*40 + 8
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
                    time_mark.time_signature = (numerator, denominator)
                case 2:  # 注释
                    time_mark = FmpCommentMark()
                    comment_length_add_6: int = read_int(file, 2)
                    time_mark.tick = read_int(file, 4)
                    comment_length: int = read_int(file, 2)
                    assert comment_length_add_6 == comment_length + 6
                    time_mark.comment = file.read(comment_length).decode()
                case 3:  # 结束标记
                    time_mark = FmpEndMark()
                    assert file.read(3) == b'\x04\x00'
                    time_mark.tick = read_int(file, 4)
                case _:
                    raise ValueError
            fmp_file.time_marks.append(time_mark)

        # 通道
        assert file.read(3) == b'CNL'
        _: int = read_int(file, 4)
        channel_count: int = read_int(file, 4)
        for _ in range(channel_count):
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
            for _ in range(num):
                key_length: int = read_int(file, 1)
                value_length: int = read_int(file, 3)
                key: str = file.read(key_length).decode()
                match key:
                    case 'effect.reverb.mix':
                        assert value_length == 2
                        channel.reverb_mix = read_int(file, value_length)
                    case 'effect.reverb.room':
                        assert value_length == 2
                        channel.reverb_room = read_int(file, value_length)
                    case 'effect.reverb.damping':
                        assert value_length == 2
                        channel.reverb_damping = read_int(file, value_length)
                    case 'effect.reverb.width':
                        assert value_length == 2
                        channel.reverb_width = read_int(file, value_length)
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
            assert file.read(4) == b'\x04\x00\x00\x00'

            fmp_file.channels.append(channel)

        num: int = read_int(file, 4)
        for _ in range(num):
            key_length: int = read_int(file, 1)
            value_length: int = read_int(file, 3) - 1
            key: str = file.read(key_length).decode()
            match key:
                case 'instrument_cfg':
                    fmp_file.instrument_cfg = json.loads(file.read(value_length).decode().replace('\n', '\\n'))
                case 'dgprogram_cfg':
                    fmp_file.dgprogram_cfg = json.loads(file.read(value_length).decode().replace('\n', '\\n'))
                case 'dgstyle_cfg':
                    fmp_file.dgstyle_cfg = json.loads(file.read(value_length).decode().replace('\n', '\\n'))
            assert file.read(1) == bytes(1)
        assert not file.read()

        return fmp_file

    def transpose(self, transposition: int) -> None:
        for track in self.tracks:
            track.transpose(transposition)

    def save_to_file(self, file: str | bytes | Path | BinaryIO) -> None:
        if isinstance(file, (str, bytes, Path)):
            with open(file, 'wb') as fp:
                self._save_to_file(fp)
        else:
            self._save_to_file(file)

    def _save_to_file(self, file: BinaryIO) -> None:
        file.write(b'FMP')
        file.write(bytes(2))
        for version_part in self.version:
            write_int(file, version_part, 2)
        for compatible_version_part in self.compatible_version:
            write_int(file, compatible_version_part, 2)

        write_int(file, len(self.instrument.encode()) + 28, 4)
        file.write(bytes(4))
        write_int(file, self.tempo, 4)
        write_int(file, self.time_signature[0], 2)
        write_int(file, self.time_signature[1], 2)
        write_int(file, self.ticks_per_beat, 2)
        file.write(bytes(4))
        write_int(file, len(self.instrument.encode()), 2)
        file.write(self.instrument.encode())
        file.write(b'\x03\x00\x00\x00')

        num: int = 1 + bool(self.title) + bool(self.subtitle) + bool(self.comment)
        write_int(file, num, 4)
        write_int(file, 3, 1)
        write_int(file, 1, 3)
        file.write(b'sio')
        write_bool(file, self.show_info_on_open)
        if self.title:
            write_int(file, 2, 1)
            write_int(file, len(self.title.encode()) + 1, 3)
            file.write(b'ti')
            file.write(self.title.encode())
            file.write(bytes(1))
        if self.subtitle:
            write_int(file, 3, 1)
            write_int(file, len(self.subtitle.encode()) + 1, 3)
            file.write(b'sti')
            file.write(self.subtitle.encode())
            file.write(bytes(1))
        if self.comment:
            write_int(file, 3, 1)
            write_int(file, len(self.comment.encode()) + 1, 3)
            file.write(b'cmt')
            file.write(self.comment.encode())
            file.write(bytes(1))

        file.write(b'TRK')
        write_int(file, sum(len(track.notes) * 12 + len(track.name) + 40 for track in self.tracks) + 8, 4)
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
        length: int = 8
        for time_mark in self.time_marks:
            if isinstance(time_mark, FmpBpmTimeSignatureMark):
                length += 17
            elif isinstance(time_mark, FmpCommentMark):
                length += 9 + len(time_mark.comment.encode())
            elif isinstance(time_mark, FmpEndMark):
                length += 7
            else:
                raise TypeError
        write_int(file, length, 4)
        write_int(file, len(self.time_marks), 4)
        for time_mark in self.time_marks:
            if isinstance(time_mark, FmpBpmTimeSignatureMark):
                write_int(file, 1, 1)
                write_int(file, 14, 2)
                write_int(file, time_mark.tick, 4)
                write_bool(file, time_mark.change_tempo)
                write_int(file, time_mark.tempo, 4)
                write_bool(file, time_mark.change_time_signature)
                write_int(file, time_mark.time_signature[0], 2)
                write_int(file, time_mark.time_signature[1], 2)
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
        pointer: int = file.tell()
        file.seek(4, 1)
        write_int(file, len(self.channels), 4)
        for channel in self.channels:
            write_int(file, len(channel.soundfont_name.encode()), 4)
            file.write(bytes(2))
            write_int(file, channel.index, 4)
            write_int(file, channel.volume, 2)
            write_int(file, channel.pan, 2)
            write_bool(file, channel.solo)
            write_bool(file, channel.muted)
            write_int(file, len(channel.soundfont_name.encode()), 2)
            file.write(channel.soundfont_name.encode())
            write_int(file, channel.soundfont_index, 4)
            write_int(file, 9 if channel.reverb_mix > 0 else 5, 4)
            if channel.reverb_mix > 0:
                write_int(file, 17, 1)
                write_int(file, 2, 3)
                file.write(b'effect.reverb.mix')
                write_int(file, channel.reverb_mix, 2)
                write_int(file, 18, 1)
                write_int(file, 2, 3)
                file.write(b'effect.reverb.room')
                write_int(file, channel.reverb_room, 2)
                write_int(file, 21, 1)
                write_int(file, 2, 3)
                file.write(b'effect.reverb.damping')
                write_int(file, channel.reverb_damping, 2)
                write_int(file, 19, 1)
                write_int(file, 2, 3)
                file.write(b'effect.reverb.width')
                write_int(file, channel.reverb_width, 2)
            write_int(file, 2, 1)
            write_int(file, 1, 3)
            file.write(b'pg')
            write_bool(file, channel.participate_generate)
            write_int(file, 2, 1)
            write_int(file, 4, 3)
            file.write(b'tp')
            write_int(file, channel.transposition, 4)
            write_int(file, 3, 1)
            write_int(file, 1, 3)
            file.write(b'ntm')
            write_int(file, channel.note_trigger_mode, 1)
            write_int(file, 2, 1)
            write_int(file, 1, 3)
            file.write(b'ir')
            write_bool(file, channel.inherit)
            write_int(file, 2, 1)
            write_int(file, len(channel.range), 3)
            file.write(b'rg')
            file.write(bytes(channel.range))
            file.write(b'\x04\x00\x00\x00')
        current_pointer: int = file.tell()
        file.seek(pointer)
        write_int(file, current_pointer - pointer, 4)
        file.seek(current_pointer)

        num = bool(self.instrument_cfg) + bool(self.dgprogram_cfg) + bool(self.dgstyle_cfg)
        write_int(file, num, 4)
        if self.instrument_cfg:
            write_int(file, 14, 1)
            bytes_data: bytes = json.dumps(self.instrument_cfg, ensure_ascii=False, separators=(',', ': ')).encode()
            write_int(file, len(bytes_data) + 1, 3)
            file.write(b'instrument_cfg')
            file.write(bytes_data)
            file.write(bytes(1))
        if self.dgprogram_cfg:
            write_int(file, 13, 1)
            bytes_data: bytes = json.dumps(self.dgprogram_cfg, ensure_ascii=False, separators=(',', ': ')).encode()
            write_int(file, len(bytes_data) + 1, 3)
            file.write(b'dgprogram_cfg')
            file.write(bytes_data)
            file.write(bytes(1))
        if self.dgstyle_cfg:
            write_int(file, 13, 1)
            bytes_data: bytes = json.dumps(self.dgstyle_cfg, ensure_ascii=False, separators=(',', ': ')).encode()
            write_int(file, len(bytes_data) + 1, 3)
            file.write(b'dgstyle_cfg')
            file.write(bytes_data)
            file.write(bytes(1))

    @classmethod
    def from_midi(cls,
                  midi_file: MidiFile,
                  *,
                  transposition: int = 0,
                  ) -> Self:
        # TODO: 时间标记
        tracks: list[FmpTrack] = []
        for midi_track in midi_file:
            fmp_track = FmpTrack()
            midi_tick: int = 0
            for message in midi_track:
                midi_tick += message.time
                if message.type == 'note_on':
                    if message.velocity > 0:
                        time: float = midi_tick / midi_file.ticks_per_beat
                        fmp_track.notes.append(FmpNote(message.note,
                                                       round(time * FMP_DEFAULT_TICKS_PER_BEAT),
                                                       round(DEFAULT_DURATION * FMP_DEFAULT_TICKS_PER_BEAT),
                                                       message.velocity * 2))
            if fmp_track:
                fmp_track.name = str(len(tracks))
            tracks.append(fmp_track)

        fmp_file: Self = cls()
        fmp_file.tracks = tracks
        fmp_file.transpose(transposition)
        return fmp_file

    def export_midi(self,
                    *,
                    transposition: int = 0,
                    ticks_per_beat: int = MIDI_DEFAULT_TICKS_PER_BEAT,
                    ) -> MidiFile:
        midi_file = MidiFile(charset='gbk')
        midi_file.ticks_per_beat = ticks_per_beat

        time_signature_track = MidiTrack()
        tempo_track = MidiTrack()
        for time_mark in self.time_marks:
            if isinstance(time_mark, FmpBpmTimeSignatureMark):
                if time_mark.change_tempo:
                    tempo_track.append(MetaMessage(type='set_tempo',
                                                   tempo=time_mark.tempo,
                                                   time=round(time_mark.tick / self.ticks_per_beat * ticks_per_beat)))
                if time_mark.change_time_signature:
                    time_signature_track.append(MetaMessage(type='time_signature',
                                                            numerator=time_mark.time_signature[0],
                                                            denomitator=time_mark.time_signature[1],
                                                            time=round(time_mark.tick / self.ticks_per_beat * ticks_per_beat)))
        midi_file.tracks.append(time_signature_track)
        midi_file.tracks.append(tempo_track)

        for track in self.tracks:
            midi_track = MidiTrack()
            midi_track.append(MetaMessage(type='track_name', name=track.name, time=0))
            midi_track.append(Message(type='program_change', program=10, time=0))

            for note in track.notes:
                if note.pitch + transposition in range(128):
                    midi_track.append(Message(
                        type='note_on',
                        note=note.pitch + transposition,
                        velocity=round(note.velocity * 127),
                        time=round(note.tick / self.ticks_per_beat * ticks_per_beat),
                    ))
                    midi_track.append(Message(
                        type='note_off',
                        note=note.pitch + transposition,
                        time=round((note.tick / self.ticks_per_beat + note.duration) * ticks_per_beat),
                    ))
            midi_track.sort(key=lambda msg: msg.time)
            midi_file.tracks.append(midi_track)

        for midi_track in midi_file.tracks:
            midi_tick: int = 0
            for message in midi_track:
                message.time -= midi_tick  # 整型的，不用在意精度
                midi_tick += message.time  # a bit tricky, try to understand.

        for midi_track in midi_file.tracks:
            midi_track.append(MetaMessage(type='end_of_track', time=0))

        return midi_file

    def set_velocity(self, velocity: int) -> None:
        for track in self.tracks:
            track.set_velocity(velocity)


def read_int(file: BinaryIO,
             /,
             byte: int = 1,
             byteorder: Literal['big', 'little'] = 'little',
             signed: bool = False) -> int:
    return int.from_bytes(file.read(byte), byteorder, signed=signed)


def read_bool(file: BinaryIO) -> bool:
    b: bytes = file.read(1)
    i: int = int.from_bytes(b)
    if i not in (0, 1):
        raise ValueError(f'Read value {repr(b)} is not a bool.')
    return bool(i)


def write_int(file: BinaryIO,
              value: int,
              byte: int = 1,
              byteorder: Literal['big', 'little'] = 'little') -> None:
    signed: bool = (value < 0)
    file.write(value.to_bytes(byte, byteorder, signed=signed))


def write_bool(file: BinaryIO,
               value: bool) -> None:
    file.write(value.to_bytes())
