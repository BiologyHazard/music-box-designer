import copy
import random

import mido
from mido import Message, MidiFile, MidiTrack

from .consts import DEFAULT_DURATION


def random_time_and_velocity(
    midi_file: MidiFile,
    time_sigma: float = 1 / 96,
    velocity_mu: float = 64,
    velocity_sigma: float = 8,
) -> MidiFile:
    new_file: MidiFile = copy.copy(midi_file)
    new_file.tracks = []
    for midi_track in midi_file.tracks:
        new_track = MidiTrack()
        midi_tick: int = 0
        for message in midi_track:
            midi_tick += message.time
            if message.type == "note_on" and message.velocity > 0:
                start = midi_tick / midi_file.ticks_per_beat + random.gauss(
                    0, time_sigma
                )
                start = max(0, start)
                new_track.append(
                    Message(
                        "note_on",
                        note=message.note,
                        velocity=round(random.gauss(velocity_mu, velocity_sigma)),
                        time=round(start * midi_file.ticks_per_beat),
                    )
                )
                new_track.append(
                    Message(
                        "note_off",
                        note=message.note,
                        time=round(
                            (start + DEFAULT_DURATION / 2) * midi_file.ticks_per_beat
                        ),
                    )
                )
        new_track.sort(key=lambda message: message.time)
        new_file.tracks.append(MidiTrack(mido.midifiles.tracks._to_reltime(new_track)))
    return new_file
