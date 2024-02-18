__all__: list[str] = [
    'logger',
    'emid_to_midi',
    'midi_to_emid',
    'fmp_to_midi',
    'midi_to_fmp',
    'convert',
    'generate_draft',
    'get_note_count_and_length',
]

from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml
from mido import MidiFile

from .draft import Draft, DraftSettings, find_available_filename
from .emid import EmidFile
from .fmp import FmpFile
from .log import logger
from .mcode import MCodeFile
from .presets import MusicBox, get_preset, music_box_30_notes, music_box_presets

# from functools import wraps
# from typing import TypeVar
# _T = TypeVar('_T')
# def _check_overwrite(
#         function: Callable[[str | Path, str | Path, int], _T]
# ) -> Callable[[str | Path, str | Path, int, bool], _T]:
#     @wraps(function)
#     def wrapper(source_file_path: str | Path,
#                 destination_file_path: str | Path,
#                 transposition: int = 0,
#                 overwrite: bool = False) -> _T:
#         destination_file_path = find_available_filename(destination_file_path, overwrite)
#         return function(source_file_path, destination_file_path, transposition)
#     return wrapper


_SUPPORTED_SUFFIXES: list[str] = ['.emid', '.fmp', '.mid', '.mcode']


def emid_to_midi(source_file_path: str | Path,
                 destination_file_path: str | Path,
                 transposition: int = 0,
                 overwrite: bool = False) -> None:
    EmidFile.load_from_file(
        source_file_path
    ).export_midi(
        transposition=transposition
    ).save(
        find_available_filename(destination_file_path, overwrite=overwrite)
    )


def midi_to_emid(source_file_path: str | Path,
                 destination_file_path: str | Path,
                 transposition: int = 0,
                 overwrite: bool = False) -> None:
    EmidFile.from_midi(
        MidiFile(source_file_path),
        transposition=transposition,
    ).save_to_file(
        find_available_filename(destination_file_path, overwrite=overwrite)
    )


def fmp_to_midi(source_file_path: str | Path,
                destination_file_path: str | Path,
                transposition: int = 0,
                overwrite: bool = False) -> None:
    FmpFile.load_from_file(
        source_file_path
    ).export_midi(
        transposition=transposition
    ).save(
        find_available_filename(destination_file_path, overwrite=overwrite)
    )


def midi_to_fmp(source_file_path: str | Path,
                destination_file_path: str | Path,
                transposition: int = 0,
                overwrite: bool = False) -> None:
    FmpFile.new('Instrument').import_midi(
        MidiFile(source_file_path),
        transposition=transposition,
    ).save_to_file(
        find_available_filename(destination_file_path, overwrite=overwrite)
    )


def mcode_to_midi(source_file_path: str | Path,
                  destination_file_path: str | Path,
                  transposition: int = 0,
                  overwrite: bool = False) -> None:
    MCodeFile.open(
        source_file_path
    ).export_midi(
        transposition=transposition
    ).save(
        find_available_filename(destination_file_path, overwrite=overwrite)
    )


def midi_to_mcode(source_file_path: str | Path,
                  destination_file_path: str | Path,
                  transposition: int = 0,
                  overwrite: bool = False) -> None:
    MCodeFile.from_midi(
        MidiFile(source_file_path),
        transposition=transposition,
    ).save(
        find_available_filename(destination_file_path, overwrite=overwrite)
    )


_FUNCTIONS: dict[tuple[str, str], Callable[[str | Path, str | Path, int, bool], None]] = {
    ('.emid', '.mid'): emid_to_midi,
    ('.mid', '.emid'): midi_to_emid,
    ('.fmp', '.mid'): fmp_to_midi,
    ('.mid', '.fmp'): midi_to_fmp,
    ('.mcode', '.mid'): mcode_to_midi,
    ('.mid', '.mcode'): midi_to_mcode,
}


def convert(source: str | Path,
            destination: str | Path,
            transposition: int = 0,
            overwrite: bool = False) -> None:
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
        return function(source, destination, transposition, overwrite)

    # 如果未指定特定一个文件，则把 source 目录下所有符合扩展名的文件全部转换
    for path in source.parent.iterdir():
        if path.suffix == pure_suffix(source):
            if destination == Path(pure_suffix(destination)):
                temp_destination: Path = path.with_suffix(
                    pure_suffix(destination))  # source_directory/source_name.suffix
            else:  # something/name.suffix
                temp_destination = destination.with_stem(source.stem)  # something/source_name.suffix
            # 递归调用 convert 单文件的版本
            return convert(path, temp_destination, transposition=transposition, overwrite=overwrite)


def generate_draft(file_path: str | Path,
                   settings_path: str | Path | None = None,
                   pdf: bool = False,
                   note_count: int | None = None,
                   transposition: int = 0,
                   remove_blank: bool = True,
                   skip_near_notes: bool = True,
                   bpm: float | None = None,
                   title: str | None = None,
                   subtitle: str | None = None,
                   music_info: str | None = None,
                   show_bpm: float | None = None,
                   scale: float = 1,
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

    # if note_count is not None and note_count not in music_box_presets:
    #     raise ValueError(f'{note_count} note music box not in presets.')
    # preset: MusicBoxPreset | None = music_box_presets[note_count] if note_count is not None else None
    Draft.load_from_file(
        file_path,
        preset=get_preset(note_count),
        transposition=transposition,
        remove_blank=remove_blank,
        skip_near_notes=skip_near_notes,
        bpm=bpm,
    ).export_pics(
        settings=settings,
        title=title,
        subtitle=subtitle,
        music_info=music_info,
        show_bpm=show_bpm,
        scale=scale,
    ).save(format='PDF' if pdf else 'PNG', overwrite=overwrite)


def get_note_count_and_length(file_path: str | Path,
                              note_count: int | None = None,
                              transposition: int = 0,
                              remove_blank: bool = True,
                              skip_near_notes: bool = True,
                              bpm: float | None = None,
                              scale: float = 1) -> tuple[int, float]:
    draft: Draft = Draft.load_from_file(file_path,
                                        preset=get_preset(note_count),
                                        transposition=transposition,
                                        remove_blank=remove_blank,
                                        skip_near_notes=skip_near_notes,
                                        bpm=bpm)
    if draft.notes:
        length: float = draft.notes[-1].time * draft.preset.length_mm_per_beat * scale
    else:
        length = 0

    return len(draft.notes), length
