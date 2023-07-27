from consts import MUSIC_BOX_30_NOTES_PITCH, T_pitch
from typing import BinaryIO, Literal


def pitch_to_mbindex(pitch: T_pitch) -> int:
    try:
        return MUSIC_BOX_30_NOTES_PITCH.index(pitch)
    except:
        raise ValueError(f'Pitch {pitch} not in range of 30 notes music box.')


def mbindex_to_pitch(mbindex: int) -> T_pitch:
    return MUSIC_BOX_30_NOTES_PITCH[mbindex]


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
