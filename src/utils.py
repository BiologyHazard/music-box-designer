import logging
from typing import BinaryIO, Literal
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont

from .consts import MUSIC_BOX_30_NOTES_PITCH, MM_PER_INCH


def pitch_to_mbindex(pitch: int) -> int:
    try:
        return 29 - MUSIC_BOX_30_NOTES_PITCH.index(pitch)
    except ValueError:
        raise ValueError(f'Pitch {pitch} not in range of 30 notes music box.')


def mbindex_to_pitch(mbindex: int) -> int:
    if mbindex in range(30):
        return MUSIC_BOX_30_NOTES_PITCH[mbindex]
    else:
        raise ValueError('mbindex must be int in range(30)')


def read_int(file: BinaryIO,
             /,
             byte: int = 1,
             byteorder: Literal['big', 'little'] = 'little',
             signed: bool = False) -> int:
    return int.from_bytes(file.read(byte), byteorder, signed=signed)


def read_bool(file: BinaryIO) -> bool:
    b: bytes = file.read(1)
    i: int = int.from_bytes(b)
    if i not in (0, 1):
        raise ValueError(f'Read value {repr(b)} is not a bool.')
    return bool(i)


def mm_to_pixel(x: float, /, ppi: float) -> float:
    return x / MM_PER_INCH * ppi


def pixel_to_mm(x: float, /, ppi: float) -> float:
    return x * MM_PER_INCH / ppi


def pos_mm_to_pixel(pos: tuple[float, float], /, ppi: float) -> tuple[int, int]:
    x, y = pos
    return (round(mm_to_pixel(x, ppi)), round(mm_to_pixel(y, ppi)))


# @lru_cache
# def get_font(font_path: str | Path, size: int, **kwargs) -> ImageFont.FreeTypeFont:
#     return ImageFont.truetype(str(font_path), size, **kwargs)

@lru_cache
def get_empty_draw() -> ImageDraw.ImageDraw:
    return ImageDraw.Draw(Image.new('RGBA', (0, 0)))


# def log_func(f):
#     def wrapped(*args, **kwargs):
#         result = f(*args, **kwargs)
#         logging.debug(f'{f.__name__}({args}, {kwargs}) returns {result}')
#         return result
#     return wrapped


# @log_func
def get_text_height(text: str, font: ImageFont.FreeTypeFont, **kwargs) -> int:
    return (
        get_empty_draw().multiline_textbbox((0, 0), text, font, 'la', **kwargs)[3]
        - get_empty_draw().multiline_textbbox((0, 0), text, font, 'ld', **kwargs)[3]
    )


def draw_circle(draw: ImageDraw.ImageDraw, center: tuple[float, float], radius: float, fill=None, outline=None, width: int = 1) -> None:
    x, y = center
    xy: tuple[tuple[int, int], tuple[int, int]] = ((round(x - radius), round(y - radius)),
                                                   (round(x + radius), round(y + radius)))
    draw.ellipse(xy, fill, outline, width)
