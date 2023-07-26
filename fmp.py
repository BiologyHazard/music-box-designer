from dataclasses import dataclass
from pathlib import Path
from typing import Self, BinaryIO
import math
from mido import MidiFile, MidiTrack, Message, MetaMessage, bpm2tempo
from consts import T_pitch, DEFAULT_VELOCITY, DEFAULT_DURATION, DEFAULT_TICKS_PER_BEAT


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
    notes: list[FmpNote] = []

    def transpose(self, transposition: int) -> None:
        self.notes = [note.__class__(note.pitch + transposition, note.time, note.duration, note.velocity)
                      for note in self.notes
                      if note.pitch + transposition in range(128)]


@dataclass
class EmidFile:
    tracks: list[FmpTrack] = []
    bpm: float = 120
    time_signature: tuple[int, int] = (4, 4)

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        ...

    @classmethod
    def load_from_file(cls, file: str | bytes | Path | BinaryIO) -> Self:
        if isinstance(file, (str, bytes, Path)):
            with open(file, 'rb') as fp:
                file = fp
        return cls.from_bytes(file.read())

    def transpose(self, transposition: int) -> None:
        for track in self.tracks:
            track.transpose(transposition)

    def to_bytes(self) -> bytes:
        ...

    def save_to_file(self, file: str | bytes | Path | BinaryIO) -> None:
        s: bytes = self.to_bytes()
        if isinstance(file, (str, bytes, Path)):
            with open(file, 'wb') as fp:
                file = fp
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
