from consts import MUSIC_BOX_30_NOTES_PITCH, T_pitch


def pitch_to_mbindex(pitch: T_pitch) -> int:
    try:
        return MUSIC_BOX_30_NOTES_PITCH.index(pitch)
    except:
        raise ValueError(f'Pitch {pitch} not in range of 30 notes music box.')


def mbindex_to_pitch(mbindex: int) -> T_pitch:
    return MUSIC_BOX_30_NOTES_PITCH[mbindex]
