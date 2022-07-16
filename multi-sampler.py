# A script for REAPER implementing a GUI multisampler for
# ReaSamplOmatic5000, using reapy and tkinter.
#
# Some configuration options are available, see below.
#
# For more detailed instructions, consult readme.md.
#
# Author: Maxim van den Berg
# Github: github.com/maximvdberg/samplomatic5000-multi
#
# Big thanks to Roméo Després and contributors for the
# reapy project!
# Link: https://github.com/RomeoDespres/reapy

import reapy as rp
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.font as tkfont
import mido

import threading
import math
import sys

# Configuration options - Defaults (changeable in GUI)
width_per_note = 20        # Width in pixels of the notes.
piano_roll_height = 60     # Height in pixels of the piano roll.
obey_note_offs = 0         # Value to set "Obey note-offs" in ReaSamplOmatic5000
create_bus_on_separate = 1 # Wether to create a bus channel on separate.

# Configuration options - Functionality
small_resize_width = width_per_note / 3 # small_resize_width is the size of the
                                        # handles used for resizing the ranges,
                                        # when the size is <= 2.
scroll_speed = 1 # Speed to scroll.
zoom_speed = 1   # Speed to zoom.
default_window_size = '1000x400'
max_recursion_depth = 10 # Max. depth to look for ReaSamplOmatics in send tracks
                         # of the selected track.

# Configuration options - Appearance
highlight = 1            # Thickness of the highlights. Set to 0 for a "flat" look
                         # Always set to 0 on Windows.
alpha = 0.7              # Alpha of the track colors.
                         # 0.2 looks nice with a dark background.
text_color = 'lightgray' # Text color of the sample ranges.
                         # Change to 'black' when using light colors.
background_color = "#202020" # Background color.
foreground_color = "#F0F0F0" # Foreground color.
                             # Interchange the colors for light theme.
highlight_color = "#e0e0e0"  # Color of the highlights

# Configuration options - MIDI
midi_port_name = "Midi Through" # You can change this to the name of
                                # the MIDI input port you use in reaper.

# Configuration options - Defaults in REAPER/SamplOmatic5000.
gain_for_minimum_velocity = 0.03162277489900589 # "Min vol" in REAPER.
                                                # Necessary for dynamics.


# Some global variables
freeze = False
current_track = None
samplomatics = []
last_touched = None
top_level_window = None
root = None
scrollbar = None
canvas = None
window = None
pianoroll_frame = None
pixel = None
track_name_text = None
port = None
midi_available = False
render_groups = []
adjust_for_highlight = True

# Constants
total_notes = 128

def rgb(rgb, a = 1):
    return "#%02x%02x%02x" % (int(rgb[0]*a), int(rgb[1]*a), int(rgb[2]*a))

