import base64
import math
import re
import time
from collections.abc import Generator, Iterable
from dataclasses import dataclass, field
from io import BytesIO
from itertools import pairwise
from pathlib import Path
from typing import NamedTuple, Self, TextIO

import mido
from PIL import Image, ImageDraw
from mido import Message, MidiFile, MidiTrack

from .consts import MIDI_DEFAULT_TICKS_PER_BEAT, DEFAULT_DURATION
from .draft import draw_circle, mm_to_pixel, pos_mm_to_pixel
from .log import logger
from .presets import music_box_30_notes

DEFAULT_PPQ: int = 96
DEFAULT_PUNCHER_TIMES: int = 2
base64_regex: str = r'([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{4}|[A-Za-z0-9+/]{3}=|[A-Za-z0-9+/]{2}==)'


class MCodeMessage(NamedTuple):
    M: int
    Y: int
    P: int = DEFAULT_PUNCHER_TIMES

    def __str__(self) -> str:
        return f'M{self.M} Y{self.Y} P{self.P}'


class MCodeNote(NamedTuple):
    pitch_index: int
    tick: int


def calculate_distance(delta_index: int, delta_tick: int, ppq: int = DEFAULT_PPQ) -> float:
    return math.hypot(delta_index * music_box_30_notes.grid_width,
                      delta_tick / ppq * music_box_30_notes.length_mm_per_beat)
    # return math.hypot(delta_index, delta_tick)


# def calculate_distance(message1: MCodeMessage, message2: MCodeMessage, /, ppq: int = DEFAULT_PPQ) -> float:
#     return calculate_distance_by_delta(message1.M - message2.M, message1.Y - message2.Y, ppq)


# def optimize_message_order(messages: list[MCodeMessage], ppq: int = DEFAULT_PPQ) -> list[MCodeMessage]:
#     """This is an in-place function. Param `messages` will be modified."""
#
#     class NoteLine(NamedTuple):
#         Y: int
#         M_min: int
#         M_max: int
#         index_min: int
#         index_max: int
#
#     print(messages)
#
#     note_lines: list[NoteLine] = []
#     accumulate_Y: int = 0
#     i: int = 0
#     while i < len(messages):
#         accumulate_Y += messages[i].Y
#         if messages[i].M in (90, 80):
#             i += 1
#             continue
#         M_min = M_max = messages[i].M
#         index_min = i
#         while (i < len(messages) - 1
#                # and messages[i].M not in (90, 80)
#                and messages[i + 1].Y == 0):
#             M_min = min(M_min, messages[i].M)
#             M_max = max(M_max, messages[i].M)
#             i += 1
#         index_max = i
#         note_lines.append(NoteLine(accumulate_Y, M_min, M_max, index_min, index_max))
#         i += 1
#
#     dp_positive: float = 0
#     dp_negative: float = 0
#     for note_line in note_lines:
#         dp_positive = min(
#             dp_positive + calculate_distance(messages[note_line.index_min - 1], messages[note_line.index_max], ppq),
#             dp_negative,
#         )
#
#     print(note_lines)
#     raise NotImplementedError
#     return messages

