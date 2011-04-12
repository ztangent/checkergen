"""Contains core functionality of checkergen.

Errors and Exceptions:
FileFormatError
FrameOverflowError

Classes:
CkgProj -- A checkergen project, contains settings and CkgDisplayGroups.
CkgExp -- A checkergen experiment, describes how a projet is displayed.
CkgDisplayGroup -- A set of CheckerShapes to be displayed simultaneously.
CheckerShapes -- Abstract checkered shape class
CheckerBoard -- A (distorted) checkerboard pattern, can color-flip.

"""

import os
import sys
import re
import csv
import random
import itertools
from xml.dom import minidom

import pyglet

import graphics
import trigger
import eyetracking
from utils import *

# Use OrderedDict substitute if we don't have Python 2.7
if sys.version_info < (2, 7):
    from odict import OrderedDict
else:
    from collections import OrderedDict

CKG_FMT = 'ckg'
EXP_FMT = 'ckx'
LOG_FMT = 'log'
XML_NAMESPACE = 'http://github.com/ZOMGxuan/checkergen'
MAX_EXPORT_FRAMES = 100000
PRERENDER_TO_TEXTURE = False
INT_HALF_PERIODS = True
EXPORT_FMTS = ['png']
EXPORT_DIR_SUFFIX = '-anim'
FIX_POS = (0, 0)
FIX_RANGE = (20, 20)
FIX_PER = 350
SANS_SERIF = ('Helvetica', 'Arial', 'FreeSans')

def xml_get(parent, namespace, name, index=0):
    """Returns concatenated text node values inside an element."""
    element = [node for node in parent.childNodes if
               node.localName == name and 
               node.namespaceURI == namespace][index]
    strings = []
    for node in element.childNodes:
        if node.nodeType == node.TEXT_NODE:
            strings.append(node.data)
    return ''.join(strings)

def xml_set(document, parent, name, string):
    """Stores value as a text node in a new DOM element."""
    element = document.createElement(name)
    parent.appendChild(element)
    text = document.createTextNode(string)
    element.appendChild(text)

def xml_pretty_print(document, indent):
    """Hack to prettify minidom's not so pretty print."""
    ugly_xml = document.toprettyxml(indent=indent)
    prettifier_re = re.compile('>\n\s+([^<>\s].*?)\n\s+</',
                               re.DOTALL)    
    pretty_xml = prettifier_re.sub('>\g<1></', ugly_xml)
    return pretty_xml

class FileFormatError(ValueError):
    """Raised when correct file format/extension is not supplied."""
    pass

class FrameOverflowError(Exception):
    """Raised when more than MAX_EXPORT_FRAMES are going to be exported."""
    pass
        
