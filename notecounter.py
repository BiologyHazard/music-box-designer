import mido
while True:
    filename = input('File Directory: ')
    if filename.startswith('"'):
        filename = filename[1:-1]
    mid = mido.MidiFile(filename)
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
    print('Notes:', notecount)
    print('Length:', "%.2f" % length, 'm')
