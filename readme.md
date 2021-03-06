# ReaSamplOmatic5000 multi

 ReaSamplOmatic500 multi lets you arrange ReaSamplOmatic5000 instances on a piano roll. This project aims to give REAPER a fully fledged sampler, such as FL Studio's _DirectWave Sampler_ or the _TX16Wx Software Sampler_, while also nicely integrating into REAPER.

 The script is powered by the excellent [reapy](https://github.com/RomeoDespres/reapy), and uses [tkinter](https://docs.python.org/3/library/tkinter.html) for the GUI.

## Contents

1. [Dependencies and Installation](#dependencies-and-installation)
2. [Usage notes](#usage-notes)
    * [Features list](#feature-list)
    * [Creating groups](#creating-groups)
3. [To-do](#to-do)
4. [Limitations](#limitations)
5. [License](#license)

## Dependencies and Installation

You need to install `reapy` and `tkinter` for the program to work. To install `reapy`, see the instructions over [here](https://github.com/RomeoDespres/reapy#installation). Make sure you have Python installed and that it is detected by REAPER. `tkinter` should be installed by default.

For MIDI support, you need `mido` and `python-rtmidi` as well. All should be available through pip (use `pip install mido python-rtmidi`).

## Usage notes

The multisampler only does the note ranges, you need to add the samples, remove ReaSamplOmatic5000 instances, and change any other options inside of REAPER. You can also set the names of the ReaSamplOmatic5000 instances, which will be reflected in the multisampler. You need to hit `Refresh` for this to update.

The multisampler will show all ReaSamplOmatic5000s from the selected track. Check `freeze` to stay on the selected track, and not follow the selection any more.

All actions are done in REAPER, so undo/redo is supported via REAPER itself. (Just remember to hit `Refresh` afterwards).

### Feature list

A short list of features and usage notes:

 * __Adding instances__ The `Add` button adds an instance of ReaSamplOmatic5000 on all selected tracks. If no track is selected, it creates a new track.
 * __Moving__ Move note ranges by clicking and dragging.
 * __Resizing__ Click the range edges and drag to resize them.
 * __Selecting__ You can select and edit multiple ranges by holding `ctrl` and clicking, or by selecting multiple ranges with the right mouse button.
 * __Copy/paste/delete__ Press `ctrl+c` and `ctrl+v` for copy and paste respectively.  Press `delete` or `d` to delete the selection.
 * __Layering__ The note ranges align vertically such that they don't overlap. This allows for easy layering of multiple samples.
 * __Groups__ The multi-sampler integrates with MIDI routing in REAPER. See [creating groups](#creating-groups) for more information.
 * __Open FX window__ You can click on any range to open up its FX-window. Double click to also close the windows of all other groups.
 * __Scroll & zoom__ Scroll the view with the mouse wheel, or click the middle mouse button and drag. Zoom with `ctrl+mousewheel`, or the `+` and `-` buttons. Zoom the piano roll with `alt+mousewheel`. The window is freely resizable (you can change the default size in the script).
 * __MIDI__ You can click on the notes on the piano roll to send MIDI data to reaper. Velocity is dependent on the height of your mouse. Read the script for details on how to set it up.
 * __Obey note-offs__ You can select whether newly added instances should obey note-offs or not (useful for sampling drums)
 * __Shortcuts__ You can press `r` as a shortcut for `Refresh`, `a` for `Add`, and `s` for `Separate`. Press `c` to scroll the view to C2.
 * __Defaults__ If you want, you can change some default values at the top of the script (short descriptions are given). You can change behaviour as well as appearance.
 * __Colors__ The multisampler also uses the track colors. You can set the alpha parameter at the top of the script to change how to colors are used.

### Creating groups

The `Separate` button takes all ReaSamplOmatic5000 instances on the current track, and separates them over new tracks. It adds a MIDI-route from the selected track to these tracks. This is useful for individual effects processing (for instance when sampling drums: for the bass drum, the snare, hi-hats, etc.). You can still edit the ranges in the original multisampler window.

You can select any of these tracks and use the multisampler on them individually. This acts essentially as a group, where you can add and tweak additional FX for this set of ReaSamplOmatic5000s as you please. Selecting the original parent track again gives you access to all groups at once. In fact, the GUI will show all ReaSamplOmatic5000 instances which are reached through MIDI routing from the selected track (up to a recursion limit, which you can change at the top of the script).

When the `create bus` option is ticked, an additional bus track is created. You can make a folder of the created track with this as the parent track to mix everything together. If you have the SWS extension installed, this is done automatically!

## To-do
 - [ ] A way to save user settings without requiring them to edit the script.
 - [ ] Reapy can check for changes in track names/colors/etc., which would eliminate the need to hit `refresh` manually. (Although since `refresh` is very slow, this might actually be undesirable behaviour.)



## Limitations

Tkinter (the Python GUI toolkit) wasn't really made for things like this, so for instance zooming is somewhat unstable. Please tell me if you know of a way to circumvent this!

More importantly, tkinter needs to run on the main thread, while REAPER can only run scripts on its main thread.
This means that communication with REAPER needs to be done indirectly via sockets, otherwise the multisampler GUI would make REAPER hang. This makes everything (in particular parsing of the track information and `refresh`) very slow. I could not find Python GUI toolkits which do not run on the main thread, but some might exist. If you know of ways to circumvent this, let me know!

Reapy cannot set set the sample(s) of ReaSamplOmatic5000, so drag-and-drop directly into the multisampler seems impossible sadly. Although you can drag-and-drop into the individual ReaSamplOmatic5000s of course.

## License

The script is licensed under the GNU GPLv3, see [license](LICENSE).