class CkgProj:
    """Defines a checkergen project, with checkerboards and other settings."""

    DEFAULTS = OrderedDict([('name', 'untitled'),
                            ('fps',  60),
                            ('res',  (800, 600)),
                            ('bg',  (127, 127, 127)),
                            ('export_fmt',  'png'),
                            ('pre',  0),
                            ('post',  0),
                            ('cross_cols',  ((0, 0, 0), (255, 0, 0))),
                            ('cross_times',  ('Infinity', 1)),
                            ('orders', []),
                            ('disp_ops', None)])

    DEFAULTS['disp_ops'] = OrderedDict([('fullscreen', False),
                                        ('priority', 0),
                                        ('logtime', False),
                                        ('logdur', False),
                                        ('trigser', False),
                                        ('trigpar', False),
                                        ('fpst', 0),
                                        ('phototest', False),
                                        ('photoburst', False),
                                        ('eyetrack', False),
                                        ('etuser', False),
                                        ('etvideo', None),
                                        ('tryagain', 0),
                                        ('trybreak', None)])

    def __init__(self, **keywords):
        """Initializes a new project, or loads it from a path.

        path -- if specified, ignore other arguments and load project 
        from path
        
        name -- name of the project, always the same as the 
        filename without the extension

        fps -- frames per second of the animation to be displayed

        res -- screen resolution / window size at which project 
        will be displayed

        bg -- background color of the animation as a 3-tuple (R, G, B)

        export_fmt -- image format for animation to be exported as

        pre -- time in seconds a blank screen will be shown before any
        display groups

        post --time in seconds a blank screen will be shown after any
        display groups

        """
        if 'path' in keywords.keys():
            self.load(keywords['path'])
            return
        for kw in self.__class__.DEFAULTS.keys():
            if kw in keywords.keys():
                setattr(self, kw, keywords[kw])
            else:
                setattr(self, kw, self.__class__.DEFAULTS[kw])
        self.groups = []

    def __setattr__(self, name, value):
        # Type conversions
        if name == 'name':
            value = str(value)
        elif name in ['fps', 'pre', 'post']:
            value = to_decimal(value)
        elif name == 'res':
            if len(value) != 2:
                raise ValueError
            value = tuple([int(v) for v in value])
        elif name == 'bg':
            if len(value) != 3:
                raise ValueError
            value = tuple([int(v) for v in value])
        elif name == 'export_fmt':
            if value not in EXPORT_FMTS:
                msg = 'image format not recognized or supported'
                raise FileFormatError(msg)
        elif name == 'cross_cols':
            if len(value) != 2:
                raise ValueError
            for col in value:
                if len(col) != 3:
                    raise ValueError
            value = tuple([tuple([int(c) for c in col]) for col in value])
        elif name == 'cross_times':
            if len(value) != 2:
                raise ValueError
            value = tuple([to_decimal(x) for x in value])

        # Store value
        self.__dict__[name] = value
        # Set dirty bit
        if name != '_dirty':
            self._dirty = True

    def add_group(self, group):
        """Append group to list and set dirty bit."""
        self.groups.append(group)
        self._dirty = True
        return self.groups.index(group)

    def del_group(self, group):
        """Remove group to list and set dirty bit."""
        self.groups.remove(group)
        self._dirty = True

    def add_shape_to_group(self, group, shape):
        """Add shape to group specified by id and set dirty bit."""
        if group not in self.groups:
            raise ValueError
        group.shapes.append(shape)
        self._dirty = True
        return group.shapes.index(shape)

    def del_shape_from_group(self, group, shape):
        """Removes shape from group specified by id and set dirty bit."""
        if group not in self.groups:
            raise ValueError
        group.shapes.remove(shape)
        self._dirty = True
   
    def set_group_attr(self, gid, name, value):
        """Set attribute of a group specified by id and set dirty bit."""
        setattr(self.groups[gid], name, value)
        self._dirty = True

    def set_shape_attr(self, group, sid, name, value):
        """Set attribute of a shape specified by id and set dirty bit."""
        if group not in self.groups:
            raise ValueError
        setattr(group.shapes[sid], name, value)
        self._dirty = True

    def is_dirty(self):
        return self._dirty

    def load(self, path):
        """Loads project from specified path."""

        # Get project name from filename
        name, ext = os.path.splitext(os.path.basename(path))
        if len(ext) == 0:
            path = '{0}.{1}'.format(path, CKG_FMT)                
        elif ext != '.{0}'.format(CKG_FMT):
            msg = "path lacks '.{0}' extension".format(CKG_FMT)
            raise FileFormatError(msg)
        if not os.path.isfile(path):
            msg = "specified file does not exist"
            raise IOError(msg)
        self.name = name

        with open(path, 'r') as project_file:
            doc = minidom.parse(project_file)

        project = doc.documentElement
        # Vars that are dicts
        dicts_to_load = [var for var in self.__class__.DEFAULTS.keys() if
                         isinstance(self.__class__.DEFAULTS[var], dict)]
        # Vars that are not dicts
        vars_to_load = [var for var in self.__class__.DEFAULTS.keys() if not
                        isinstance(self.__class__.DEFAULTS[var], dict)]
        # Name is not stored in project file
        vars_to_load.remove('name')
        for var in vars_to_load:
            try:
                value = eval(xml_get(project, XML_NAMESPACE, var))
            except IndexError:
                print "warning: missing attribute '{0}'".format(var)
                value = self.__class__.DEFAULTS[var]
                print "using default value '{0}' instead...".format(value)
            setattr(self, var, value)
        for d_name in dicts_to_load:
            d = self.__class__.DEFAULTS[d_name]
            try:
                d_el = [node for node in project.childNodes if
                        node.localName == d_name and
                        node.namespaceURI == XML_NAMESPACE][0]
                for var in d.keys():
                    try:
                        d[var] = eval(xml_get(d_el, XML_NAMESPACE, var))
                    except IndexError:
                        print "warning: missing attribute '{0}' in '{1}'".\
                            format(var, d_name)
                        print "using default value '{0}' instead...".\
                            format(d[var])
            except IndexError:
                print "warning: missing attribute set '{0}'".format(d_name)
                print "using default values instead..."
            setattr(self, d_name, d)
        self.groups = []
        group_els = [node for node in project.childNodes if
                     node.localName == 'group' and
                     node.namespaceURI == XML_NAMESPACE]
        for group_el in group_els:
            new_group = CkgDisplayGroup()
            new_group.load(group_el)
            self.groups.append(new_group)

        self._dirty = False

    def save(self, path):
        """Saves project to specified path as an XML document."""

        self.name, ext = os.path.splitext(os.path.basename(path))
        if ext != '.{0}'.format(CKG_FMT):
            path = '{0}.{1}'.format(path, CKG_FMT)

        impl = minidom.getDOMImplementation()
        doc = impl.createDocument(XML_NAMESPACE, 'project', None)
        project = doc.documentElement
        # Hack below because minidom doesn't support namespaces properly
        project.setAttribute('xmlns', XML_NAMESPACE)
        # Vars that are dicts
        dicts_to_save = [var for var in self.__class__.DEFAULTS.keys() if
                         isinstance(self.__class__.DEFAULTS[var], dict)]
        # Vars that are not dicts
        vars_to_save = [var for var in self.__class__.DEFAULTS.keys() if not
                        isinstance(self.__class__.DEFAULTS[var], dict)]
        # Name is not stored in project file
        vars_to_save.remove('name')
        for var in vars_to_save:
            xml_set(doc, project, var, repr(getattr(self, var)))
        for d_name in dicts_to_save:
            d_el = doc.createElement(d_name)
            project.appendChild(d_el)
            d = getattr(self, d_name)
            for k, v in d.iteritems():
                xml_set(doc, d_el, k, repr(v))
        for group in self.groups:
            group.save(doc, project)
        with open(path, 'w') as project_file:
            project_file.write(xml_pretty_print(doc,indent='    '))

        self._dirty = False

        return path

    def display(self, fullscreen=False, logtime=False, logdur=False,
                trigser=False, trigpar=False, fpst=0,
                phototest=False, photoburst=False,
                eyetrack=False, etuser=False, etvideo=None,
                tryagain=0, trybreak=None, groupq=[], run=None):
        """Displays the project animation on the screen.

        fullscreen -- animation is displayed fullscreen if true, stretched
        to fit if necessary

        logtime -- timestamp of each frame is saved to a logfile if true

        logdur -- duration of each frame is saved to a logfile if true

        trigser -- send triggers through serial port when each group is shown

        trigpar -- send triggers through parallel port when each group is shown

        fpst -- flips per shape trigger, i.e. number of shape color reversals
        (flips) that occur for a unique trigger to be sent for that shape

        phototest -- draw white rectangle in topleft corner when each group is
        shown for photodiode to detect

        photoburst -- make checkerboards only draw first color for one frame

        eyetrack -- use eyetracking to ensure subject is fixating on cross

        etuser -- if true, user gets to select eyetracking video source in GUI
        
        etvideo -- optional eyetracking video source file to use instead of
        live feed

        tryagain -- Append groups during which subject failed to fixate up to
        this number of times to the group queue

        trybreak -- Append a wait screen to the group queue every time
        after this many groups have been appended to the queue
        
        groupq -- queue of groups to be displayed, defaults to order of
        groups in project (i.e. groups[0] first, etc.)

        run -- experimental run where logged variables are saved (i.e.
        fail_idlist and time information)

        """

        # Create fixation crosses
        fix_crosses = [graphics.Cross([r/2 for r in self.res],
                                      (20, 20), col = cross_col) 
                       for cross_col in self.cross_cols]
        # Create test rectangle
        if phototest:
            test_rect = graphics.Rect((0, self.res[1]), 
                                      [r/8 for r in self.res],
                                      anchor='topleft')

        # Set-up groups and variables that control their display
        if groupq == []:
            groupq = list(self.groups)
        n = -1
        flipped = 0
        flip_id = -1
        groups_duration = sum([group.duration() for group in groupq])
        groups_start = self.pre * self.fps
        groups_stop = (self.pre + groups_duration) * self.fps
        disp_end = (self.pre + groups_duration + self.post) * self.fps
        if groups_start == 0 and groups_stop > 0:
            groups_visible = True
        else:
            groups_visible = False
        count = 0

        # Initialize ports
        if trigser:
            if not trigger.available['serial']:
                msg = 'serial port functionality not available'
                raise NotImplementedError(msg)
        if trigpar:
            if not trigger.available['parallel']:
                msg = 'parallel port functionality not available'
                raise NotImplementedError(msg)
        trigger.init(trigser, trigpar)

        # Initialize eyetracking
        if eyetrack:
            if not eyetracking.available:
                msg = 'eyetracking functionality not available'
                raise NotImplementedError(msg)
            if trybreak == None:
                trybreak = len(self.groups)
            fixated = False
            old_fixated = False
            tracked = False
            old_tracked = False
            cur_fix_fail = False
            trycount = 0
            fail_idlist = []
            eyetracking.select_source(etuser, etvideo)
            eyetracking.start()
        
        # Stretch to fit screen only if project res does not equal screen res
        scaling = False
        if fullscreen:
            window = pyglet.window.Window(fullscreen=True, visible=False)
            if (window.width, window.height) != self.res:
                scaling = True
        else:
            window = pyglet.window.Window(*self.res, visible=False)            

        # Set up KeyStateHandler to handle keyboard input
        keystates = pyglet.window.key.KeyStateHandler()
        window.push_handlers(keystates)

        # Create framebuffer object for drawing unscaled scene
        if scaling:
            canvas = pyglet.image.Texture.create(*self.res)
            fbo = graphics.Framebuffer(canvas)
            fbo.start_render()
            graphics.set_clear_color(self.bg)
            fbo.clear()
            fbo.end_render()

        # Clear window and make visible
        window.switch_to()
        graphics.set_clear_color(self.bg)
        window.clear()
        window.set_visible()

        # Initialize logging variables
        if logtime:
            timestamps = []
            trigstamps = []
            timer = Timer()
            timer.start()
        if logdur:
            durstamps = []
            dur = Timer()
            dur.start()

        # Main loop
        while not window.has_exit and count < disp_end:
            # Clear canvas
            if scaling:
                fbo.start_render()
                fbo.clear()
            else:
                window.clear()

            # Assume no change to group visibility
            flipped = 0
 
            # Manage groups when they are on_screen
            if groups_visible:
                # Check whether group changes in visibility
                if n >= 0 and groupq[n].visible != groupq[n].old_visible:
                    flip_id = self.groups.index(groupq[n])
                    if groupq[n].visible:
                        flipped = 1
                    elif groupq[n].old_visible:
                        flipped = -1
                # Get next group from queue
                if n < 0 or groupq[n].over:
                    # Send special trigger if waitscreen ends
                    if isinstance(groupq[n], CkgWaitScreen):
                        trigger.CUR_STATE['user'] = 1
                    n += 1
                    if n >= len(groupq):
                        groups_visible = False
                        trigger.CUR_STATE['user'] = 0
                    else:
                        groupq[n].reset()
                        if eyetrack:
                            cur_fix_fail = False
                        if groupq[n].visible:
                            flip_id = self.groups.index(groupq[n])
                            flipped = 1
                        # Send special trigger when waitscreen ends
                        if isinstance(groupq[n], CkgWaitScreen):
                            trigger.CUR_STATE['user'] = 0
                # Draw and then update group
                if n >= 0:
                    groupq[n].draw(photoburst=photoburst)
                    groupq[n].update(fps=self.fps,
                                     fpst=fpst,
                                     keystates=keystates)

            # Send triggers upon group visibility change
            if flipped == 1:
                trigger.CUR_STATE['group'] = 1
                # Draw test rectangle
                if phototest:
                    test_rect.draw()
            elif flipped == -1:
                trigger.CUR_STATE['group'] = 0

            if eyetrack:
                # First check if eye is being tracked and send trigger
                old_tracked = tracked
                tracked = eyetracking.is_tracked()
                if tracked:
                    if not old_tracked:
                        # Send trigger if eye starts being tracked
                        trigger.set_track_start()
                else:
                    if old_tracked:
                        # Send trigger if eye stops being tracked
                        trigger.set_track_stop()

                # Next check for fixation
                old_fixated = fixated
                fixated = eyetracking.is_fixated(FIX_POS, FIX_RANGE, FIX_PER)
                if fixated:
                    # Draw normal cross color if fixating
                    fix_crosses[0].draw()
                    if not old_fixated:
                        # Send trigger if fixation starts
                        trigger.set_fix_start()
                else:
                    # Draw alternative cross color if not fixating
                    fix_crosses[1].draw()
                    if old_fixated:
                        # Send trigger if fixation stops
                        trigger.set_fix_stop()

                # Take note of which groups in which fixation failed
                if not cur_fix_fail and groupq[n].visible and\
                    (tracked and not fixated):
                    cur_fix_fail = True
                    # Append failed group to group queue
                    if trycount < tryagain:
                        # Insert waitscreen every trybreak failed groups
                        if trybreak > 0:
                            if len(fail_idlist) % trybreak == 0:
                                groupq.append(CkgWaitScreen())
                        groupq.append(groupq[n])
                        groups_stop += groupq[n].duration() * self.fps
                        disp_end += groupq[n].duration() * self.fps
                        trycount += 1
                    # Maintain list of failed IDs
                    fail_idlist.append(self.groups.index(groupq[n]))

            # Change cross color based on time if eyetracking is not enabled
            if not eyetrack:
                if (count % (sum(self.cross_times) * self.fps) 
                    < self.cross_times[0] * self.fps):
                    fix_crosses[0].draw()
                else:
                    fix_crosses[1].draw()                

            # Increment count and set whether groups should be shown
            if not isinstance(groupq[n], CkgWaitScreen):
                count += 1
            if groups_start <= count < groups_stop:
                groups_visible = True
            else:
                groups_visible = False

            # Blit canvas to screen if necessary
            if scaling:
                fbo.end_render()
                window.switch_to()
                canvas.blit(0, 0)
            window.dispatch_events()
            window.flip()
            # Make sure everything has been drawn
            pyglet.gl.glFinish()

            # Append time information to lists
            if logtime:
                timestamps.append(timer.elapsed())
            if logdur:
                durstamps.append(dur.restart())

            # Send trigger ASAP after flip
            trigger.send(trigser, trigpar)

            # Log when trigger are sent
            if logtime:
                if flipped != 0 and (trigser or trigpar):
                    trigstamps.append(trigger.STATE)
                else:
                    trigstamps.append('')

        # Clean up
        if eyetrack:
            eyetracking.stop()
        window.close()
        if scaling:
            fbo.delete()
            del canvas
        trigger.quit(trigser, trigpar)

        # Store variables in run object
        if run != None:
            if logtime:
                run.timestamps = timestamps
                run.trigstamps = trigstamps
            if logdur:
                run.durstamps = durstamps
            if eyetrack and len(fail_idlist) > 0:
                run.add_idlist = fail_idlist[:tryagain]
                run.fail_idlist = fail_idlist[tryagain:]

    def export(self, export_dir, export_duration, groupq=[],
               export_fmt=None, folder=True, force=False):
        if not os.path.isdir(export_dir):
                msg = 'export path is not a directory'
                raise IOError(msg)
        if export_fmt == None:
            export_fmt = self.export_fmt

        # Set-up groups and variables that control their display
        if groupq == []:
            groupq = list(self.groups)
        n = -1
        groups_duration = sum([group.duration() for group in groupq])
        groups_start = self.pre * self.fps
        groups_stop = (self.pre + groups_duration) * self.fps
        disp_end = (self.pre + groups_duration + self.post) * self.fps
        if groups_start == 0 and groups_stop > 0:
            groups_visible = True
        else:
            groups_visible = False
        count = 0

        # Limit export duration to display duration
        frames = export_duration * self.fps
        frames = min(frames, disp_end)

        # Warn user if a lot of frames will be exported
        if frames > MAX_EXPORT_FRAMES and not force:
            msg = 'very large number ({0}) of frames to be exported'.\
                format(frames)
            raise FrameOverflowError(msg)

        # Create folder to store images if necessary
        if folder:
            export_dir = os.path.join(export_dir,
                                      self.name + EXPORT_DIR_SUFFIX)
            if not os.path.isdir(export_dir):
                os.mkdir(export_dir)

        # Create fixation crosses
        fix_crosses = [graphics.Cross([r/2 for r in self.res],
                                      (20, 20), col = cross_col) 
                       for cross_col in self.cross_cols]

        # Set up canvas and framebuffer object
        canvas = pyglet.image.Texture.create(*self.res)
        fbo = graphics.Framebuffer(canvas)
        fbo.start_render()
        graphics.set_clear_color(self.bg)
        fbo.clear()

        # Main loop
        while count < frames:
            fbo.clear()

            if groups_visible:
                # Get next group from queue
                if n < 0 or groupq[n].over:
                    n += 1
                    if n >= len(groupq):
                        groups_visible = False
                    else:
                        groupq[n].reset()
                # Draw and then update group
                if n >= 0:
                    groupq[n].draw()
                    groupq[n].update(fps=self.fps, fpst=0)

            # Draw fixation cross based on current count
            if (count % (sum(self.cross_times) * self.fps) 
                < self.cross_times[0] * self.fps):
                fix_crosses[0].draw()
            else:
                fix_crosses[1].draw()                

            # Save current frame to file
            savepath = \
                os.path.join(export_dir, 
                             '{0}{2}.{1}'.
                             format(self.name, export_fmt,
                                    repr(count).zfill(numdigits(frames-1))))
            canvas.save(savepath)

            # Increment count and set whether groups should be shown
            count += 1
            if groups_start <= count < groups_stop:
                groups_visible = True
            else:
                groups_visible = False

        fbo.delete()