# The main note range class.
class SamploRange():
    def __init__(self, window, fx, color=(255, 255, 255)):
        self.window = window
        self.project = rp.Project()
        self.index = fx.index
        self.fx = fx

        self.start = round(fx.params["Note range start"] * 127)
        self.end = round(fx.params["Note range end"] * 127)

        # Create the moveable widget.
        global alpha
        font = tkfont.Font(size=8)
        self.widget = tk.Canvas(self.window,
                                highlightthickness=highlight,
                           highlightbackground=rgb(color),
                           bg=rgb(color, alpha),
                           bd=0)
        self.widget.bind("<B1-Motion>", self.mouse)
        self.widget.bind("<ButtonRelease-1>", self.button_release)
        self.widget.bind("<Motion>", self.motion)
        self.widget.bind('<Double-Button-1>', lambda e: self.show(True))

        # Text.
        self.text_hor = None
        self.text_ver = None

        # Render group information.
        self.render_group = None
        self.layer_count = 1
        self.layer = 0

        self.redraw()

        self.mouse_start_x = 0
        self.mouse_start_y = 0
        self.mouse_current_x = 0
        self.mouse_current_y = 0

        self.in_motion = False
        self.resize_side = 0
        self.resize_start_left = 0

    # # Drawing # #
    def redraw(self):
        # Position and sizes.
        width = int(width_per_note * (self.end - self.start + 1))
        max_height = int(window.winfo_height() - piano_roll_height)
        height = max_height // self.layer_count

        x_pos = int(width_per_note * self.start)
        y_pos = self.layer * height

        # The last layer should be a bit larger, when
        # `layer_count` does not divide `max_height`.
        if self.layer == self.layer_count - 1:
            height += max_height - self.layer_count * height

        global adjust_for_highlight
        if adjust_for_highlight:
            width -= 2 * highlight
            height -= 2 * highlight

        # Drawing.
        self.widget.place(x=x_pos, y=y_pos)
        self.widget.configure(width=width, height=height)

        self.draw_name()

    def draw_name(self):
        offscreen = -50

        # Initialise the text (horizontally).
        if not self.text_hor:
            global text_color
            self.text_hor = self.widget.create_text(1, 0, text=self.fx.name,
                    anchor="nw", fill=text_color)
            self.text_ver = self.widget.create_text(offscreen, 0, text=self.fx.name,
                    anchor="nw", angle=90, fill=text_color)

        box = self.widget.bbox(self.text_hor)
        text_length = box[2] - box[0]
        text_height = box[1] - box[3]
        width = int(width_per_note * (self.end - self.start + 1))

        if text_length + 5 > width:
            # Place text vertically.
            self.widget.moveto(self.text_hor, 0, offscreen)
            self.widget.moveto(self.text_ver, 0, 2)
        else:
            # Place text horizontally.
            self.widget.moveto(self.text_hor, 3, 0)
            self.widget.moveto(self.text_ver, offscreen, 0)

    # # Event Handlers # #
    # On (double) click, show ui window.
    def show(self, exclusive=False):
        global samplomatics

        if exclusive:
            for samplorange in samplomatics:
                if samplorange != self:
                    samplorange.fx.close_ui()

        self.fx.open_ui()

    # Mouse motion, saves x and y position of the cursor.
    def motion(self, event):
        self.mouse_current_x = event.x
        self.mouse_current_y = event.y

    # On button release, reset moving/resizing parameters, and update
    # REAPER. Also set this instance to the last touched range.
    def button_release(self, event):
        self.show()

        self.in_motion = False
        self.resize_side = 0
        self.update_reaper()
        self.resize_start_left = 0

        global last_touched
        last_touched = self

    # Helper function to get event info.
    def event_info(self, event):
        c = event.widget
        x, y = c.winfo_x(), c.winfo_y()
        w, h = c.winfo_width(), c.winfo_height()
        x_add, y_add = event.x, event.y
        x_max, y_max = self.window.winfo_width(), self.window.winfo_height()
        return c, x, y, w, h, x_add, y_add, x_max, y_max

    # Handler for mouse click and drag. Depending on location, calls
    # resize or move.
    def mouse(self, event):
        c, x, y, w, h, x_add, y_add, x_max, y_max = self.event_info(event)

        start_old, end_old = (self.start, self.end)

        if not self.in_motion:
            self.mouse_start_x = self.mouse_current_x
            self.mouse_start_y = self.mouse_current_y
            self.resize_start_left = self.start
            self.in_motion = True

            # Check if resizing
            resize_width = width_per_note
            if self.end - self.start <= 2:
                resize_width = small_resize_width

            if self.mouse_start_x >= w - resize_width:
                self.resize_side = 1
            elif self.mouse_start_x < resize_width:
                self.resize_side = -1

        if self.resize_side != 0:
            self.resize(event)
        else:
            self.move(event)

        global render_groups
        if (start_old != self.start or end_old != self.end):
            move_through_groups(render_groups, self)

    # Resize the note range.
    def resize(self, event):
        c, x, y, w, h, x_add, y_add, x_max, y_max = self.event_info(event)

        if (self.resize_side > 0):
            # Resize to the right
            x_new = event.x
            end_new = max(0, math.floor(x_new / width_per_note))
            self.end = self.start + end_new
        else:
            # Resize to the left
            x_new = event.x + (self.start - self.resize_start_left) * width_per_note
            start_new = min(self.end - self.resize_start_left, math.floor(x_new / width_per_note))
            self.start = self.resize_start_left + start_new
            c.place(x=self.start * width_per_note)

        # Redraw the size.
        self.width = int(width_per_note * (self.end - self.start + 1))
        self.widget.configure(width=self.width - 2 * highlight)

        self.draw_name()

    # Move the note range.
    def move(self, event):
        c, x, y, w, h, x_add, y_add, x_max, y_max = self.event_info(event)

        x_new = x - self.mouse_current_x + event.x
        note_set = round(x_new / width_per_note)

        # Determine the new note range
        note_diff = self.end - self.start
        self.start = note_set
        self.end = note_set + note_diff

        # Redraw
        c.place(x=self.start * width_per_note)

    # # REAPER communication # #
    def update_reaper(self):
        self.fx.params["Note range start"] = self.start / 127
        self.fx.params["Note range end"] = self.end / 127
        print(f"Updating REAPER:")
        print(f"  Set note range of {self.fx.name} to ({self.start}, {self.end})")


