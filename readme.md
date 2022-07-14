# ReaSamplOmatic5000 Multi

## Contents a

1. [Dependencies and Installation](#dependencies-and-installation]
2. [Usage notes](#usage-notes)
    * [Creating groups](#creating-groups)
3. [To-do](#to-do)
4. [Limitations](#limitations)
5. [License](#license)

## Dependencies and Installation
You need to install `reapy` and `tkinter` for the program to work. To install `reapy`, see the instructions over [here](https://github.com/RomeoDespres/reapy#installation). Make sure you have Python installed and that it is detected by REAPER.

For MIDI support, you need `mido` and `rtmidi` as well. All should be available through pip (use `pip install mido rtmidi`).

## Usage notes
The multisampler only does the note ranges, you need to add the samples, remove ReaSamplOmatic5000 instances, and change any other options inside of REAPER. You can also set the names of the ReaSamplOmatic5000 instances, which will be reflected in the multisampler. You need to hit `refresh` for this to update though.

The `add` button adds an instance of ReaSamplOmatic5000 on all selected tracks. If no track is selected, it creates a new track.

The multisampler will show all ReaSamplOmatic5000s from the selected track. Check `freeze` to stay on the selected track, and not follow the selection any more.

You can click on any range to open up its FX-window.

Zoom with `ctrl+mousewheel`, or the `+` and `-` buttons. Zoom the piano roll with `alt+mousewheel`.

All actions are done in REAPER, so undo/redo is supported via REAPER itself. (Just remember to hit `refresh` afterwards).

If you want, you can change some default values at the top of the script (short descriptions are included).

The multisampler also uses the track colors. You can set the alpha parameter at the top of the script to change how to colors are used.

You can click on the notes on the piano roll to send MIDI data to reaper. Velocity is dependent on the height of your mouse. Read the script for details on how to set it up.

You can press `r` as a shortcut for `refresh`, and `s` is a shortcut for `separate`.

### Creating groups

The `separate` button takes all ReaSamplOmatic5000 instances on the current track, and separates them over new tracks. It adds a MIDI-route from the selected track to these tracks. This is useful for individual effects processing (for instance: for the bass drum, the snare, hi-hats, etc.). You can still edit the ranges in the original multisampler window.

You can select any of these tracks and use the multisampler on them individually. This acts essentially as a group, where you can add and tweak additional FX for this set of ReaSamplOmatic5000s as you please. Selecting the original parent track again gives you access to all groups at once.

When the `create bus` option is ticked, an additional bus track is created. You can make a folder of the created track with this as the parent track to mix everything together. If you have the SWS extension installed, this is done automatically!

## To-do
Let overlap between sample ranges behave nicely. For instance: separate identical ranges to the same track, render on top of each other.

Reapy can check for changes in track names/colors/etc., which would eliminate the need to hit `refresh` manually. (Although since `refresh` is very slow, this might actually be undesirable behaviour.)


## Limitations
Tkinter (the Python GUI toolkit) wasn't really made for things like this, so for instance zooming is somewhat unstable. Please tell me if you know of a way to circumvent this!

More importantly, tkinter needs to run on the main thread, while REAPER can only run scripts on its main thread.
This means that communication with REAPER needs to be done indirectly via sockets, otherwise the multisampler GUI would make REAPER hang. This makes everything (in particular parsing of the track information and `refresh`) very slow. I could not find Python GUI toolkits which do not run on the main thread, but some might exist. If you know of ways to circumvent this, let me know!

Reapy cannot set set the sample(s) of ReaSamplOmatic5000, so drag-and-drop directly into the multisampler not possible sadly. Although you can drag-and-drop into the individual ReaSamplOmatic5000s of course.

I couldn't get reapy to detect the FX type. Instead, I have to manually try with a try-except if they contain the parameters identifying the ReaSamplOmatic5000 (ew!).


## License

The script is licensed under the GNU GPLv3, see [license](LICENSE.txt].