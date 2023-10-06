import json
from typing import Any
from pathlib import Path

from mido import MidiFile

from .draft import Draft, DraftSettings
from .emid import EmidFile
from .fmp import FmpFile


def emid_to_midi(emid_file_path) -> None:
    EmidFile.load_from_file(emid_file_path).export_midi().save('examples/example.mid')


def midi_to_emid(midi_file_path) -> None:
    midi_file = MidiFile(midi_file_path)
    emid_file = EmidFile.from_midi(midi_file)
    emid_file.save_to_file('examples/example.emid')

    # or in a single line:
    EmidFile.from_midi(MidiFile('examples/example.mid')).save_to_file('examples/example.emid')


def fmp_to_midi(fmp_file_path) -> None:
    FmpFile.load_from_file(fmp_file_path).export_midi().save('examples/example.mid')


def midi_to_fmp(midi_file_path) -> None:
    FmpFile.from_midi(MidiFile(midi_file_path)).save_to_file('examples/example.fmp')


def generate_draft(file_path, settings_path='settings.json', **kwargs) -> None:
    if settings_path is None or not Path(settings_path).is_file():
        settings = DraftSettings(**kwargs)
    else:
        with open(settings_path, 'r', encoding='utf-8') as fp:
            obj: dict[str, Any] = json.loads(fp.read())
        obj.update(kwargs)
        settings: DraftSettings = DraftSettings.model_validate(obj)

    Draft.load_from_file(file_path).export_pics(settings=settings).save()
