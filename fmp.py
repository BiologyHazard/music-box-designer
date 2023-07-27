from dataclasses import dataclass, field
from pathlib import Path
from typing import Self, BinaryIO, Any
import math
import json
from mido import MidiFile, MidiTrack, Message, MetaMessage, bpm2tempo, tempo2bpm
from consts import T_pitch, DEFAULT_VELOCITY, DEFAULT_DURATION, DEFAULT_TICKS_PER_BEAT
from utils import read_int, read_bool

FMP_TRANSPOSITION = -7


@dataclass(frozen=True)
class FmpNote:
    pitch: T_pitch
    '''midi音高'''
    time: float
    '''音符起始位置的节拍数'''
    duration: float
    '''音符持续时间的节拍数'''
    velocity: float
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
        self.notes = [note.__class__(note.pitch + transposition, note.time, note.duration, note.velocity)
                      for note in self.notes
                      if note.pitch + transposition in range(128)]


@dataclass
class FmpTimeMark:
    time: float = 0


@dataclass
class FmpBpmTimeSignatureMark(FmpTimeMark):
    change_tempo: bool = True
    bpm: float = 120
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
    data: bytes = b''


@dataclass
class FmpFile:
    version: tuple[int, int, int] = (3, 0, 0)
    compatible_version: tuple[int, int, int] = (0, 0, 0)
    bpm: float = 120
    time_signature: tuple[int, int] = (4, 4)
    ticks_per_beat: int = 96
    instrument: str = 'Instrument_Preset_PaperStripMusicBox_30Note'
    show_info_on_open: bool = False
    title: str = ''
    subtitle: str = ''
    comment: str = ''
    tracks: list[FmpTrack] = field(default_factory=lambda: [])
    time_marks: list[FmpTimeMark] = field(default_factory=lambda: [])
    channels: list[FmpChannel] = field(default_factory=lambda: [])
    dgprogram_cfg: dict[str, Any] = field(default_factory=lambda: {})
    dgstyle_cfg: dict[str, Any] = field(default_factory=lambda: {})

    @classmethod
    def _load_from_file(cls, file: BinaryIO) -> Self:
        fmp_file: Self = cls()

        # 头部数据
        assert file.read(3) == b'FMP'
        assert file.read(2) == bytes(2)

        fmp_file.version = (read_int(file, 2), read_int(file, 2), read_int(file, 2))
        fmp_file.compatible_version = (read_int(file, 2), read_int(file, 2), read_int(file, 2))
        file.read(2)

        assert file.read(6) == bytes(6)

        tempo: int = read_int(file, 4)
        fmp_file.bpm = tempo2bpm(tempo)

        numerator: int = read_int(file, 2)
        denominator: int = read_int(file, 2)
        fmp_file.time_signature = (numerator, denominator)

        fmp_file.ticks_per_beat = read_int(file, 2)

        assert file.read(4) == bytes(4)

        instrument_length: int = read_int(file, 2)
        fmp_file.instrument = file.read(instrument_length).decode()

        assert file.read(4) == b'\x03\x00\x00\x00'
        num: int = read_int(file, 1) - 1
        assert file.read(7) == b'\x00\x00\x00\x03\x01\x00\x00'

        # 工程信息
        assert file.read(3) == b'sio'
        fmp_file.show_info_on_open = read_bool(file)
        for i in range(num):
            type_length: int = read_int(file, 1)
            info_length: int = read_int(file, 2) - 1
            assert file.read(1) == b'\x00'
            info_type: str = file.read(type_length).decode()
            if info_type == 'ti':
                fmp_file.title = file.read(info_length).decode()
            elif info_type == 'sti':
                fmp_file.subtitle = file.read(info_length).decode()
            elif info_type == 'cmt':
                fmp_file.comment = file.read(info_length).decode()
            else:
                raise ValueError
            assert file.read(1) == b'\x00'

        # 轨道
        assert file.read(3) == b'TRK'
        file_magic_num: int = read_int(file, 4)
        track_count: int = read_int(file, 4)
        for _ in range(track_count):
            track = FmpTrack()

            assert read_int(file, 1) == 1
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
                time: float = tick / fmp_file.ticks_per_beat
                pitch: int = read_int(file, 1) + FMP_TRANSPOSITION
                duration_tick: int = read_int(file, 4)
                duration: float = duration_tick / fmp_file.ticks_per_beat
                velocity: float = read_int(file, 1) / 255
                note = FmpNote(pitch, time, duration, velocity)
                track.notes.append(note)

            fmp_file.tracks.append(track)

        # 时间标记
        assert file.read(3) == b'TMK'
        file.read(4)
        time_mark_count: int = read_int(file, 4)
        for _ in range(time_mark_count):
            mark_type: int = read_int(file, 1)
            if mark_type == 1:  # bpm / 节拍标记
                time_mark = FmpBpmTimeSignatureMark()
                assert file.read(2) == '\x0E\x00'
                tick = read_int(file, 4)
                time_mark.time = tick / fmp_file.ticks_per_beat
                time_mark.change_tempo = read_bool(file)
                tempo = read_int(file, 4)
                time_mark.bpm = tempo2bpm(tempo)
                time_mark.change_time_signature = read_bool(file)
                numerator = read_int(file, 2)
                denominator = read_int(file, 2)
                time_mark.time_signature = (numerator, denominator)
            elif mark_type == 2:  # 注释
                time_mark = FmpCommentMark()
                comment_length_add_6: int = read_int(file, 2)
                tick = read_int(file, 4)
                time_mark.time = tick / fmp_file.ticks_per_beat
                comment_length: int = read_int(file, 2)
                assert comment_length_add_6 == comment_length + 6
                time_mark.comment = file.read(comment_length).decode()
            elif mark_type == 3:  # 结束标记
                time_mark = FmpEndMark()
                tick = read_int(file, 4)
                time_mark.time = tick / fmp_file.ticks_per_beat
            else:
                raise ValueError
            fmp_file.time_marks.append(time_mark)

        # 通道
        assert file.read(3) == b'CNL'
        channel_length: int = read_int(file, 4) + 1
        channel = FmpChannel()
        channel.data = file.read(channel_length)
        fmp_file.channels.append(channel)

        dgprogram_cfg_length: int = read_int(file, 3) - 1
        assert file.read(13) == b'dgprogram_cfg'
        fmp_file.dgprogram_cfg = json.loads(file.read(dgprogram_cfg_length).decode().replace('\n', '\\n'))
        assert file.read(1) == b'\x00'
        assert file.read(1) == b'\x0B'
        dgstyle_cfg_length: int = read_int(file, 3) - 1
        assert file.read(11) == b'dgstyle_cfg'
        fmp_file.dgstyle_cfg = json.loads(file.read(dgstyle_cfg_length).decode().replace('\n', '\\n'))
        assert file.read(1) == b'\x00'
        assert file.read() == b''

        return fmp_file

    @classmethod
    def load_from_file(cls, file: str | bytes | Path | BinaryIO) -> Self:
        if isinstance(file, (str, bytes, Path)):
            with open(file, 'rb') as fp:
                return cls._load_from_file(fp)
        else:
            return cls._load_from_file(file)

    def transpose(self, transposition: int) -> None:
        for track in self.tracks:
            track.transpose(transposition)

    def to_bytes(self) -> bytes:
        ...

    def save_to_file(self, file: str | bytes | Path | BinaryIO) -> None:
        s: bytes = self.to_bytes()
        if isinstance(file, (str, bytes, Path)):
            with open(file, 'wb') as fp:
                fp.write(s)
        else:
            file.write(s)

    @classmethod
    def from_midi(cls,
                  midi_file: MidiFile,
                  *,
                  transposition: int = 0,
                  ) -> Self:
        tracks: list[FmpTrack] = []
        for midi_track in midi_file:
            fmp_track = FmpTrack()
            midi_tick: int = 0
            for message in midi_track:
                midi_tick += message.time
                if message.type == 'note_on':
                    if message.velocity > 0:
                        time: float = midi_tick / midi_file.ticks_per_beat
                        fmp_track.notes.append(FmpNote(message.note, time, DEFAULT_DURATION, DEFAULT_VELOCITY))
            if fmp_track:
                fmp_track.name = str(len(tracks))
            tracks.append(fmp_track)

        fmp_file: Self = cls()
        fmp_file.tracks = tracks
        fmp_file.transpose(transposition)
        return fmp_file

    def export_midi(self,
                    *,
                    bpm: float = 120,
                    transposition: int = 0,
                    ticks_per_beat: int = DEFAULT_TICKS_PER_BEAT,
                    ) -> MidiFile:
        midi_file = MidiFile()
        midi_file.ticks_per_beat = ticks_per_beat

        # 空轨道用于保存tempo信息
        empty_track = MidiTrack()
        empty_track.append(MetaMessage(type='set_tempo', tempo=bpm2tempo(bpm), time=0))
        midi_file.tracks.append(empty_track)

        for track in self.tracks:
            events: list[Message] = []
            for note in track.notes:
                if note.pitch + transposition in range(128):
                    events.append(Message(
                        type='note_on',
                        note=note.pitch + transposition,
                        velocity=note.velocity * 127,
                        time=round(note.time * ticks_per_beat),
                    ))
                    events.append(Message(
                        type='note_off',
                        note=note.pitch + transposition,
                        time=round((note.time + note.duration) * ticks_per_beat),
                    ))
            events.sort(key=lambda msg: msg.time)  # type: ignore

            midi_track = MidiTrack()
            midi_track.append(MetaMessage(type='track_name', name=f'Track {track.name}', time=0))
            midi_track.append(Message(type='program_change', program=10, time=0))

            midi_tick: int = 0
            for message in events:
                midi_track.append(message.copy(time=message.time - midi_tick))  # type: ignore
                midi_tick = message.time  # type: ignore
            midi_track.append(MetaMessage(type='end_of_track', time=0))
            midi_file.tracks.append(midi_track)

        return midi_file


print(FmpFile.load_from_file(r"C:\Users\Administrator\Documents\Tencent Files\3482991796\FileRecv\Sincerely2.fmp"))
