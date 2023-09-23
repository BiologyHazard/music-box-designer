MM_PER_INCH = 25.4

DEFAULT_TICKS_PER_BEAT = 96
'''FL导出的midi默认为此值'''

NOTES = 30
MUSIC_BOX_30_NOTES_PITCH: list[int] = [53, 55, 60, 62, 64, 65, 67, 69, 70, 71,
                                       72, 73, 74, 75, 76, 77, 78, 79, 80, 81,
                                       82, 83, 84, 85, 86, 87, 88, 89, 91, 93]
MIN_TRIGGER_SPACING = 7.0
LENGTH_MM_PER_BEAT = 8.0
GRID_WIDTH = 2.0
LEFT_BORDER = RIGHT_BORDER = 6.0
COL_WIDTH: float = LEFT_BORDER + (NOTES - 1) * GRID_WIDTH + RIGHT_BORDER  # 每栏宽70mm

DEFAULT_DURATION = 1