class CkgExp:

    DEFAULTS = {'name': None, 'proj' : None, 
                'blocks': 1, 'sequences': None,
                'flags': '--fullscreen --logtime --logdur'}

    def __init__(self, **keywords):
        """Create a checkergen experiment, which specifies how a project
        is to be displayed.

        path -- if specified, ignore other arguments and load project 
        from path

        name -- name of the experiment

        proj -- CkgProj that the experiment is to be created for

        blocks -- number of times the selected sequence of display groups
        will be shown in one run

        sequences -- list of possible display group id sequences, from which
        one sequence will be randomly  selected for display in a run,
        defaults to reduced latin square with side length equal to the number
        of display groups in the supplied CkgProj

        flags -- string passed to the display command as flags

        """
        if 'path' in keywords.keys():
            self.load(keywords['path'])
            return
        for kw in self.__class__.DEFAULTS.keys():
            if kw in keywords.keys():
                setattr(self, kw, keywords[kw])
            else:
                setattr(self, kw, self.__class__.DEFAULTS[kw])

        if self.name == None and self.proj != None:
            self.name = self.proj.name

        if self.sequences == None:
            if self.proj == None:
                msg = "either project or sequences have to be specified"
                raise ValueError(msg)
            else:
                self.gen_latin_square(len(self.proj.groups))

        del self.proj

    def gen_latin_square(self, n):
        """Set experiment sequences as a cyclic reduced latin square."""
        sequence = range(n)
        self.sequences = [[sequence[i - j] for i in range(n)] 
                          for j in range(n, 0, -1)]

    def random_run(self, name):
        """Choose random sequence, create run from it and return."""
        sequence = random.choice(self.sequences)
        run = CkgRun(name=name,
                     flags=self.flags,
                     blocks=self.blocks,
                     sequence=sequence)
        return run

    def save(self, path=None):
        """Saves experiment to specified path in the CSV format."""

        if path == None:
            path = os.path.join(os.getcwd(),
                                '{0}.{1}'.format(self.name, EXP_FMT))
        else:
            self.name, ext = os.path.splitext(os.path.basename(path))
            if ext != '.{0}'.format(EXP_FMT):
                path = '{0}.{1}'.format(path, EXP_FMT)

        with open(path, 'wb') as expfile:
            expwriter = csv.writer(expfile, dialect='excel-tab')
            expwriter.writerow(['checkergen experiment file'])
            expwriter.writerow(['flags:', self.flags])
            expwriter.writerow(['blocks:', self.blocks])
            expwriter.writerow(['sequences:'])
            for sequence in self.sequences:
                expwriter.writerow(sequence)

    def load(self, path):
        """Loads experiment from specified path."""

        # Get project name from filename
        name, ext = os.path.splitext(os.path.basename(path))
        if len(ext) == 0:
            path = '{0}.{1}'.format(path, EXP_FMT)                
        elif ext != '.{0}'.format(EXP_FMT):
            msg = "path lacks '.{0}' extension".format(EXP_FMT)
            raise FileFormatError(msg)
        if not os.path.isfile(path):
            msg = "specified file does not exist"
            raise IOError(msg)
        self.name = name

        self.sequences = []
        with open(path, 'rb') as expfile:
            expreader = csv.reader(expfile, dialect='excel-tab')
            for n, row in enumerate(expreader):
                if n == 1:
                    self.flags = row[1]
                elif n == 2:
                    self.blocks = int(row[1])
                elif n > 3:
                    sequence = [int(i) for i in row]
                    self.sequences.append(sequence)
 
