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
highlight = 0            # Thickness of the highlights. Set to 0 for a "flat" look.
				 # Always set to 0 on Windows.
alpha = 0.7              # Alpha of the track colors.
                         # 0.2 looks nice with a dark background.
text_color = 'lightgray' # Text color of the sample ranges.
                         # Change to 'black' when using light colors.
background = "#202020"   # Background color.
foreground = "#F0F0F0" 	 # Foreground color.
				 # Interchange the colors for light theme.

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

# Constants
total_notes = 128

def rgb(rgb, a = 1):
    return "#%02x%02x%02x" % (int(rgb[0]*a), int(rgb[1]*a), int(rgb[2]*a))

class SamploRange():
    def __init__(self, window, fx, color=(255, 255, 255)):
        self.window = window
        self.project = rp.Project()
        self.index = fx.index
        self.fx = fx

        self.start = round(fx.params["Note range start"] * 127)
        self.end = round(fx.params["Note range end"] * 127)

        # Create the moveable widget
        global alpha
        font = tkfont.Font(size=8)
        widget = tk.Canvas(self.window,
                           highlightthickness=highlight,
                           highlightbackground=rgb(color),
                           bg=rgb(color, alpha),
                           bd=0)
        widget.bind("<B1-Motion>", self.mouse)
        widget.bind("<ButtonRelease-1>", self.button_release)
        widget.bind("<Motion>", self.motion)

        # Create the background image.
        self.text_hor = None
        self.text_ver = None
        self.widget = widget
        self.redraw()

        self.mouse_start_x = 0
        self.mouse_start_y = 0
        self.mouse_current_x = 0
        self.mouse_current_y = 0

        self.in_motion = False
        self.resize_side = 0
        self.resize_start_left = 0

    def set_height(self, window_height):
        height = int(window_height - piano_roll_height)
        self.widget.configure(height=height - 2 * highlight)

    def redraw(self):
        # Position and sizes
        x_pos = int(width_per_note * self.start)
        width = int(width_per_note * (self.end - self.start + 1))
        height = int(window.winfo_height() - piano_roll_height)

        # Drawing
        self.widget.place(x=x_pos, y=0)
        self.widget.configure(width=width - 2 * highlight,
                              height=height - 2 * highlight)

        self.draw_name()

    def draw_name(self):
        offscreen = -50

        # Initialise the text (horizontally)
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
            # Place text vertically
            self.widget.moveto(self.text_hor, 0, offscreen)
            self.widget.moveto(self.text_ver, 0, 2)
        else:
            # Place text horizontally
            self.widget.moveto(self.text_hor, 3, 0)
            self.widget.moveto(self.text_ver, offscreen, 0)


    def motion(self, event):
        self.mouse_current_x = event.x
        self.mouse_current_y = event.y

    def button_release(self, event):
        self.fx.open_ui()
        # TODO(?): close others windows in REAPER

        self.in_motion = False
        self.resize_side = 0
        self.update_reaper()
        self.resize_start_left = 0

        global last_touched
        last_touched = self


    def event_info(self, event):
        c = event.widget
        x, y = c.winfo_x(), c.winfo_y()
        w, h = c.winfo_width(), c.winfo_height()
        x_add, y_add = event.x, event.y
        x_max, y_max = self.window.winfo_width(), self.window.winfo_height()
        return c, x, y, w, h, x_add, y_add, x_max, y_max

    def mouse(self, event):
        c, x, y, w, h, x_add, y_add, x_max, y_max = self.event_info(event)

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

    # Resize the note range
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
            print(self.end, self.end - self.resize_start_left, math.floor(x_new / width_per_note))
            start_new = min(self.end - self.resize_start_left, math.floor(x_new / width_per_note))
            self.start = self.resize_start_left + start_new
            c.place(x=self.start * width_per_note)

        # Redraw the size.
        self.width = int(width_per_note * (self.end - self.start + 1))
        self.widget.configure(width=self.width - 2 * highlight)

        self.draw_name()

    # Move the note range
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

    def update_reaper(self):
        print("update REAPER:", self.start, self.end)
        self.fx.params["Note range start"] = self.start / 127
        self.fx.params["Note range end"] = self.end / 127


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
            print("Install the SWS extension (with Python API) for automatic folder creation")


def init():
    project = rp.Project()

    # Set all selected tracks. Of none are selected, create a new one.
    tracks = project.selected_tracks
    if len(tracks) == 0:
        tracks = [project.add_track()]
        tracks[0].name = "Multi-Sampler"

    for track in tracks:
        setup(track)