# # # Layered rendering. # # #

# The group class describes a selection of overlapping SamploRanges.
# It is used only for the `create_layers` functionality, which
# describes a way to render the SamploRanges without overlap.
class SamploGroup():
    def __init__(self):
        self.sranges = []
        self.start = float('inf')
        self.end = -float('inf')
        self.layers = None

    def add(self, srange):
        self.sranges.append(srange)
        self.start = min(self.start, srange.start)
        self.end = max(self.end, srange.end)

    def remove(self, srange):
        try:
            self.sranges.remove(srange)
        except:
            pass

        if len(self.sranges) > 0:
            self.start = min(x.start for x in self.sranges)
            self.end = max(x.end for x in self.sranges)

    # Determines valid subgroups in the group, and returns them.
    # Should always be called after `remove` has been called.
    def split(self):
        groups_split = []

        for srange in self.sranges:
            insert_in_groups(groups_split, srange, False)

        return groups_split

    def merge(self, group):
        self.sranges += group.sranges
        self.start = min(self.start, group.start)
        self.end = max(self.end, group.end)

    def intersect(self, srange):
        if srange.end < self.start:
            return False
        elif self.end < srange.start:
            return False
        return True

    def create_layers(self):
        self.layers = []

        self.sranges.sort(key=lambda x: x.start)
        group_todo = list(self.sranges)

        # Keep creating ranges until no ranges are left.
        while group_todo:
            layer = [group_todo[0]]
            group_todo = group_todo[1:]

            # Create a layer of non-overlapping (but as close together
            # as possible) closest ranges. And remove the added ranges
            # from the todo list.
            for srange in list(group_todo):
                if srange.start > layer[-1].end:
                    layer.append(srange)
                    group_todo.remove(srange)

            self.layers.append(layer)

    def get_layer(self, srange):
        for n, layer in enumerate(self.layers):
            if srange in layer:
                return n
        return -1

    def update_srange_layers(self):
        self.create_layers()
        for srange in self.sranges:
            srange.render_group = self
            srange.layer_count = len(self.layers)
            srange.layer = self.get_layer(srange)
            srange.redraw()


def insert_in_groups(groups, srange, update_srange=True):
    intersect = False

    # Try to insert into any of the existing groups.
    for group in groups:
        if group.intersect(srange):
            group.add(srange)
            intersect = True

            if update_srange:
                srange.render_group = group
            break

    # Create new group if necessary.
    if not intersect:
        group_new = SamploGroup()
        group_new.add(srange)
        groups.append(group_new)

        if update_srange:
            srange.render_group = group_new


# The logic for updating the groups after updating the position
# of the specified SamploRange. It has the following steps:
#  (1) First, the range is removed from the current group
#  (2) This potentially splits the group, which is done in the
#      first section.
#  (3) Then the range is reinserted.
#  (4) Finally, it merges all groups that overlap with the (new)
#      group of the range
def move_through_groups(groups, srange):
    assert srange.render_group is None or srange.render_group in groups

    # Remove from the current group, split the group if necessary.
    if srange.render_group:
        srange.render_group.remove(srange)

        if len(srange.render_group.sranges) == 0:
            # Remove if the group is empty.
            groups.remove(srange.render_group)
        else:
            # Split into new groups if necessary.
            groups_split = srange.render_group.split()
            if len(groups_split) > 1:
                groups.remove(srange.render_group)
                groups += groups_split

                # Update the layer information in the sranges.
                for group in groups_split:
                    group.update_srange_layers()
            else:
                srange.render_group.update_srange_layers()

    srange.render_group = None

    # Insert into groups again.
    if not srange.render_group:
        insert_in_groups(groups, srange)

    assert srange.render_group != None

    # Merge groups if necessary.
    for group in list(groups):
        if group == srange.render_group:
            continue

        # Merge if the groups overlap.
        if group.intersect(srange.render_group):
            group.merge(srange.render_group)

            groups.remove(srange.render_group)

            # Update all references.
            for s in srange.render_group.sranges:
                s.render_group = group

    # Update the layer information in the sranges.
    srange.render_group.update_srange_layers()


