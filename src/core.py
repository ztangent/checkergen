"""Contains core functionality of checkergen.

Errors and Exceptions:
FileFormatError
FrameOverflowError

Classes:
CkgProj -- A checkergen project, contains settings and CheckerBoards.
CheckerBoard -- A (distorted) checkerboard pattern, can color-flip.

"""

import os
import sys
import re
from xml.dom import minidom

import pyglet

import graphics
import signals
from utils import *

CKG_FMT = 'ckg'
XML_NAMESPACE = 'http://github.com/ZOMGxuan/checkergen'
MAX_EXPORT_FRAMES = 100000
PRERENDER_TO_TEXTURE = False
EXPORT_FMTS = ['png']

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

    DEFAULTS = {'name': 'untitled',
                'fps': 60,
                'res': (800, 600),
                'bg': (127, 127, 127),
                'export_fmt': 'png',
                'pre': 0,
                'post': 0,
                'cross_cols': ((0, 0, 0), (255, 0, 0)),
                'cross_times': ('Infinity', 1)}

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
        if ext == '.{0}'.format(CKG_FMT):
            self.name = name
        else:
            msg = "path lacks '.{0}' extension".format(CKG_FMT)
            raise FileFormatError(msg)

        with open(path, 'r') as project_file:
            doc = minidom.parse(project_file)

        project = doc.documentElement
        vars_to_load = self.__class__.DEFAULTS.keys()
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
        vars_to_save = self.__class__.DEFAULTS.keys()
        # Name is not stored in project file
        vars_to_save.remove('name')
        for var in vars_to_save:
            xml_set(doc, project, var, repr(getattr(self, var)))
        for group in self.groups:
            group.save(doc, project)
        with open(path, 'w') as project_file:
            project_file.write(xml_pretty_print(doc,indent='    '))

        self._dirty = False

        return path

    def display(self, fullscreen=False, logtime=False, logdur=False,
                sigser=False, sigpar=False, phototest=False, group_queue=[]):
        """Displays the project animation on the screen.

        fullscreen -- animation is displayed fullscreen if true, stretched
        to fit if necessary

        logtime -- timestamp of each frame is saved to a logfile if true

        logdur -- duration of each frame is saved to a logfile if true

        sigser -- send signals through serial port when each group is shown

        sigpar -- send signals through parallel port when each group is shown

        phototest -- draw white rectangle in topleft corner when each group is
        shown for photodiode to detect

        group_queue -- queue of groups to be displayed (in reverse order),
        defaults to order of groups in project (i.e. groups[0] first, etc.)

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
        if group_queue == []:
            group_queue = list(reversed(self.groups))
        cur_group = None
        group_vis_flip = 0
        groups_duration = sum([group.duration() for group in group_queue])
        groups_start = self.pre * self.fps
        groups_stop = (self.pre + groups_duration) * self.fps
        anim_stop = (self.pre + groups_duration + self.post) * self.fps
        if groups_start == 0 and groups_stop > 0:
            groups_visible = True
        else:
            groups_visible = False
        count = 0

        # Initialize ports
        signals.init(sigser, sigpar)

        # Stretch to fit screen only if project res does not equal screen res
        scaling = False
        if fullscreen:
            window = pyglet.window.Window(fullscreen=True, visible=False)
            if (window.width, window.height) != self.res:
                scaling = True
        else:
            window = pyglet.window.Window(*self.res, visible=False)            

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
        if logtime and logdur:
            logstring = ''
            stamp = Timer()
            dur = Timer()
            stamp.start()
            dur.start()
        elif logtime or logdur:
            logstring = ''
            timer = Timer()
            timer.start()

        # Main loop
        while not window.has_exit and count < anim_stop:
            # Clear canvas
            if scaling:
                fbo.start_render()
                fbo.clear()
            else:
                window.clear()
            # Assume no change to group visibility
            group_vis_flip = 0
 
            if groups_visible:
                if cur_group != None:
                    # Check whether group changes in visibility
                    if cur_group.visible != cur_group.old_visible:
                        if cur_group.visible:
                            group_vis_flip = 1
                        elif cur_group.old_visible:
                            group_vis_flip = -1
                    # Check if current group is over
                    if cur_group.over:
                        cur_group = None
                # Get next group from queue
                if cur_group == None:
                    try:
                        cur_group = group_queue.pop()
                        cur_group.reset()
                        if cur_group.visible:
                            group_vis_flip = 1
                    except IndexError:
                        pass
                # Draw and then update group
                if cur_group != None:
                    cur_group.draw()
                    cur_group.update(self.fps)

            # Send signals upon group visibility change
            if group_vis_flip == 1:
                signals.set_group_start()
                # Draw test rectangle
                if phototest:
                    test_rect.gl_draw()
            elif group_vis_flip == -1:
                signals.set_group_stop()
            else:
                signals.set_null()
            # Draw fixation cross based on current count
            if (count % (sum(self.cross_times) * self.fps) 
                < self.cross_times[0] * self.fps):
                fix_crosses[0].gl_draw()
            else:
                fix_crosses[1].gl_draw()                

            # Increment count and set whether groups should be shown
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

            # Append time information to log string            
            if logtime and logdur:
                logstring = '\n'.join([logstring, str(stamp.elapsed())])
                logstring = '\t'.join([logstring, str(dur.restart())])
            elif logtime:
                logstring = '\n'.join([logstring, str(timer.elapsed())])
            elif logdur:
                logstring = '\n'.join([logstring, str(timer.restart())])

            # Send signals ASAP after flip
            signals.send(sigser, sigpar)

            # Log when signals are sent
            if logtime or logdur:
                if group_vis_flip != 0 and (sigser or sigpar):
                    sigmsg = '{0} sent'.format(signals.STATE)
                    logstring = '\t'.join([logstring, sigmsg])

        # Clean up
        window.close()
        if scaling:
            fbo.delete()
            del canvas
        signals.quit(sigser, sigpar)

        # Write log string to file
        if logtime or logdur:
            filename = '{0}.log'.format(self.name)
            with open(filename, 'w') as logfile:
                logfile.write(logstring)

    def export(self, export_dir, export_duration, group_queue=[],
               export_fmt=None, folder=True, force=False):
        if not os.path.isdir(export_dir):
                msg = 'export path is not a directory'
                raise IOError(msg)
        if export_fmt == None:
            export_fmt = self.export_fmt

        # Set-up groups and variables that control their display
        if group_queue == []:
            group_queue = list(reversed(self.groups))
        cur_group = None
        groups_duration = sum([group.duration() for group in group_queue])
        groups_start = self.pre * self.fps
        groups_stop = (self.pre + groups_duration) * self.fps
        anim_stop = (self.pre + groups_duration + self.post) * self.fps
        if groups_start == 0 and groups_stop > 0:
            groups_visible = True
        else:
            groups_visible = False
        count = 0

        # Limit export duration to anim duration
        frames = export_duration * self.fps
        frames = min(frames, anim_stop)

        # Warn user if a lot of frames will be exported
        if frames > MAX_EXPORT_FRAMES and not force:
            msg = 'very large number ({0}) of frames to be exported'.\
                format(frames)
            raise FrameOverflowError(msg)

        # Create folder to store images if necessary
        if folder:
            export_dir = os.path.join(export_dir, self.name)
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
                # Check if current group is over
                if cur_group != None:
                    if cur_group.over:
                        cur_group = None
                # Get next group from queue
                if cur_group == None:
                    try:
                        cur_group = group_queue.pop()
                        cur_group.reset()
                    except IndexError:
                        pass
                # Draw and then update group
                if cur_group != None:
                    cur_group.draw()
                    cur_group.update(self.fps)
            # Draw fixation cross based on current count
            if (count % (sum(self.cross_times) * self.fps) 
                < self.cross_times[0] * self.fps):
                fix_crosses[0].gl_draw()
            else:
                fix_crosses[1].gl_draw()                

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

class CkgDisplayGroup:

    DEFAULTS = {'pre': 0, 'disp': 'Infinity', 'post': 0}

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
        self._disp_start = self.pre
        self._disp_stop = self.pre + self.disp
        self._end_point = self.pre + self.disp + self.post
        self.over = False
        self.old_visible = False
        if self._disp_start == 0 and self._disp_stop > 0:
            self.visible = True
        else:
            self.visible = False
            if self._end_point == 0:
                self.over = True
        for shape in self.shapes:
            shape.reset()

    def draw(self, lazy=False):
        """Draws all contained shapes during the appropriate interval."""
        if self.visible:
            for shape in self.shapes:
                if lazy:
                    shape.lazydraw()
                else:
                    shape.draw()

    def update(self, fps):
        """Increments internal count, makes group visible when appropriate."""
        
        if self.visible:
            # Set triggers to be sent
            for n, shape in enumerate(self.shapes):
                if shape.flipped:
                    signals.set_board_flip(n)
            # Update contained shapes
            for shape in self.shapes:
                shape.update(fps)

        # Increment count and set flags for the next frame
        self._count += 1
        self.old_visible = self.visible
        if (self._disp_start * fps) <= self._count < (self._disp_stop * fps):
            self.visible = True
        else:
            self.visible = False
        if self._count >= (self._end_point * fps):
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
        
class CheckerShape:
    # Abstract class, to be implemented.
    pass

class CheckerDisc(CheckerShape):
    # Circular checker pattern, to be implemented
    pass
        
class CheckerBoard(CheckerShape):

    DEFAULTS = {'dims': (5, 5),
                'init_unit': (30, 30), 'end_unit': (50, 50),
                'position': (0, 0), 'anchor': 'bottomleft',
                'cols': ((0, 0, 0), (255, 255, 255)),
                'freq': 1, 'phase': 0}

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

    def draw(self, always_compute=False):
        """Draws appropriate prerender depending on current phase."""
        if not self._computed or always_compute:
            self.compute()
        self._cur_phase %= 360
        n = int(self._cur_phase // 180)
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