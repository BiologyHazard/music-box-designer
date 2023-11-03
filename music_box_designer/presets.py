from dataclasses import dataclass, field


@dataclass(frozen=True)
class MusicBox:
    notes: int
    range: tuple[int, ...]
    grid_width: float
    left_border: float
    right_border: float
    min_trigger_spacing: float = 7
    length_mm_per_beat: float = 8

    col_width: float = field(init=False)

    def __post_init__(self) -> None:
        if len(self.range) != self.notes:
            raise ValueError('The length of range must be equal to notes.')
        object.__setattr__(self, 'col_width', self.left_border + self.grid_width * (self.notes - 1) + self.right_border)


music_box_30_notes = MusicBox(
    notes=30,
    range=(53, 55, 60, 62, 64, 65, 67, 69, 70, 71,
           72, 73, 74, 75, 76, 77, 78, 79, 80, 81,
           82, 83, 84, 85, 86, 87, 88, 89, 91, 93),
    grid_width=2,
    left_border=6,
    right_border=6,
)

music_box_20_notes = MusicBox(
    notes=20,
    range=(60, 62, 64, 65, 67, 69, 71, 72, 74, 76,
           77, 79, 81, 83, 84, 86, 88, 89, 91, 93),
    grid_width=3,
    left_border=6.5,
    right_border=6.5,
)

music_box_15_notes = MusicBox(
    notes=15,
    range=(68, 70, 72, 73, 75, 77, 79,
           80, 82, 84, 85, 87, 89, 91, 92),
    grid_width=2,
    left_border=6,
    right_border=6,
)

music_box_presets: dict[int, MusicBox] = {
    15: music_box_15_notes,
    20: music_box_20_notes,
    30: music_box_30_notes,
}