class CkgRun:

    def __init__(self, name, flags, blocks, sequence):
        """Creates an experimental run."""
        self.name = name
        self.flags = flags
        self.blocks = blocks
        self.sequence = sequence
        self.add_idlist = None
        self.fail_idlist = None
        self.timestamps = []
        self.durstamps = []
        self.trigstamps = []

    def idlist(self):
        """Generate idlist from sequence and return it."""
        idlist = ([-1] + self.sequence) * self.blocks
        return idlist

    def write_log(self, path=None):
        """Write a log file for the experimental run in the CSV format."""

        if path == None:
            path = os.path.join(os.getcwd(),
                                '{0}.{1}'.format(self.name, LOG_FMT))
        else:
            self.name, ext = os.path.splitext(os.path.basename(path))
            if ext != '.{0}'.format(LOG_FMT):
                path = '{0}.{1}'.format(path, LOG_FMT)

        with open(path, 'wb') as runfile:
            runwriter = csv.writer(runfile, dialect='excel-tab')
            runwriter.writerow(['checkergen log file'])
            runwriter.writerow(['flags:', self.flags])
            runwriter.writerow(['blocks:', self.blocks])
            runwriter.writerow(['sequence:'] + self.sequence)
            if self.add_idlist != None:
                runwriter.writerow(['groups appended:'])
                rowlist = grouper(len(self.sequence), self.add_idlist, '')
                for row in rowlist:
                    runwriter.writerow(row)
            if self.fail_idlist != None:
                runwriter.writerow(['groups failed (not appended):'])
                rowlist = grouper(len(self.sequence), self.fail_idlist, '')
                for row in rowlist:
                    runwriter.writerow(row)
            stamps = [self.timestamps, self.durstamps, self.trigstamps]
            if len(max(stamps)) > 0:
                for l in stamps:
                    if len(l) == 0:
                        l = [''] * len(max(stamps))
                runwriter.writerow(['timestamps', 'durations', 'triggers'])
                for row in zip(*stamps):
                    runwriter.writerow(row)

