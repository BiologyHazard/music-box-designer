import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self, TextIO

import mido.midifiles.tracks
from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo

from .consts import DEFAULT_DURATION, MIDI_DEFAULT_TICKS_PER_BEAT
from .log import logger

EMID_TICKS_PER_BEAT = 8
EMID_PITCHES: list[int] = [93, 91, 89, 88, 87, 86, 85, 84, 83, 82,
                           81, 80, 79, 78, 77, 76, 75, 74, 73, 72,
                           71, 70, 69, 67, 65, 64, 62, 60, 55, 53]

# def pitch_to_mbindex(pitch: int) -> int:
#     try:
#         return 29 - MUSIC_BOX_30_NOTES_PITCH.index(pitch)
#     except ValueError:
#         raise ValueError(f'Pitch {pitch} not in range of 30 notes music box.')


# def mbindex_to_pitch(mbindex: int) -> int:
#     if mbindex in range(30):
#         return MUSIC_BOX_30_NOTES_PITCH[29 - mbindex]
#     else:
#         raise ValueError('mbindex must be int in range(30)')


@dataclass(frozen=True)
class EmidNote:
    emid_pitch: int
    '''音高'''
    tick: int
    '''音符起始位置的刻数'''


@dataclass
class EmidTrack:
    name: str = ''
    notes: list[EmidNote] = field(default_factory=lambda: [])


@dataclass
class EmidFile:
    tracks: list[EmidTrack] = field(default_factory=lambda: [])
    length: int = 1

    file_path: Path | None = None

    @classmethod
    def from_str(cls, data: str) -> Self:
        data = data.strip()
        notes_str, tmp_str = data.strip().split('&')
        length_str, track_name_str = tmp_str.split('*')
        length = int(length_str)
        note_str_list: list[str] = notes_str.split('#')
        track_name_list: list[str] = track_name_str.split(',')
        track_name_dict: dict[str, int] = {k: v for v, k in enumerate(track_name_list)}
        # 添加空轨道
        tracks: list[EmidTrack] = []
        for track_name in track_name_list:
            new_track = EmidTrack(track_name)
            tracks.append(new_track)
        # 添加音符
        for note_str in note_str_list:
            emid_pitch_str, tick_str, track_name = note_str.split(',')
            emid_pitch = int(emid_pitch_str)
            tick = int(tick_str)
            track_index: int = track_name_dict[track_name]
            tracks[track_index].notes.append(EmidNote(emid_pitch, tick))
        return cls(tracks, length)

    @classmethod
    def load_from_file(cls, file: str | Path | TextIO) -> Self:
        if isinstance(file, (str, Path)):
            with open(file, 'r', encoding='utf-8') as fp:
                self: Self = cls.from_str(fp.read())
            self.file_path = Path(file)
        else:
            self = cls.from_str(file.read())
            self.file_path = None
        return self

    def get_length(self) -> int:
        return math.ceil(max(note.tick for track in self.tracks for note in track.notes) / EMID_TICKS_PER_BEAT * 2) + 1

    def update_length(self) -> int:
        '''更新长度并返回更新后的长度'''
        self.length = self.get_length()
        return self.length

    def to_str(self) -> str:
        note_str: str = '#'.join(
            f'{note.emid_pitch},{note.tick},{track.name}'
            for track in self.tracks
            for note in track.notes
        )
        track_names_str: str = ','.join(track.name for track in self.tracks)
        return f'{note_str}&{self.length}*{track_names_str}'

    def save_to_file(self, file: str | Path | TextIO, update_length=True) -> None:
        if update_length:
            self.update_length()
        s: str = self.to_str()
        if isinstance(file, (str, Path)):
            file_path = Path(file)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(s, 'utf-8')
        else:
            file.write(s)

    @classmethod
    def from_midi(cls,
                  midi_file: MidiFile,
                  *,
                  transposition: int = 0,
                  ) -> Self:
        emid_file: Self = cls()

        for midi_track in midi_file.tracks:
            emid_track = EmidTrack()
            midi_tick: int = 0
            for message in midi_track:
                midi_tick += message.time
                if message.type == 'note_on':
                    if message.velocity == 0:
                        continue
                    if message.note + transposition not in EMID_PITCHES:
                        logger.warning('note out of range!')
                        continue
                    tick: int = round(midi_tick / midi_file.ticks_per_beat * EMID_TICKS_PER_BEAT)
                    emid_track.notes.append(EmidNote(
                        EMID_PITCHES.index(message.note + transposition), tick))
            if emid_track.notes:
                emid_track.name = str(len(emid_file.tracks))
                emid_file.tracks.append(emid_track)

        emid_file.update_length()
        return emid_file

    def export_midi(self,
                    *,
                    bpm: float | None = None,
                    transposition: int = 0,
                    ticks_per_beat: int = MIDI_DEFAULT_TICKS_PER_BEAT,
                    ) -> MidiFile:
        midi_file = MidiFile(charset='gbk')
        midi_file.ticks_per_beat = ticks_per_beat

        if bpm is not None:
            tempo_track = MidiTrack()
            tempo_track.append(MetaMessage(type='set_tempo', tempo=bpm2tempo(bpm), time=0))
            midi_file.tracks.append(tempo_track)

        for track in self.tracks:
            midi_track = MidiTrack()
            # midi_track.append(MetaMessage(type='track_name', name=f'Track {track.name}', time=0))
            midi_track.name = f'Track {track.name}'
            midi_track.append(Message(type='program_change', program=10, time=0))
            for note in track.notes:
                if EMID_PITCHES[note.emid_pitch] + transposition not in range(128):
                    continue

                midi_track.append(Message(
                    type='note_on',
                    note=EMID_PITCHES[note.emid_pitch] + transposition,
                    time=round(note.tick / EMID_TICKS_PER_BEAT * ticks_per_beat)
                ))
                midi_track.append(Message(
                    type='note_off',
                    note=EMID_PITCHES[note.emid_pitch] + transposition,
                    time=round((note.tick / EMID_TICKS_PER_BEAT + DEFAULT_DURATION) * ticks_per_beat)
                ))
            midi_track.sort(key=lambda message: message.time)
            midi_file.tracks.append(MidiTrack(mido.midifiles.tracks._to_reltime(midi_track)))

        for midi_track in midi_file.tracks:
            midi_track.append(MetaMessage(type='end_of_track', time=0))

        return midi_file
