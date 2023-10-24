__all__: list[str] = ['logger',
                      'emid_to_midi',
                      'midi_to_emid',
                      'fmp_to_midi',
                      'midi_to_fmp',
                      'convert',
                      'generate_draft',
                      'get_note_count_and_length']

from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml
from mido import MidiFile

from .consts import LENGTH_MM_PER_BEAT
from .draft import Draft, DraftSettings, find_available_filename
from .emid import EmidFile
from .fmp import FmpFile
from .log import logger

# from typing import TypeVar

# _T = TypeVar('_T')
# def _check_overwrite(
#         function: Callable[[str | Path, str | Path], _T]
#     ) -> Callable[[str | Path, str | Path, bool], _T]:
#     def wrapper(source_file_path: str | Path, destination_file_path: str | Path, overwrite: bool = False) -> _T:
#         if not overwrite:
#             destination_file_path = find_available_filename(destination_file_path)
#         return function(source_file_path, destination_file_path)
#     return wrapper


_SUPPORTED_SUFFIXES: list[str] = ['.emid', '.fmp', '.mid']


def emid_to_midi(source_file_path: str | Path, destination_file_path: str | Path, overwrite: bool = False) -> None:
    if not overwrite:
        destination_file_path = find_available_filename(destination_file_path)
    EmidFile.load_from_file(source_file_path).export_midi().save(destination_file_path)


def midi_to_emid(source_file_path: str | Path, destination_file_path: str | Path, overwrite: bool = False) -> None:
    if not overwrite:
        destination_file_path = find_available_filename(destination_file_path)
    EmidFile.from_midi(MidiFile(source_file_path)).save_to_file(destination_file_path)


def fmp_to_midi(source_file_path: str | Path, destination_file_path: str | Path, overwrite: bool = False) -> None:
    if not overwrite:
        destination_file_path = find_available_filename(destination_file_path)
    FmpFile.load_from_file(source_file_path).export_midi().save(destination_file_path)


def midi_to_fmp(source_file_path: str | Path, destination_file_path: str | Path, overwrite: bool = False) -> None:
    if not overwrite:
        destination_file_path = find_available_filename(destination_file_path)
    FmpFile.new('Instrument').import_midi(MidiFile(source_file_path)).save_to_file(destination_file_path)


_FUNCTIONS: dict[tuple[str, str], Callable[[str | Path, str | Path, bool], None]] = {
    ('.emid', '.mid'): emid_to_midi,
    ('.mid', '.emid'): midi_to_emid,
    ('.fmp', '.mid'): fmp_to_midi,
    ('.mid', '.fmp'): midi_to_fmp,
}


def convert(source: str | Path, destination: str | Path, overwrite=False) -> None:
    def pure_suffix(path: Path) -> str:
        if '.' in path.name:
            return f'.{path.name.rsplit('.', maxsplit=1)[1]}'
        return ''

    def pure_stem(path: Path) -> str:
        return path.name.rsplit('.', maxsplit=1)[0]

    source = Path(source)
    destination = Path(destination)
    if pure_suffix(source) not in _SUPPORTED_SUFFIXES:
        raise ValueError("The source extension must be '.emid', '.fmp' or '.mid'.")
    if pure_suffix(destination) not in _SUPPORTED_SUFFIXES:
        raise ValueError("The destination extension must be '.emid', '.fmp' or '.mid'.")

    if pure_stem(source) not in ('', '*'):  # 如果指定了特定一个文件
        if not pure_stem(destination):
            destination = source.with_suffix(pure_suffix(destination))
        function = _FUNCTIONS.get((pure_suffix(source), pure_suffix(destination)))
        if function is None:
            raise ValueError(f"Cannot convert '{pure_suffix(source)}' file to '{pure_suffix(destination)}' file.")
        return function(source, destination, overwrite)

    # 如果未指定特定一个文件，则把 source 目录下所有符合扩展名的文件全部转换
    for path in source.parent.iterdir():
        if path.suffix == pure_suffix(source):
            if destination == Path(pure_suffix(destination)):
                temp_destination: Path = path.with_suffix(
                    pure_suffix(destination))  # source_directory/source_name.suffix
            else:  # something/name.suffix
                temp_destination = destination.with_stem(source.stem)  # something/source_name.suffix
            # 递归调用 convert 单文件的版本
            return convert(path, temp_destination, overwrite)


def generate_draft(file_path: str | Path,
                   settings_path: str | Path | None = None,
                   overwrite: bool = False,
                   **kwargs) -> None:
    if settings_path is None or not Path(settings_path).is_file():
        logger.warning(f'Settings path not specified, using kwargs {kwargs!r} to initialize DraftSettings.')
        settings: DraftSettings = DraftSettings(**kwargs)
    else:
        with open(settings_path, 'rb') as fp:
            obj: dict[str, Any] = yaml.safe_load(fp)
        obj.update(kwargs)
        settings = DraftSettings.model_validate(obj)

    Draft.load_from_file(file_path).export_pics(settings=settings).save(overwrite=overwrite)


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