class CkgDisplayGroup:

    DEFAULTS = OrderedDict([('pre',  0), ('disp',  'Infinity'), ('post',  0)])

    def __init__(self, **keywords):
        """Create a new group of shapes to be displayed together.

        pre -- time in seconds a blank screen is shown before
        shapes in group are displayed

        disp -- time in seconds the shapes in the group are displayed,
        negative numbers result in shapes being displayed forever

        post -- time in seconds a blank screen is shown after
        shapes in group are displayed

        """
        for kw in self.__class__.DEFAULTS.keys():
            if kw in keywords.keys():
                setattr(self, kw, keywords[kw])
            else:
                setattr(self, kw, self.__class__.DEFAULTS[kw])
        self.shapes = []
        self.reset()

    def __setattr__(self, name, value):
        if name in self.__class__.DEFAULTS:
            value = to_decimal(value)
        self.__dict__[name] = value

    def duration(self):
        """Returns total duration of display group."""
        return self.pre + self.disp + self.post

    def reset(self):
        """Resets internal count and all contained shapes."""
        self._count = 0
        self._start = self.pre
        self._stop = self.pre + self.disp
        self._end = self.pre + self.disp + self.post
        self.over = False
        self.old_visible = False
        if self._start == 0 and self._stop > 0:
            self.visible = True
        else:
            self.visible = False
            if self._end == 0:
                self.over = True
        self._flip_count = [0] * len(self.shapes)
        for shape in self.shapes:
            shape.reset()

    def draw(self, lazy=False, photoburst=False):
        """Draws all contained shapes during the appropriate interval."""
        if self.visible:
            for shape in self.shapes:
                if lazy:
                    shape.lazydraw()
                else:
                    shape.draw(photoburst=photoburst)

    def update(self, **keywords):
        """Increments internal count, makes group visible when appropriate.

        fps -- refresh rate of the display in frames per second

        fpst -- flips per shape trigger, i.e. number of shape color reversals
        (flips) that occur for a unique trigger to be sent for that shape

        """

        fps = keywords['fps']
        fpst = keywords['fpst']
                
        if self.visible:
            # Set triggers to be sent
            if fpst > 0:
                for n, shape in enumerate(self.shapes):
                    if shape.flipped:
                        self._flip_count[n] += 1
                    if self._flip_count[n] >= fpst:
                        trigger.CUR_STATE['shape'] = 1
                        trigger.CUR_STATE['sid'] = n
                        self._flip_count[n] = 0
            # Update contained shapes
            for shape in self.shapes:
                shape.update(fps)

        # Increment count and set flags for the next frame
        self._count += 1
        self.old_visible = self.visible
        if (self._start * fps) <= self._count < (self._stop * fps):
            self.visible = True
        else:
            self.visible = False
        if self._count >= (self._end * fps):
            self.over = True
        else:
            self.over = False

    def save(self, document, parent):
        """Saves group in specified XML document as child of parent."""
        group_el = document.createElement('group')
        parent.appendChild(group_el)
        for var in self.__class__.DEFAULTS.keys():
            xml_set(document, group_el, var,  repr(getattr(self, var)))
        for shape in self.shapes:
            shape.save(document, group_el)
          
    def load(self, element):
        """Loads group from XML DOM element."""
        for var in self.__class__.DEFAULTS.keys():
            try:
                value = eval(xml_get(element, XML_NAMESPACE, var))
            except IndexError:
                print "warning: missing attribute '{0}'".format(var)
                value = self.__class__.DEFAULTS[var]
                print "using default value '{0}' instead...".format(value)
            setattr(self, var, value)
        shape_els = [node for node in element.childNodes if
                     node.localName == 'shape' and
                     node.namespaceURI == XML_NAMESPACE]
        for shape_el in shape_els:
            # TODO: Make load code shape-agnostic
            new_shape = CheckerBoard()
            new_shape.load(shape_el)
            self.shapes.append(new_shape)