# # # Setup functions # # #

# Add new ReaSamplOmatic5000 instance.
def setup(track, note_start = -1, note_end = -1):
    global current_track, samplomatics, window, last_touched

    # The default note ranges.
    if note_start == -1 and last_touched:
        note_start = last_touched.end + 1
    elif note_start == -1:
        note_start = 60
    if note_end == -1:
        note_end = note_start

    samplomatic = track.add_fx("ReaSamplomatic5000")
    samplomatic.params["Obey note-offs"] = obey_note_offs.get()
    samplomatic.params["Gain for minimum velocity"] = gain_for_minimum_velocity
    samplomatic.params["Note range start"] = note_start / 127
    samplomatic.params["Note range end"] = note_end / 127

    if track == current_track:
        samplorange = SamploRange(window, samplomatic, track.color)
        samplomatics.append(samplorange)
        last_touched = samplorange

        global render_groups
        move_through_groups(render_groups, samplorange)

# If no track is selected, create a new one. Then add new ReaSamplOmatic5000
# instances to all selected tracks.
def init():
    project = rp.Project()

    # Set all selected tracks. Of none are selected, create a new one.
    tracks = project.selected_tracks
    if len(tracks) == 0:
        tracks = [project.add_track()]
        tracks[0].name = "Multi-Sampler"
        tracks[0].select()

    for track in tracks:
        setup(track)


# # # Separate functionality # # #

# Helper function for below.
def separate_next_samplomatic(track, bus):
    global create_bus_on_separate
    project = rp.Project()
    for fx in track.fxs:
        if is_samplomatic(fx):
            index_add = 1 if not bus else 2
            track_new = project.add_track(index=track.index+index_add,
                                          name=f"{fx.name}")
            send = track.add_send(track_new)

            if create_bus_on_separate.get():
                # Select the track.
                track_new.select()

            # Move the fx to the tracks.
            fx.move_to_track(track_new)
            return True
    return False


# Split the ReaSamplOmatic5000 instances over separate tracks.
# If 'create bus' is ticked, put them in a folder too.
def separate():
    global root, current_track
    if not current_track:
        return

    track_name_text.set("   separating...   ")
    root.after(100, separate_samplomatics)

def separate_samplomatics():
    global current_track, create_bus_on_separate
    project = rp.Project()


    bus = None
    if create_bus_on_separate.get():
        # Clear the selection for folder creation.
        project.unselect_all_tracks()

        # Add a bus track.
        bus = project.add_track(index=current_track.index+1,
                                name=f"bus - {current_track.name}")
        bus.select()

    # Create the tracks for all SamplOmatics.
    while separate_next_samplomatic(current_track, bus):
        pass

    # Create the folder.
    if create_bus_on_separate.get():
        try:
            project.perform_action(rp.reascript_api.NamedCommandLookup("_SWS_MAKEFOLDER"))

            # Go back to selecting the original track.
            project.unselect_all_tracks()
            current_track.select()
        except:
            print("Install the SWS extension for automatic folder creation")

    parse_current()


# # # Track parsing # # #

# Return true if the given fx is a ReaSamplOmatic instance.
# TODO: make this try/except more efficient
#       how(?)
def is_samplomatic(fx):
    try:
        fx.params["Note range start"]
        fx.params["Note range end"]
        return True
    except Exception as e:
        return False