def close():
    global root
    root.destroy()


def is_samplomatic(fx):
    # TODO: make this try/except more efficient
    #       how(?)
    try:
        fx.params["Note range start"]
        fx.params["Note range end"]
        return True
    except Exception as e:
        return False

def parse(track, recursion_depth=max_recursion_depth):
    global window, samplomatics

    if recursion_depth == max_recursion_depth:
        print("Start parsing track...")

        # Remove the previous track info.
        for r in samplomatics:
            r.widget.destroy();
        samplomatics = []
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
            samplomatics.append(SamploRange(window, fx, track.color))

    if recursion_depth == max_recursion_depth:
        print("Done!")


def parse_current():
    global current_track, track_name_text
    if current_track:
        track_name_text.set(str(current_track.name).strip())
        parse(current_track)
    else:
        track_name_text.set("")

def resize(event, canvas, window_id):
    global sampomatics, window
    canvas.itemconfigure(window_id, height=canvas.winfo_height())

    # Resize all notes
    for samplerange in samplomatics:
        samplerange.set_height(canvas.winfo_height())

def check_selected():
    project = rp.Project()
    tracks = project.selected_tracks
    global current_track, samplomatics, track_name_text

    if not freeze.get():
        if len(tracks) == 1 and current_track != tracks[0]:
            current_track = tracks[0]
            track_name_text.set(str(current_track.name).strip())

            parse(current_track)

        if len(tracks) == 0:
            current_track = None
            track_name_text.set("")


    # rp.defer(loop)
    # loop()
    global root
    root.after(500, check_selected)


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

def zoom_pianoroll(zoom):
    global piano_roll_height, pianoroll_frame, samplomatics

    piano_roll_height += zoom
    piano_roll_height = max(5, piano_roll_height)

    for samplorange in samplomatics:
        samplorange.redraw()
    for note_widget in pianoroll_frame.winfo_children():
        note_widget.configure(height=piano_roll_height - 2 - 2 * highlight)

def guimain():
    global top_level_window, root, window, canvas, scrollbar, pixel, track_name_text

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

    btn_refresh = tk.Button(buttons, text="Separate", width=6, height=1, command=separate_samplomatics)
    btn_refresh.grid(column=2, row=0, padx=4, pady=4)

    btn_zoom_in  = tk.Button(buttons, text="+", width=1, height=1, command=lambda: zoom(1))
    btn_zoom_out = tk.Button(buttons, text="-", width=1, height=1, command=lambda: zoom(-1))
    btn_zoom_in.grid(column=3, row=0, padx=4, pady=4)
    btn_zoom_out.grid(column=4, row=0, padx=4, pady=4)

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


    track_name_text = tk.StringVar()
    track_name_label = tk.Label(buttons, textvariable=track_name_text, anchor='w')
    track_name_label.grid(column=0, row=1, columnspan=7, sticky='W')
    track_name_text.set("")

    # Create the internal level, were we will draw everything
    container = tk.Frame(root, highlightthickness=0)
    canvas = tk.Canvas(container, highlightthickness=0)

    scrollbar = tk.Scrollbar(container, orient="horizontal", command=canvas.xview)
    window = tk.Frame(canvas)

    window_id = canvas.create_window((0, 0), window=window, anchor="nw")
    canvas.configure(xscrollcommand=scrollbar.set, yscrollcommand=scrollbar.set)

    # Create the pianoroll
    gui_pianoroll()

    # Button mapping
    canvas.bind_all("<r>", lambda e: parse_current())
    canvas.bind_all("<s>", lambda e: separate_samplomatics())
    canvas.bind_all("<a>", lambda e: init())
    canvas.bind_all("<c>", lambda e, c=canvas: c.xview_moveto(36/128))

    # Resizing
    window.bind("<Configure>", lambda e, c=canvas: c.configure(scrollregion=c.bbox("all")))
    canvas.bind("<Configure>", lambda e, c=canvas, fid=window_id: resize(e, c, fid))

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

if __name__ == "__main__":
    # Setup midi
    setup_midi()

    # Create the top level window.
    top_level_window = tk.Tk(className='samplomatic5000 multi')
    top_level_window.geometry(default_window_size)
    top_level_window.tk_setPalette(background=background, foreground=foreground)

    # Create the virtual pixel
    pixel = tk.PhotoImage(width=1, height=1)

    # Setup the GUI.
    guimain()

    # rp.at_exit(close)