class CkgWaitScreen(CkgDisplayGroup):
    """Dummy display group, waits for user input to proceed."""

    DEFAULTS = {'cont_keys': [(pyglet.window.key.NUM_ENTER,
                               pyglet.window.key.ENTER),
                              (pyglet.window.key.SPACE,)],
                'infos': ["press enter when ready",
                          "the experiment will start soon"],
                'res': CkgProj.DEFAULTS['res'],
                'font_name': SANS_SERIF,
                'font_color': (0, 0, 0, 255),
                'font_size': 16,
                'bold': True,
                'info_pos': (1/2.0, 16/30.0),
                'info_anchor': ('center', 'center')}

    def __init__(self, **keywords):
        """Create an informative waitscreen that proceeds after user input."""
        for kw in self.__class__.DEFAULTS.keys():
            if kw in keywords.keys():
                setattr(self, kw, keywords[kw])
            else:
                setattr(self, kw, self.__class__.DEFAULTS[kw])
        if len(self.cont_keys) != len(self.infos):
            msg = 'list length mismatch between cont_keys and infos'
            raise IndexError(msg)
        else:
            self.num_steps = len(self.infos)
        self.labels = [pyglet.text.Label(info,
                                         font_name=self.font_name,
                                         font_size=self.font_size,
                                         color=self.font_color,
                                         bold=self.bold,
                                         x=int(self.res[0]*self.info_pos[0]),
                                         y=int(self.res[1]*self.info_pos[1]),
                                         anchor_x=self.info_anchor[0],
                                         anchor_y=self.info_anchor[1])
                       for info in self.infos]
        self.reset()

    def __setattr__(self, name, value):
        self.__dict__[name] = value

    def duration(self):
        """Returns zero since wait times are arbitrary."""
        return to_decimal(0)

    def reset(self):
        """Resets some flags."""
        self.visible = False
        self.old_visible = False
        self.steps_done = 0
        self.over = False

    def draw(self, **keywords):
        """Draw informative text."""
        self.labels[self.steps_done].draw()

    def update(self, **keywords):
        """Checks for keypress, sends trigger upon end."""
        
        keystates = keywords['keystates']

        if max([keystates[key] for key in self.cont_keys[self.steps_done]]):
            self.steps_done += 1
        if self.steps_done == self.num_steps:
            self.over = True

