import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self, TextIO

from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo

from consts import (DEFAULT_DURATION, DEFAULT_TICKS_PER_BEAT, TIME_PER_BEAT,
                    T_pitch)
from utils import mbindex_to_pitch, pitch_to_mbindex


@dataclass(frozen=True)
class EmidNote:
    pitch: T_pitch
    '''midi音高'''
    time: float
    '''节拍数'''


@dataclass
class EmidTrack:
    name: str = ''
    notes: list[EmidNote] = field(default_factory=lambda: [])

    def transpose(self, transposition: int) -> None:
        self.notes = [note.__class__(note.pitch + transposition, note.time)
                      for note in self.notes
                      if note.pitch + transposition in range(128)]


@dataclass
class EmidFile:
    tracks: list[EmidTrack] = field(default_factory=lambda: [])
    length: int = 1

    @classmethod
    def from_str(cls, data: str) -> Self:
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
            mbindex_str, time_str, trackname = note_str.split(',')
            try:
                pitch: int = mbindex_to_pitch(int(mbindex_str))
            except:
                continue
            time: float = float(time_str) / TIME_PER_BEAT
            track_index: int = track_name_dict[trackname]
            tracks[track_index].notes.append(EmidNote(pitch, time))
        return cls(tracks, length)

    @classmethod
    def load_from_file(cls, file: str | bytes | Path | TextIO) -> Self:
        if isinstance(file, (str, bytes, Path)):
            with open(file, 'r', encoding='utf-8') as fp:
                file = fp
        return cls.from_str(file.read())

    def update_length(self) -> int:
        '''更新长度并返回更新后的长度'''
        self.length = math.ceil(max(note.time for track in self.tracks for note in track.notes) / TIME_PER_BEAT * 2) + 1
        return self.length

    def transpose(self, transposition: int) -> None:
        for track in self.tracks:
            track.transpose(transposition)

    def to_str(self) -> str:
        note_str: str = '#'.join(
            f'{pitch_to_mbindex(note.pitch)},{round(note.time * TIME_PER_BEAT)},{track.name}'
            for track in self.tracks
            for note in track.notes
        )
        track_names_str: str = ','.join(track.name for track in self.tracks)
        return ''.join((note_str, '&', str(self.length), '*', track_names_str))

    def save_to_file(self, file: str | bytes | Path | TextIO, update_length=True) -> None:
        if update_length:
            self.update_length()
        s: str = self.to_str()
        if isinstance(file, (str, bytes, Path)):
            with open(file, 'w', encoding='utf-8') as fp:
                file = fp
        file.write(s)

    @classmethod
    def from_midi(cls,
                  midi_file: MidiFile,
                  *,
                  transposition: int = 0,
                  ) -> Self:
        tracks: list[EmidTrack] = []
        for midi_track in midi_file.tracks:
            emid_track = EmidTrack()
            midi_tick: int = 0
            for message in midi_track:
                midi_tick += message.time
                if message.type == 'note_on':
                    if message.velocity > 0:
                        time: float = midi_tick / midi_file.ticks_per_beat
                        emid_track.notes.append(EmidNote(message.note, time))
            if emid_track:
                emid_track.name = str(len(tracks))
                tracks.append(emid_track)

        emid_file: Self = cls()
        emid_file.tracks = tracks
        emid_file.transpose(transposition)
        emid_file.update_length()
        return emid_file

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
                        time=round(note.time * ticks_per_beat)
                    ))
                    events.append(Message(
                        type='note_off',
                        note=note.pitch + transposition,
                        time=round((note.time + DEFAULT_DURATION) * ticks_per_beat)
                    ))
            events.sort(key=lambda message: (message.time, ['note_off', 'note_on'].index(message.type)))  # type: ignore

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