# Recursively parse all ReaSamplOmatic5000 on the given track
# and all of its recursive MIDI sends.
def parse(track, recursion_depth=max_recursion_depth):
    global window, samplomatics, render_groups

    if recursion_depth == max_recursion_depth:
        print("Start parsing track...")

        # Remove the previous track info.
        for r in samplomatics:
            r.widget.destroy();
        samplomatics = []
        render_groups = []
    if recursion_depth == 0:
        return

    project = rp.Project()

    # Parse the send tracks recursively.
    for send in track.sends:
        if not send.midi_dest == (-1, -1):
            print("  Parsing send track:", send.dest_track.name)
            parse(send.dest_track, recursion_depth - 1)

    # Create Range elements for all Samplomatics on the track.
    fxs = track.fxs
    for fx in fxs:
        print("    Parsing FX:", fx.name)

        if is_samplomatic(fx):
            srange = SamploRange(window, fx, track.color)
            samplomatics.append(srange)

            # Add to the render groups.
            move_through_groups(render_groups, srange)

    if recursion_depth == max_recursion_depth:
        print("Done!")


# Call `parse` on the currently selected track.
def parse_current():
    global root, current_track, track_name_text
    if current_track:
        track_name_text.set("   parsing tracks...   ")
        root.after(100, lambda: parse(current_track))
        root.after(200, lambda: track_name_text.set(current_track.name))
    else:
        track_name_text.set("")


# Check if the selection has changed, and loop.
def check_selected():
    project = rp.Project()
    tracks = project.selected_tracks
    global current_track, samplomatics, track_name_text

    if not freeze.get():
        if len(tracks) == 1 and current_track != tracks[0]:
            current_track = tracks[0]
            track_name_text.set(str(current_track.name).strip())

            parse_current()

        if len(tracks) == 0:
            current_track = None
            track_name_text.set("")

            # Remove the previous track info.
            for r in samplomatics:
                r.widget.destroy();
            samplomatics = []
            render_groups = []

    global root
    root.after(500, check_selected)

    # rp.defer(loop)
    # loop()


# # # Event handling # # #

# After resizing the window, all note sizes should be updated, which
# this function does. (The rest is done automatically by tkinter.)
def resize(event, canvas, window_id):
    global sampomatics, window
    canvas.itemconfigure(window_id, height=canvas.winfo_height())

    # Resize all notes
    for samplerange in samplomatics:
        samplerange.redraw()