class CheckerShape:
    # Abstract class, to be implemented.
    pass

class CheckerDisc(CheckerShape):
    # Circular checker pattern, to be implemented
    pass
        
class CheckerBoard(CheckerShape):

    DEFAULTS = OrderedDict([('dims',  (5, 5)),
                            ('init_unit',  (30, 30)),
                            ('end_unit',  (50, 50)),
                            ('position',  (0, 0)),
                            ('anchor',  'bottomleft'),
                            ('cols',  ((0, 0, 0), (255, 255, 255))),
                            ('freq', 1),
                            ('phase', 0)])

    # TODO: Reimplement mid/center anchor functionality in cool new way

    def __init__(self, **keywords):
        for kw in self.__class__.DEFAULTS.keys():
            if kw in keywords.keys():
                setattr(self, kw, keywords[kw])
            else:
                setattr(self, kw, self.__class__.DEFAULTS[kw])
        self.reset()

    def __setattr__(self, name, value):
        # Type conversions
        if name == 'dims':
            if len(value) != 2:
                raise ValueError
            value = tuple([int(x) for x in value])
        elif name in ['init_unit', 'end_unit', 'position']:
            if len(value) != 2:
                raise ValueError
            value = tuple([to_decimal(x) for x in value])
        elif name == 'anchor':
            if value not in graphics.locations.keys():
                raise ValueError
        elif name == 'cols':
            if len(value) != 2:
                raise ValueError
            for col in value:
                if len(col) != 3:
                    raise ValueError
            value = tuple([tuple([int(c) for c in col]) for col in value])
        elif name in ['freq', 'phase']:
            value = to_decimal(value)
        # Store value
        self.__dict__[name] = value
        # Recompute if necessary
        if name in ['dims', 'init_unit', 'end_unit', 
                    'position', 'anchor','cols']:
            self._computed = False

    def save(self, document, parent):
        """Saves board in specified XML document as child of parent."""
        board_el = document.createElement('shape')
        board_el.setAttribute('type', 'board')
        parent.appendChild(board_el)
        for var in self.__class__.DEFAULTS.keys():
            xml_set(document, board_el, var, repr(getattr(self, var)))
          
    def load(self, element):
        """Loads group from XML DOM element."""
        for var in self.__class__.DEFAULTS.keys():
            try:
                value = eval(xml_get(element, XML_NAMESPACE, var))
            except IndexError:
                print "warning: missing attribute '{0}'".format(var)
                value = self.__class__.DEFAULTS[var]
                print "using default value '{0}' instead...".format(value)
            setattr(self, var, value)

    def reset(self, new_phase=None):
        """Resets checkerboard animation back to initial phase."""
        if new_phase == None:
            new_phase = self.phase
        self._cur_phase = new_phase
        self._prev_phase = new_phase
        self.flipped = False
        self._first_draw = True
        if not self._computed:
            self.compute()

    def update(self, fps):
        """Increase the current phase of the checkerboard animation."""
        self._prev_phase = self._cur_phase
        if self.freq != 0:
            if INT_HALF_PERIODS:
                frames_per_half_period = round(fps / (self.freq * 2))
                degs_per_frame = 180 / to_decimal(frames_per_half_period)
            else:
                degs_per_frame = 360 * self.freq / fps
            self._cur_phase += degs_per_frame
            if self._cur_phase >= 360:
                self._cur_phase %= 360
        cur_n = int(self._cur_phase // 180)
        prev_n = int(self._prev_phase // 180)
        if cur_n != prev_n:
            self.flipped = True
        else:
            self.flipped = False

    def compute(self):
        """Computes a model of the checkerboard for drawing later."""
        # Create batches to store model
        self._batches = [pyglet.graphics.Batch() for n in range(2)]

        # Calculate size of checkerboard in pixels
        self._size = tuple([(y1 + y2) / 2 * n for y1, y2, n in
                            zip(self.init_unit, self.end_unit, self.dims)])

        # Calculate unit size gradient
        unit_grad = tuple([(2 if (flag == 0) else 1) * 
                           (y2 - y1) / n for y1, y2, n, flag in 
                           zip(self.init_unit, self.end_unit, self.dims,
                               graphics.locations[self.anchor])])

        # Set initial values
        if PRERENDER_TO_TEXTURE:
            init_pos = [(1 - a)* s/to_decimal(2) for s, a in 
                        zip(self._size, graphics.locations[self.anchor])]
        else:
            init_pos = list(self.position)
        init_unit = [c + m/2 for c, m in zip(self.init_unit, unit_grad)]
        cur_unit = list(init_unit)
        cur_unit_pos = list(init_pos)

        # Add unit cells to batches in nested for loop
        for j in range(self.dims[1]):
            for i in range(self.dims[0]):

                cur_unit_rect = graphics.Rect(cur_unit_pos, cur_unit,
                                              anchor=self.anchor)
                cur_unit_rect.col = self.cols[(i + j) % 2]
                cur_unit_rect.add_to_batch(self._batches[0])
                cur_unit_rect.col = self.cols[(i + j + 1) % 2]
                cur_unit_rect.add_to_batch(self._batches[1])

                # Increase x values
                cur_unit_pos[0] += \
                    graphics.locations[self.anchor][0] * cur_unit[0]
                cur_unit[0] += unit_grad[0]

            # Reset x values
            cur_unit_pos[0] = init_pos[0]
            cur_unit[0] = init_unit[0]

            # Increase y values
            cur_unit_pos[1] += \
                graphics.locations[self.anchor][1] * cur_unit[1]
            cur_unit[1] += unit_grad[1]

        if PRERENDER_TO_TEXTURE:
            # Create textures
            int_size = [int(round(s)) for s in self._size]
            self._prerenders =\
                [pyglet.image.Texture.create(*int_size) for n in range(2)]
            # Set up framebuffer
            fbo = graphics.Framebuffer()
            for n in range(2):
                fbo.attach_texture(self._prerenders[n])
                # Draw batch to texture
                fbo.start_render()
                self._batches[n].draw()
                fbo.end_render()
                # Anchor textures for correct blitting later
                self._prerenders[n].anchor_x, self._prerenders[n].anchor_y =\
                    [int(round((1 - a)* s/to_decimal(2))) for s, a in 
                     zip(self._size, graphics.locations[self.anchor])]
            fbo.delete()
            # Delete batches since they won't be used
            del self._batches

        self._computed = True

    def draw(self, photoburst=False, always_compute=False):
        """Draws appropriate prerender depending on current phase.

        photoburst -- draw first color for only one frame for testing purposes

        always_compute -- recompute what the checkerboard should look like
        every frame

        """
        if not self._computed or always_compute:
            self.compute()
        self._cur_phase %= 360
        n = int(self._cur_phase // 180)
        if photoburst and n == 0 and not self.flipped:
            n = 1
        if PRERENDER_TO_TEXTURE:
            self._prerenders[n].blit(*self.position)
        else:
            self._batches[n].draw()

    def lazydraw(self):
        """Only draws on color reversal."""
        cur_n = int(self._cur_phase // 180)
        prev_n = int(self._prev_phase // 180)
        if (cur_n != prev_n) or self._first_draw:
            self.draw()
        if self._first_draw:
            self._first_draw = False
