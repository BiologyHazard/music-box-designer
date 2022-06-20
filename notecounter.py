from os.path import splitext

from mido import MidiFile

from emid import EmidFile

while True:
    filename = input('File Directory: ').strip('"')
    extension = splitext(filename)[1]

    if extension == '.mid':
        mid = MidiFile(filename)
        max_tick = 0
        notecount = 0
        for track in mid.tracks:
            tick = 0
            for msg in track:
                tick += msg.time
                if msg.type == 'note_on':
                    notecount += 1
                    max_tick = max(max_tick, tick)
        length = max_tick / mid.ticks_per_beat * 0.008

    elif extension == '.emid':
        emidfile = EmidFile(filename)
        notecount = 0
        for emidtrack in emidfile.tracks:
            notecount += len(emidtrack)
        length = emidfile.length / 1000

    print(f'Notes: {notecount}')
    print(f'Length: {length:.2f} m')