# Zoom the note sizes. Update the piano roll and SamploRanges.
# Also try to keep the zoom centered.
# (this does not look very smooth, maybe it can be improved)
def zoom(zoom):
    global width_per_note

    # Set the new size
    width_per_note_old = width_per_note
    width_per_note += zoom
    width_per_note = max(5, width_per_note)

    # Update the sizes
    global pianoroll_frame, samplomatics
    for samplorange in samplomatics:
        samplorange.redraw()
    for note_widget in pianoroll_frame.winfo_children():
        note_widget.configure(width=width_per_note - 2 - 2 * highlight)

    # Move the canvas view
    global canvas, scrollbar
    scroll_pos = canvas.xview()[0] * 128 * width_per_note_old
    x_pos_before = top_level_window.winfo_pointerx() - root.winfo_rootx() + scroll_pos
    x_pos_before = (x_pos_before // width_per_note_old) * width_per_note_old
    x_pos_after = x_pos_before + (x_pos_before / width_per_note_old) * zoom

    canvas.configure(xscrollincrement=1)
    canvas.xview_scroll(round(x_pos_after - x_pos_before), "units")
    canvas.configure(xscrollincrement=0)

# Zoom the pianoroll view.
def zoom_pianoroll(zoom):
    global piano_roll_height, pianoroll_frame, samplomatics

    piano_roll_height += zoom
    piano_roll_height = max(5, piano_roll_height)

    for samplorange in samplomatics:
        samplorange.redraw()
    for note_widget in pianoroll_frame.winfo_children():
        note_widget.configure(height=piano_roll_height - 2 - 2 * highlight)


# # # MIDI routing # # #

# Send the MIDI note on the selected MIDI channel.
def play_note(note, on, event=None):
    global midi_available
    if not midi_available:
        return

    msg = None
    if on:
        msg = mido.Message('note_on', note=note,
                velocity=int(event.y / piano_roll_height * 128))
    else:
        msg = mido.Message('note_off', note=note)

    port.send(msg)

# Setup the MIDI connection.
def setup_midi():
    global port, midi_available

    try:
        import mido
        midi_available = True
    except:
        print("Install mido and rtmidi for MIDI support.")
        midi_available = False
        return

    port_names = mido.get_output_names()
    port_name = ""

    if len(port_names) == 0:
        print("No MIDI available. Did you install rtmidi?")
        midi_available = False
        return

    for name in port_names:
        if midi_port_name.lower() in name.lower():
            port_name = name
            break
    if not port_name:
        port_name = port_names[0]

    port = mido.open_output(port_name)


# # # GUI setup # # #

# The main GUI construction function.
def guimain():
    global top_level_window, root, window, canvas, scrollbar, pixel, track_name_text, fullscreen

    # Create the root window
    root = tk.Frame(top_level_window)
    root.pack(side="top", fill="both", expand=True)

    # Create the buttons.
    buttons = tk.Frame(root)
    buttons.pack(side="top", anchor="nw")

    btn_init = tk.Button(buttons, text="Add", width=6, height=1, command=init)
    btn_init.grid(column=0, row=0, padx=4, pady=4)

    btn_refresh = tk.Button(buttons, text="Refresh", width=6, height=1, command=parse_current)
    btn_refresh.grid(column=1, row=0, padx=4, pady=4)

    btn_refresh = tk.Button(buttons, text="Separate", width=6, height=1, command=separate)
    btn_refresh.grid(column=2, row=0, padx=4, pady=4)

    btn_zoom_in  = tk.Button(buttons, text="+", width=1, height=1, command=lambda: zoom(1))
    btn_zoom_out = tk.Button(buttons, text="-", width=1, height=1, command=lambda: zoom(-1))
    btn_zoom_in.grid(column=3, row=0, padx=4, pady=4)
    btn_zoom_out.grid(column=4, row=0, padx=4, pady=4)

    # Create the checkboxes.
    global obey_note_offs, create_bus_on_separate, freeze
    obey_note_offs = tk.IntVar(value=obey_note_offs)
    create_bus_on_separate = tk.IntVar(value=create_bus_on_separate)
    freeze = tk.IntVar()
    check_obey_noteoffs = tk.Checkbutton(buttons, text='Obey note-offs',
                                         var=obey_note_offs,
                                         highlightthickness=0,
                                         fg='gray')
    check_create_bus =    tk.Checkbutton(buttons, text='Create bus',
                                         var=create_bus_on_separate,
                                          highlightthickness=0,
                                         fg='gray')
    check_freeze =        tk.Checkbutton(buttons, text='Feeze',
                                         var=freeze,
                                         highlightthickness=0,
                                         fg='gray')
    check_obey_noteoffs.grid(column=5, row=0, padx=4, pady=4)
    check_create_bus.grid(column=6, row=0, padx=4, pady=4)
    check_freeze.grid(column=7, row=0, padx=4, pady=4)


    # Create the track label
    track_name_text = tk.StringVar()
    track_name_label = tk.Label(buttons, textvariable=track_name_text, anchor='w')
    track_name_label.grid(column=0, row=1, columnspan=8, sticky='W')
    track_name_text.set("")

    # Create the internal level, were we will draw everything
    container = tk.Frame(root, highlightthickness=0)
    canvas = tk.Canvas(container, highlightthickness=0)

    scrollbar = tk.Scrollbar(container, orient="horizontal", command=canvas.xview)
    window = tk.Frame(canvas)

    window_id = canvas.create_window((0, 0), window=window, anchor="nw")
    canvas['xscrollcommand'] = scrollbar.set

    # Create the pianoroll
    gui_pianoroll()

    # Button mapping
    canvas.bind_all("<r>", lambda e: parse_current())
    canvas.bind_all("<s>", lambda e: separate())
    canvas.bind_all("<a>", lambda e: init())
    canvas.bind_all("<c>", lambda e, c=canvas: c.xview_moveto(36/128))

    # Resizing
    window.bind("<Configure>", lambda e, c=canvas: c.configure(scrollregion=c.bbox("all")))
    top_level_window.bind("<Configure>", lambda e, c=canvas, fid=window_id: resize(e, c, fid))

    # Scrolling with middle mouse button (doesn't seem to work very well though)
    window.bind_all("<ButtonPress-2>", lambda e, c=canvas: c.scan_mark(e.x, e.y))
    window.bind_all("<B2-Motion>", lambda e, c=canvas: c.scan_dragto(e.x, 0, gain=1))

    # Scrolling
    scroll_windows = lambda e, c=canvas: canvas.xview_scroll(int(-e.delta/abs(e.delta)*scroll_speed) , "units")
    scroll_linux = lambda direction, c=canvas: canvas.xview_scroll(direction*scroll_speed, "units")
    canvas.bind_all("<MouseWheel>", scroll_windows, add=True)
    canvas.bind_all("<Button-4>", lambda e, d=-1: scroll_linux(d), add=True)
    canvas.bind_all("<Button-5>", lambda e, d=1: scroll_linux(d), add=True)

    # Zooming (canvas)
    zoom_windows = lambda e: zoom(int(-e.delta/abs(e.delta)*zoom_speed))
    zoom_linux = lambda direction: zoom(direction*zoom_speed)
    canvas.bind_all("<Control-MouseWheel>", zoom_windows, add=True)
    canvas.bind_all("<Control-Button-4>", lambda e, d=-1: zoom_linux(d), add=True)
    canvas.bind_all("<Control-Button-5>", lambda e, d=1: zoom_linux(d), add=True)

    # Zooming (pianoroll)
    zoom_pianoroll_windows = lambda e: zoom_pianoroll(int(-e.delta/abs(e.delta)*zoom_speed))
    zoom_pianoroll_linux = lambda direction: zoom_pianoroll(direction*zoom_speed)
    canvas.bind_all("<Alt-MouseWheel>", zoom_pianoroll_windows, add=True)
    canvas.bind_all("<Alt-Button-4>", lambda e, d=-1: zoom_pianoroll_linux(d), add=True)
    canvas.bind_all("<Alt-Button-5>", lambda e, d=1: zoom_pianoroll_linux(d), add=True)

    # Packing
    container.pack(side="bottom", fill="both", expand=True)
    scrollbar.pack(side="bottom", fill="x")
    canvas.pack(side="top", fill="both", expand=True)

    # Start the loop
    root.after(500, check_selected)
    root.after(10, lambda c=canvas: c.xview_moveto(36/128)) # Scroll the view to C2
    root.mainloop()


# Create the pianoroll GUI.
def gui_pianoroll():
    global pixel, window, pianoroll_frame

    w = width_per_note - 2 - 2 * highlight # (Tkinter's sizes are not exact)
    h = piano_roll_height - 2 - 2 * highlight

    pianoroll_frame = tk.Frame(window)
    pianoroll_frame.pack(anchor = "w", side=tk.BOTTOM)

    octaves = 10
    for note in range(128):
        black = (note % 12) in [1,3,6,8,10]
        color = 'black' if black else 'white'
        fg_color = 'white' if black else 'black'
        select_color = 'gray' if black else 'lightgray'
        note_button = tk.Button(pianoroll_frame,
                image=pixel,
                text=f"C{note//12-1}" if note % 12 == 0 else " ",
                width=w, height=h,
                padx=0, pady=0,
                highlightthickness=highlight,
                activebackground=select_color,
                bd=0,
                bg=color,
                fg=fg_color,
                command=lambda i=note: play_note(i, False),
                compound="c")
        note_button.grid(column=note, row=0)
        note_button.bind("<Button-1>", lambda e, i=note: play_note(i, True, e))


# # # Main # # #

if __name__ == "__main__":
    # Setup midi
    setup_midi()

    # Create the top level window.
    top_level_window = tk.Tk(className='samplomatic5000 multi')
    top_level_window.geometry(default_window_size)
    top_level_window.tk_setPalette(background=background_color,
                                   foreground=foreground_color,
                                   highlightBackground=highlight_color)

    # Create the virtual pixel
    pixel = tk.PhotoImage(width=1, height=1)

    # Setup the GUI.
    guimain()

    # rp.at_exit(close)

