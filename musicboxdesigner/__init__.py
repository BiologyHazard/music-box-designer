from pathlib import Path
from typing import Any

import yaml
from mido import MidiFile

from .consts import LENGTH_MM_PER_BEAT
from .draft import Draft, DraftSettings
from .emid import EmidFile
from .fmp import FmpFile

__all__: list[str] = ['emid_to_midi',
                      'midi_to_emid',
                      'fmp_to_midi',
                      'midi_to_fmp',
                      'generate_draft',
                      'get_note_count_and_length']


def emid_to_midi(emid_file_path, midi_file_path) -> None:
    EmidFile.load_from_file(emid_file_path).export_midi().save(midi_file_path)


def midi_to_emid(midi_file_path, emid_file_path) -> None:
    EmidFile.from_midi(MidiFile(midi_file_path)).save_to_file(emid_file_path)


def fmp_to_midi(fmp_file_path, midi_file_path) -> None:
    FmpFile.load_from_file(fmp_file_path).export_midi().save(midi_file_path)


def midi_to_fmp(midi_file_path, fmp_file_path) -> None:
    FmpFile.from_midi(MidiFile(midi_file_path)).save_to_file(fmp_file_path)


def generate_draft(file_path, settings_path='draft_settings.yml', **kwargs) -> None:
    if settings_path is None or not Path(settings_path).is_file():
        settings = DraftSettings(**kwargs)
    else:
        with open(settings_path, 'r', encoding='utf-8') as fp:
            obj: dict[str, Any] = yaml.safe_load(fp.read())
        obj.update(kwargs)
        settings: DraftSettings = DraftSettings.model_validate(obj)

    Draft.load_from_file(file_path).export_pics(settings=settings).save()


def get_note_count_and_length(file_path: str | Path,
                              transposition: int = 0,
                              remove_blank: bool = True,
                              skip_near_notes: bool = True,
                              bpm: float | None = None,
                              scale: float = 1) -> tuple[int, float]:
    draft: Draft = Draft.load_from_file(file_path, transposition, remove_blank, skip_near_notes, bpm)
    if draft.notes:
        length: float = draft.notes[-1].time * LENGTH_MM_PER_BEAT * scale
    else:
        length = 0

    return len(draft.notes), length