# def get_optimized_notes(notes: list[MCodeNote],
#                         ppq: int = DEFAULT_PPQ) -> list[MCodeNote]:
#     """Do we have an algorithm which uses O(1) extra space?"""
#
#     @dataclass
#     class DPState:
#         distance: float = 0
#         # last_index: int = 0
#         # last_tick: int = 0
#         notes: list[MCodeNote] = field(default_factory=list)
#
#     dp_positive = DPState()
#     dp_negative = DPState()
#
#     i: int = 0
#     while i < len(notes):
#         start: int = i
#         tick: int = notes[i].tick
#         min_index = max_index = notes[i].pitch_index
#         while (i < len(notes)
#                and notes[i].tick == notes[start].tick):
#             min_index: int = min(min_index, notes[i].pitch_index)
#             max_index: int = max(max_index, notes[i].pitch_index)
#             i += 1
#         if not dp_positive.notes:
#             dp_positive.distance = 0
#             distance_positive = distance_negative = 0
#         else:
#             distance_positive: float = calculate_distance(
#                 dp_positive.notes[-1].pitch_index - min_index, dp_positive.notes[-1].tick - tick, ppq)
#             distance_negative: float = calculate_distance(
#                 dp_negative.notes[-1].pitch_index - min_index, dp_negative.notes[-1].tick - tick, ppq)
#             dp_positive.distance = max(distance_positive, distance_negative)
#         dp_positive.distance += calculate_distance(0, max_index - min_index, ppq)
#         if distance_positive < distance_negative:
#             dp_positive.notes.extend(notes[start:i])
#         else:
#             dp_positive.notes = dp_negative.notes + notes[start:i]
#
#         if not dp_negative.notes:
#             dp_negative.distance = 0
#             distance_positive = distance_negative = 0
#         else:
#             distance_positive = dp_positive.distance + calculate_distance(
#                 dp_positive.notes[-1].pitch_index - max_index, dp_positive.notes[-1].tick - tick, ppq)
#             distance_negative = dp_negative.distance + calculate_distance(
#                 dp_negative.notes[-1].pitch_index - max_index, dp_negative.notes[-1].tick - tick, ppq)
#             dp_negative.distance = max(distance_positive, distance_negative)
#         dp_negative.distance += calculate_distance(0, max_index - min_index, ppq)
#         if distance_positive < distance_negative:
#             dp_negative.notes = dp_positive.notes + list(reversed(notes[start:i]))
#         else:
#             dp_negative.notes.extend(reversed(notes[start:i]))
#         # dp_negative.notes.extend(reversed(notes[start:i]))
#
#     notes_arranged: list[MCodeNote] = (dp_positive.notes
#                                        if dp_positive.distance < dp_negative.distance
#                                        else dp_negative.notes)
#     return notes_arranged


class _NoteLine(NamedTuple):
    """For dynamic programming. A note line is a line of notes with the same tick."""
    pitch_indexes: list[int]  # Should not be empty
    tick: int


def _get_note_lines(notes: list[MCodeNote]) -> list[_NoteLine]:
    note_lines: list[_NoteLine] = []
    i: int = 0
    while i < len(notes):
        tick: int = notes[i].tick
        pitch_indexes: list[int] = []
        while (i < len(notes)
               and notes[i].tick == tick):
            pitch_indexes.append(notes[i].pitch_index)
            i += 1
        note_lines.append(_NoteLine(pitch_indexes=pitch_indexes, tick=tick))
    return note_lines


def get_arranged_notes(notes: list[MCodeNote], ppq: int = DEFAULT_PPQ) -> list[MCodeNote]:
    """Do we have an algorithm which uses O(1) extra space?"""
    note_lines: list[_NoteLine] = _get_note_lines(notes)

    distance_positive: float = 0  # Positive means from lowest to highest
    distance_negative: float = 0  # Negative means from highest to lowest
    routine_positive: list[bool] = []  # True for positive, False for negative
    routine_negative: list[bool] = []
    for i in range(len(note_lines)):
        previous_note_line = note_lines[i - 1] if i > 0 else note_lines[0]
        current_note_line = note_lines[i]
        # If we merge these lines in a for loop, the code would be more concise but less readable.
        distance_positive_positive: float = distance_positive + calculate_distance(
            previous_note_line.pitch_indexes[-1] - current_note_line.pitch_indexes[0],
            previous_note_line.tick - current_note_line.tick,
            ppq,
        )
        distance_negative_positive: float = distance_negative + calculate_distance(
            previous_note_line.pitch_indexes[0] - current_note_line.pitch_indexes[0],
            previous_note_line.tick - current_note_line.tick,
            ppq,
        )
        distance_positive_negative: float = distance_positive + calculate_distance(
            previous_note_line.pitch_indexes[-1] - current_note_line.pitch_indexes[-1],
            previous_note_line.tick - current_note_line.tick,
            ppq,
        )
        distance_negative_negative: float = distance_negative + calculate_distance(
            previous_note_line.pitch_indexes[0] - current_note_line.pitch_indexes[-1],
            previous_note_line.tick - current_note_line.tick,
            ppq,
        )

        if distance_positive_positive < distance_negative_positive:
            distance_positive = distance_positive_positive
            routine_positive.append(True)
        else:
            distance_positive = distance_negative_positive
            routine_positive.append(False)
        if distance_positive_negative < distance_negative_negative:
            distance_negative = distance_positive_negative
            routine_negative.append(True)
        else:
            distance_negative = distance_negative_negative
            routine_negative.append(False)

        current_line_distance: float = calculate_distance(
            0,
            current_note_line.pitch_indexes[-1] - current_note_line.pitch_indexes[0],
            ppq,
        )
        distance_positive += current_line_distance
        distance_negative += current_line_distance

        # print(distance_positive_positive, distance_negative_positive,
        #       distance_positive_negative, distance_negative_negative, sep='\t')
        # print(distance_positive, distance_negative, sep='\t')
        # print(routine_positive, routine_negative, sep='\t')

    if distance_positive < distance_negative:
        # distance = distance_positive
        final_routine: bool = True
    else:
        # distance = distance_negative
        final_routine = False

    routine_reversed: list[bool] = []
    current_routine: bool = final_routine
    for i in reversed(range(len(note_lines))):
        # len(routine_positive) == len(routine_negative) == len(note_lines)
        # routine_positive[0] and routine_negative[0] are meaningless.
        routine_reversed.append(current_routine)
        if current_routine is True:
            current_routine = routine_positive[i]
        else:
            current_routine = routine_negative[i]
    routine = list(reversed(routine_reversed))
    # print(routine)

    notes_arranged: list[MCodeNote] = []
    for note_line, direction in zip(note_lines, routine):
        if direction is True:
            notes_arranged.extend(
                MCodeNote(pitch_index=pitch_index, tick=note_line.tick)
                for pitch_index in note_line.pitch_indexes
            )
        else:
            notes_arranged.extend(
                MCodeNote(pitch_index=pitch_index, tick=note_line.tick)
                for pitch_index in reversed(note_line.pitch_indexes)
            )
    return notes_arranged


