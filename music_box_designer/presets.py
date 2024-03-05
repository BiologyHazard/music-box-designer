from dataclasses import dataclass, field
from typing import overload


@dataclass(frozen=True)
class MusicBox:
    note_count: int
    range: list[int]
    grid_width: float
    left_border: float
    right_border: float
    min_trigger_spacing: float = 7
    length_mm_per_beat: float = 8

    col_width: float = field(init=False)

    def __post_init__(self) -> None:
        if len(self.range) != self.note_count:
            raise ValueError('The length of range must be equal to notes.')
        object.__setattr__(self, 'col_width',
                           self.left_border + self.grid_width * (self.note_count - 1) + self.right_border)


music_box_30_notes = MusicBox(
    note_count=30,
    range=[53, 55, 60, 62, 64, 65, 67, 69, 70, 71,
           72, 73, 74, 75, 76, 77, 78, 79, 80, 81,
           82, 83, 84, 85, 86, 87, 88, 89, 91, 93],
    grid_width=2,
    left_border=6,
    right_border=6,
)

music_box_20_notes = MusicBox(
    note_count=20,
    range=[60, 62, 64, 65, 67, 69, 71, 72, 74, 76,
           77, 79, 81, 83, 84, 86, 88, 89, 91, 93],
    grid_width=3,
    left_border=6.5,
    right_border=6.5,
)

music_box_15_notes = MusicBox(
    note_count=15,
    range=[68, 70, 72, 73, 75, 77, 79,
           80, 82, 84, 85, 87, 89, 91, 92],
    grid_width=2,
    left_border=6,
    right_border=6,
)

music_box_presets: dict[int, MusicBox] = {
    15: music_box_15_notes,
    20: music_box_20_notes,
    30: music_box_30_notes,
}


@overload
def get_preset(preset_like: int | MusicBox | None,
               /,
               default: None = ...) -> MusicBox | None: ...


@overload
def get_preset(preset_like: int | MusicBox | None,
               /,
               default: MusicBox = ...) -> MusicBox: ...


def get_preset(preset_like: int | MusicBox | None,
               /,
               default: MusicBox | None = None) -> MusicBox | None:
    if preset_like is None:
        return default
    elif isinstance(preset_like, int):
        if preset_like not in music_box_presets:
            raise ValueError(f'{preset_like} note music box not in presets.')
        return music_box_presets[preset_like]
    elif isinstance(preset_like, MusicBox):
        return preset_like
    else:
        raise TypeError(f'preset_like must be int, MusicBox or None, got {type(preset_like)}.')
