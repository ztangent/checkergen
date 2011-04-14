"""Contains core functionality of checkergen.

Errors and Exceptions:
FileFormatError
FrameOverflowError

Classes:
CkgProj -- A checkergen project, contains settings and CkgDisplayGroups.
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
from datetime import datetime
from xml.dom import minidom

import pyglet

import graphics
import priority
import trigger
import eyetracking
from utils import *

# Use OrderedDict substitute if we don't have Python 2.7
if sys.version_info < (2, 7):
    from odict import OrderedDict
else:
    from collections import OrderedDict

CKG_FMT = 'ckg'
LOG_FMT = 'csv'
XML_NAMESPACE = 'http://github.com/ZOMGxuan/checkergen'
MAX_EXPORT_FRAMES = 100000
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

    DEFAULTS['disp_ops'] = OrderedDict([('repeats', 1),
                                        ('waitless', False),
                                        ('fullscreen', False),
                                        ('priority', None),
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
                                        ('trybreak', None),
                                        ('nolog', False)])

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

    def display(self, **keywords):
        """Displays the project animation on the screen.

        name -- name that logfile will be saved with

        repeats -- number of times specified order of display groups should
        be repeated

        waitless -- if true, no waitscreens will appear at the start of each
        repeat

        fullscreen -- animation is displayed fullscreen if true, stretched
        to fit if necessary

        priority -- priority level to which process should be raised

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

        tryagain -- append groups during which subject failed to fixate up to
        this number of times to the group queue

        trybreak -- append a wait screen to the group queue every time
        after this many groups have been appended to the queue
        
        order -- order in which groups (specified by id) will be displayed

        """

        # Create RunState
        disp_ops = self.disp_ops
        for kw in keywords.keys():
            if kw in disp_ops.keys() and keywords[kw] != None:
                disp_ops[kw] = keywords[kw]
        if 'name' in keywords.keys() and keywords['name'] != None:
            name = keywords['name']
        else:
            timestr = datetime.today().strftime('_%Y-%m-%d_%H-%M-%S')
            name = self.name + timestr
        if 'order' in keywords.keys() and len(keywords['order']) > 0:
            order = keywords['order']
        elif len(self.orders) > 0:
            order = random.choice(self.orders)
        else:
            order = range(len(self.groups))
        runstate = CkgRunState(name=name,
                               res=self.res, fps=self.fps, bg=self.bg,
                               cross_cols=self.cross_cols,
                               cross_times=self.cross_times,
                               disp_ops=disp_ops, order=order)
        runstate.start()
        waitscreen = CkgWaitScreen()

        # Count through pre
        for count in range(self.pre * self.fps):
            if runstate.window.has_exit:
                break
            runstate.update()
        # Loop through repeats
        for i in range(runstate.disp_ops['repeats']):
            # Show waitscreen
            if not runstate.disp_ops['waitless']:
                waitscreen.reset()
                waitscreen.display(runstate)
            # Loop through display groups
            runstate.events['blk_on'] = True
            for gid in runstate.order:
                if gid == -1:
                    waitscreen.reset()
                    waitscreen.display(runstate)
                else:
                    self.groups[gid].display(runstate)
                # Append failed groups
                if runstate.disp_ops['eyetrack'] and runstate.truefail:
                    if len(runstate.add_gids) < runstate.disp_ops['tryagain']:
                        runstate.add_gids.append(gid)
                    else:
                        runstate.fail_gids.append(gid)
            runstate.events['blk_off'] = True
        # Loop through added groups
        if runstate.disp_ops['eyetrack']:
            for blk in grouper(runstate.add_gids,
                               runstate.disp_ops['trybreak']):
                # Show waitscreen
                if not runstate.disp_ops['waitless']:                
                    waitscreen.reset()
                    waitscreen.display(runstate)
                runstate.events['blk_on'] = True
                # Loop through display groups
                for gid in blk:
                    if gid != None:
                        self.groups[gid].display(runstate)
                runstate.events['blk_on'] = True            
        # Count through post
        for count in range(self.post * self.fps):
            if runstate.window.has_exit:
                break
            runstate.update()

        # Stop and output log
        runstate.stop()
        if not runstate.disp_ops['nolog']:
            runstate.log()

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
 
class CkgRunState:
    """Contains information about the state of a checkergen project
    when it is being displayed or exported."""

    DEFAULTS = dict([('name', 'untitled'),
                     ('res', None),
                     ('fps', None),
                     ('bg', None),
                     ('cross_cols', None),
                     ('cross_times', None),
                     ('order', []),
                     ('disp_ops', None),
                     ('events', None),
                     ('add_gids', []),
                     ('fail_gids', []),
                     ('timestamps', []),
                     ('durstamps', []),
                     ('trigstamps', [])])

    DEFAULTS['events'] = dict([('blk_on', False),
                               ('blk_off', False),
                               ('track_on', False),
                               ('track_off', False),
                               ('fix_on', False),
                               ('fix_off', False),
                               ('grp_on', False),
                               ('grp_off', False),
                               ('sids', set())])
    
    def __init__(self, **keywords):
        """Creates the RunState."""
        for kw in self.__class__.DEFAULTS.keys():
            if kw in keywords.keys():
                setattr(self, kw, keywords[kw])
            else:
                setattr(self, kw, self.__class__.DEFAULTS[kw])

    def start(self):
        """Initialize all subsystems and start the run."""

        if self.disp_ops == None:
            msg = "RunState lacks display options"
            raise ValueError(msg)

        if min(self.res, self.fps, self.bg,
               self.cross_cols, self.cross_times) == None:
            msg = "RunState intialized with insufficent project information"
            raise ValueError(msg)

        self._count = 0

        # Create fixation crosses
        self.fix_crosses = [graphics.Cross([r/2 for r in self.res],
                                           (20, 20), col = cross_col) 
                            for cross_col in self.cross_cols]

        # Create test rectangle
        if self.disp_ops['phototest']:
            self.test_rect = graphics.Rect((0, self.res[1]), 
                                           [r/8 for r in self.res],
                                           anchor='topleft')

        # Initialize ports
        if self.disp_ops['trigser']:
            if not trigger.available['serial']:
                msg = 'serial port functionality not available'
                raise NotImplementedError(msg)
        if self.disp_ops['trigpar']:
            if not trigger.available['parallel']:
                msg = 'parallel port functionality not available'
                raise NotImplementedError(msg)
        trigger.init(self.disp_ops['trigser'], self.disp_ops['trigpar'])

        # Initialize eyetracking
        if self.disp_ops['eyetrack']:
            if not eyetracking.available:
                msg = 'eyetracking functionality not available'
                raise NotImplementedError(msg)
            if self.disp_ops['trybreak'] == None:
                self.disp_ops['trybreak'] = len(self.order)
            self.fixated = False
            self.old_fixated = False
            self.tracked = False
            self.old_tracked = False
            self.fix_fail = False
            self.true_fail = False
            eyetracking.select_source(self.disp_ops['etuser'],
                                      self.disp_ops['etvideo'])
            eyetracking.start()
        
        # Stretch to fit screen only if project res does not equal screen res
        self.scaling = False
        if self.disp_ops['fullscreen']:
            self.window = pyglet.window.Window(fullscreen=True, visible=False)
            if (self.window.width, self.window.height) != self.res:
                self.scaling = True
        else:
            self.window = pyglet.window.Window(*self.res, visible=False)

        # Set up KeyStateHandler to handle keyboard input
        self.keystates = pyglet.window.key.KeyStateHandler()
        self.window.push_handlers(self.keystates)

        # Clear window and make visible
        self.window.switch_to()
        graphics.set_clear_color(self.bg)
        self.window.clear()
        self.window.set_visible()

        # Create framebuffer object for drawing unscaled scene
        if self.scaling:
            self.canvas = pyglet.image.Texture.create(*self.res)
            self.fbo = graphics.Framebuffer(self.canvas)
            self.fbo.start_render()
            graphics.set_clear_color(self.bg)
            self.fbo.clear()

        # Set process priority
        if self.disp_ops['priority'] != None:
            if not priority.available[sys.platform]:
                msg = "setting priority not available on {0}".\
                    format(sys.platform)
                raise NotImplementedError(msg)
            else:
                if self.disp_ops['priority'].isdigit():
                    self.disp_ops['priority'] = int(self.disp_ops['priority'])
                priority.set(self.disp_ops['priority'])

        # Start timers
        if self.disp_ops['logtime']:
            self.timer = Timer()
            self.timer.start()
        if self.disp_ops['logdur']:
            self.dur = Timer()
            self.dur.start()

    def update(self):
        """Update the RunState."""

        # Check for tracking and fixation
        if self.disp_ops['eyetrack']:
            self.old_tracked = self.tracked
            self.tracked = eyetracking.is_tracked()
            self.old_fixated = self.fixated
            self.fixated = eyetracking.is_fixated(FIX_POS, FIX_RANGE, FIX_PER)

            if self.fixated:
                # Draw normal cross color if fixating
                self.fix_crosses[0].draw()
            else:
                # Draw alternative cross color if not fixating
                self.fix_crosses[1].draw()

            # Update eyetracking events
            if self.tracked != self.old_tracked:
                if self.tracked:
                    self.events['track_on'] = True
                else:
                    self.events['track_off'] = True
            if self.fixated != self.old_fixated:
                if self.fixated:
                    self.events['fix_on'] = True
                else:
                    self.events['fix_off'] = True

            # Check for failure of trial
            if self.tracked and not self.fixated:
                self.fix_fail = True
        else:
            # Change cross color based on time
            if (self._count % (sum(self.cross_times) * self.fps) 
                < self.cross_times[0] * self.fps):
                self.fix_crosses[0].draw()
            else:
                self.fix_crosses[1].draw()                
                
        # Blit canvas to screen if necessary
        if self.scaling:
            self.fbo.end_render()
            self.canvas.blit(0, 0)
        self.window.switch_to()
        self.window.dispatch_events()
        self.window.flip()
        # Make sure everything has been drawn
        pyglet.gl.glFinish()

        # Append time information to lists
        if self.disp_ops['logtime']:
            self.timestamps.append(self.timer.elapsed())
        elif self.disp_ops['logdur']:
            self.timestamps.append('')
        if self.disp_ops['logdur']:
            self.durstamps.append(self.dur.restart())
        elif self.disp_ops['logtime']:
            self.durstamps.append('')

        # Send trigger ASAP after flip
        if self.disp_ops['trigser'] or self.disp_ops['trigpar']:
            trigger.send(trigser, trigpar, self.encode_events())

        # Log when triggers are sent
        if (self.disp_ops['logtime'] and
            (self.disp_ops['trigser'] or self.disp_ops['trigpar']) and
            self.encode_events() != None):
            self.trigstamps.append(self.encode_events())
        else:
            self.trigstamps.append('')

        # Clear canvas, events, prepare for next frame
        if self.scaling:
            self.fbo.start_render()
            self.fbo.clear()
        else:
            self.window.clear()
        self.events = self.__class__.DEFAULTS['events']

        self._count += 1

    def stop(self):
        """Clean up RunState."""
        if self.disp_ops['eyetrack']:
            eyetracking.stop()
        if self.scaling:
            self.fbo.delete()
            del self.canvas
        self.window.close()
        if self.disp_ops['trigser'] or self.disp_ops['trigpar']:
            trigger.quit(trigser, trigpar)
        if self.disp_ops['priority'] != None:
            priority.set('normal')

    def log(self, path=None):
        """Write a log file for the experimental run in the CSV format."""

        if path == None:
            path = os.path.join(os.getcwd(),
                                '{0}.{1}'.format(self.name, LOG_FMT))
        else:
            self.name, ext = os.path.splitext(os.path.basename(path))
            if ext != '.{0}'.format(LOG_FMT):
                path = '{0}.{1}'.format(path, LOG_FMT)

        with open(path, 'wb') as logfile:
            writer = csv.writer(logfile, dialect='excel-tab')
            writer.writerow(['checkergen log file'])
            writer.writerow(['display options:'])
            writer.writerow(self.disp_ops.keys())
            writer.writerow(self.disp_ops.values())
            writer.writerow(['order:'] + self.order)
            if self.disp_ops['eyetrack']:
                write.writerow(['groups added'])
                for blk in grouper(self.add_gids,
                                   self.disp_ops['trybreak'], ''):
                    write.writerow(blk)
                write.writerow(['groups failed'])
                for blk in grouper(self.fail_gids,
                                   self.disp_ops['trybreak'], ''):
                    write.writerow(blk)
            if self.disp_ops['logtime'] or self.disp_ops['logdur']:
                stamps = [self.timestamps, self.durstamps, self.trigstamps]
                writer.writerow(['timestamps', 'durations', 'triggers'])
                for stamp in zip(*stamps):
                    writer.writerow(list(stamp))

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
        """Resets counts and all contained shapes."""
        self._flip_count = [0] * len(self.shapes)
        for shape in self.shapes:
            shape.reset()

    def draw(self, runstate):
        """Draws all contained shapes during the appropriate interval."""
        for shape in self.shapes:
            shape.draw(photoburst=runstate.disp_ops['photoburst'])

    def update(self, runstate):
        """Updates contained shapes, sets event triggers."""
        # Set events to be sent
        if runstate.disp_ops['fpst'] > 0:
            for n, shape in enumerate(self.shapes):
                if shape.flipped:
                    self._flip_count[n] += 1
                if self._flip_count[n] >= fpst:
                    runstate.events['sids'].add(n)
                    self._flip_count[n] = 0
        # Update contained shapes
        for shape in self.shapes:
            shape.update(runstate.fps)

    def display(self, runstate):
        """Display the group in the context described by supplied runstate."""
        self.reset()
        for count in range(self.pre * runstate.fps):
            if runstate.window.has_exit:
                break
            runstate.update()
        runstate.events['blk_on'] = True
        if runstate.disp_ops['eyetrack']:
            runstate.fix_fail = False
            renstate.true_fail = False
        for count in range(self.disp * runstate.fps):
            if runstate.window.has_exit:
                break
            self.draw(runstate)
            self.update(runstate)
            runstate.update()
        runstate.events['blk_off'] = True
        if runstate.disp_ops['eyetrack']:
            if runstate.fix_fail:
                runstate.true_fail = True
        for count in range(self.post * runstate.fps):
            if runstate.window.has_exit:
                break
            runstate.update()

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
        self.steps_done = 0

    def draw(self, runstate):
        """Draw informative text."""
        self.labels[self.steps_done].draw()

    def update(self, runstate):
        """Checks for keypress, sends trigger upon end."""
        if max([runstate.keystates[key] for 
                key in self.cont_keys[self.steps_done]]):
            self.steps_done += 1

    def display(self, runstate):
        """Displays waitscreen in context described by supplied runstate."""
        while self.steps_done < self.num_steps:
            if runstate.window.has_exit:
                break
            self.draw(runstate)
            self.update(runstate)
            runstate.update()

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

        self._computed = True

    def draw(self, photoburst=False, always_compute=False):
        """Draws appropriate batch depending on current phase.

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
        self._batches[n].draw()

    def lazydraw(self):
        """Only draws on color reversal."""
        cur_n = int(self._cur_phase // 180)
        prev_n = int(self._prev_phase // 180)
        if (cur_n != prev_n) or self._first_draw:
            self.draw()
        if self._first_draw:
            self._first_draw = False