def notes_to_messages(notes: Iterable[MCodeNote],
                      puncher_times: int = DEFAULT_PUNCHER_TIMES) -> Generator[MCodeMessage, None, None]:
    tick: int = 0
    for note in notes:
        yield MCodeMessage(note.pitch_index, note.tick - tick, puncher_times)
        tick = note.tick


def messages_to_notes(messages: Iterable[MCodeMessage],
                      ignore_M90_M80_Y: bool = True) -> Generator[MCodeNote, None, None]:
    tick: int = 0
    for message in messages:
        if message.M not in (90, 80) or not ignore_M90_M80_Y:
            tick += message.Y
        if message.M in (90, 80):
            continue
        yield MCodeNote(pitch_index=message.M, tick=tick)


@dataclass
class MCodeFile:
    ppq: int = DEFAULT_PPQ
    puncher_times: int = DEFAULT_PUNCHER_TIMES
    messages: list[MCodeMessage] = field(default_factory=list)
    comments: list[str] = field(default_factory=lambda: [''] * 5)

    @classmethod
    def open(cls, file: str | Path | TextIO) -> Self:
        if isinstance(file, str | Path):
            with open(file, 'r', encoding='utf-8') as fp:
                return cls.from_str(fp.read())
        else:
            return cls.from_str(file.read())

    @classmethod
    def from_str(cls, s: str) -> Self:
        return cls.from_lines(s.splitlines())

    @classmethod
    def from_lines(cls, lines: list[str]) -> Self:
        mcode_file: Self = cls()
        for line in lines:
            if not line:
                continue
            if line.startswith('//'):
                mcode_file.comments.append(line[2:])
            else:
                try:
                    Mxx, Yxx, Pxx = line.strip().split()
                    if Mxx[0] != 'M' or Yxx[0] != 'Y' or Pxx[0] != 'P':
                        raise ValueError
                    M = int(Mxx[1:])
                    Y = int(Yxx[1:])
                    P = int(Pxx[1:])
                    mcode_file.messages.append(MCodeMessage(M, Y, P))
                except Exception:
                    raise ValueError(f'Invalid line: {line}')
        return mcode_file

    @classmethod
    def from_midi(cls, midi_file: MidiFile, transposition: int = 0) -> Self:
        mcode_file: Self = cls()
        notes: list[MCodeNote] = []
        for track in midi_file.tracks:
            midi_tick: int = 0
            for message in track:
                midi_tick += message.time
                if message.type == 'note_on' and message.velocity > 0:
                    try:
                        pitch_index: int = music_box_30_notes.range.index(message.note + transposition)
                    except ValueError:
                        logger.warning(f'Note {message.note + transposition} is not in the range of the music box.')
                        continue
                    notes.append(MCodeNote(pitch_index + 1,
                                           round(midi_tick / midi_file.ticks_per_beat * mcode_file.ppq)))

        notes.sort(key=lambda note: (note.tick, note.pitch_index))
        notes = get_arranged_notes(notes, mcode_file.ppq)

        mcode_file.messages.append(MCodeMessage(90, 500, 0))
        mcode_file.messages.extend(notes_to_messages(notes))
        mcode_file.messages.append(MCodeMessage(80, 500, 0))

        total_ticks: int = notes[-1].tick if notes else 0
        bytes_io = BytesIO()
        midi_file.save(file=bytes_io)
        bytes_data: bytes = bytes_io.getvalue()
        base64_str: str = base64.b64encode(bytes_data).decode('utf-8')
        mcode_file.comments[0] = f'Total: {total_ticks} ticks'
        mcode_file.comments[1] = f'PPQ: {mcode_file.ppq} ticks'
        mcode_file.comments[2] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        mcode_file.comments[3] = f'MusicBoxPuncher MCode. Generated by Music Box Designer.'
        mcode_file.comments[4] = f'MIDI {base64_str}'

        return mcode_file

    def export_midi(self,
                    use_comment: bool = True,
                    transposition: int = 0,
                    ticks_per_beat: int = MIDI_DEFAULT_TICKS_PER_BEAT) -> MidiFile:
        midi_file: MidiFile = MidiFile()
        midi_file.ticks_per_beat = ticks_per_beat
        midi_track: MidiTrack = MidiTrack()

        if use_comment:
            match = re.search(rf'MIDI ({base64_regex})', self.comments[4])
            if match is None:
                logger.warning('No midi data found in comments.')
            else:
                base64_str: str = match.group(1)
                bytes_data: bytes = base64.b64decode(base64_str)
                midi_file = MidiFile(file=BytesIO(bytes_data))
                return midi_file
        for pitch_index, tick in messages_to_notes(self.messages):
            pitch = music_box_30_notes.range[pitch_index - 1] + transposition
            if pitch not in range(128):
                logger.warning(f'Note {pitch} is not in range(128).')
                continue
            midi_track.append(Message('note_on',
                                      note=pitch,
                                      velocity=64,
                                      time=round(tick / self.ppq * ticks_per_beat)))
            midi_track.append(Message('note_off',
                                      note=pitch,
                                      time=round(((tick / self.ppq) + DEFAULT_DURATION) * ticks_per_beat)))
        midi_track.sort(key=lambda message: message.time)
        midi_file.tracks.append(MidiTrack(mido.midifiles.tracks._to_reltime(midi_track)))

        return midi_file

    def generate_pic(self, ppi: float = 300) -> Image.Image:
        notes: list[MCodeNote] = []
        tick: int = 0
        for message in self.messages:
            tick += message.Y
            if message.M in (90, 80):
                continue
            notes.append(MCodeNote(message.M, tick))
        length: float = tick / self.ppq * music_box_30_notes.length_mm_per_beat
        image_size: tuple[int, int] = pos_mm_to_pixel((music_box_30_notes.col_width, length), ppi, 'round')
        image: Image.Image = Image.new('RGBA', image_size, 'white')
        draw: ImageDraw.ImageDraw = ImageDraw.Draw(image)
        for index, tick in notes:
            draw_circle(
                image,
                pos_mm_to_pixel((music_box_30_notes.left_border + index * music_box_30_notes.grid_width,
                                 tick / self.ppq * music_box_30_notes.length_mm_per_beat),
                                ppi, 'round'),
                mm_to_pixel(1, ppi), 'black',
            )
        for (index0, tick0), (index1, tick1) in pairwise(notes):
            draw.line(
                (pos_mm_to_pixel((music_box_30_notes.left_border + index0 * music_box_30_notes.grid_width,
                                  tick0 / self.ppq * music_box_30_notes.length_mm_per_beat),
                                 ppi, 'round'),
                 pos_mm_to_pixel((music_box_30_notes.left_border + index1 * music_box_30_notes.grid_width,
                                  tick1 / self.ppq * music_box_30_notes.length_mm_per_beat),
                                 ppi, 'round')),
                'black',
                round(mm_to_pixel(0.5, ppi)),
            )
        return image

    def iter_lines(self) -> Generator[str, None, None]:
        for message in self.messages:
            yield str(message)
        for comment in self.comments:
            yield f'//{comment}'

    def __str__(self) -> str:
        return '\n'.join(self.iter_lines())

    def save(self, file: str | Path | TextIO) -> None:
        if len(self.comments) != 5:
            raise ValueError(f'Length of comments should be 5, got {len(self.comments)}.')
        s: str = str(self)
        if isinstance(file, str | Path):
            with open(file, 'w', encoding='utf-8') as fp:
                fp.write(s)
        else:
            file.write(s)
