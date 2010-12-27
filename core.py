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
from utils import *

CKG_FMT = 'ckg'
XML_NAMESPACE = 'http://github.com/ZOMGxuan/checkergen'
DEFAULT_NAME = 'untitled'
DEFAULT_FPS = 60
DEFAULT_RES = 800, 600
DEFAULT_BG = (127, 127, 127)
EXPORT_FMTS = ['bmp', 'tga', 'jpg', 'png']
DEFAULT_EXPORT_FMT = 'png'
MAX_EXPORT_FRAMES = 10000

class FileFormatError(ValueError):
    """Raised when correct file format/extension is not supplied."""
    pass

class FrameOverflowError(Exception):
    """Raised when more than MAX_EXPORT_FRAMES are going to be exported."""
    pass
        
class CkgProj:
    """Defines a checkergen project, with checkerboards and other settings."""

    def __init__(self, name=DEFAULT_NAME, fps=DEFAULT_FPS, res=DEFAULT_RES, 
                 bg=DEFAULT_BG, export_fmt=DEFAULT_EXPORT_FMT, path=None):
        if path != None:
            self.load(path)
            return
        self.name = str(name)
        self.fps = to_decimal(fps)
        self.res = tuple([int(d) for d in res])
        self.bg = bg
        if export_fmt in EXPORT_FMTS:
            self.export_fmt = export_fmt
        else:
            msg = 'image format not recognized or supported'
            raise FileFormatError(msg)
        self.boards = []

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name != 'dirty':
            self.dirty = True

    def load(self, path):
        """Loads project from specified path."""

        def xml_get(parent, namespace, name):
            """Returns concatenated text node values inside an element."""
            # TODO: fix crashing on messed up namespace
            element = parent.getElementsByTagNameNS(namespace, name)[0]
            strings = []
            for node in element.childNodes:
                if node.nodeType == node.TEXT_NODE:
                    strings.append(node.data)
            return ''.join(strings)

        name, ext = os.path.splitext(os.path.basename(path))
        if ext == '.{0}'.format(CKG_FMT):
            self.name = name
        else:
            msg = "path lacks '.{0}' extension".format(CKG_FMT)
            raise FileFormatError(msg)

        with open(path, 'r') as project_file:
            doc = minidom.parse(project_file)

        project = doc.documentElement
        for var in ['fps', 'res', 'bg', 'export_fmt']:
            value = eval(xml_get(project, XML_NAMESPACE, var))
            setattr(self, var, value)
        self.boards = []
        board_els = project.getElementsByTagNameNS(XML_NAMESPACE, 'board')
        board_args = ['dims', 'init_unit', 'end_unit', 'position',
                      'anchor', 'cols', 'freq', 'phase']
        for board_el in board_els:
            board_dict = dict([(arg, eval(xml_get(board_el, 
                                                  XML_NAMESPACE, arg)))
                               for arg in board_args])
            new_board = CheckerBoard(**board_dict)
            self.boards.append(new_board)

        self.dirty = False

    def save(self, path):
        """Saves project to specified path as an XML document."""

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

        self.name, ext = os.path.splitext(os.path.basename(path))
        if ext != '.{0}'.format(CKG_FMT):
            path = '{0}.{1}'.format(path, CKG_FMT)

        impl = minidom.getDOMImplementation()
        doc = impl.createDocument(XML_NAMESPACE, 'project', None)
        project = doc.documentElement
        # Hack below because minidom doesn't support namespaces properly
        project.setAttribute('xmlns', XML_NAMESPACE)
        for var in ['fps', 'res', 'bg', 'export_fmt']:
            xml_set(doc, project, var, repr(getattr(self, var)))
        for board in self.boards:
            board_el = doc.createElement('board')
            project.appendChild(board_el)
            for var in ['dims', 'init_unit', 'end_unit', 'position',
                        'anchor', 'cols', 'freq', 'phase']:
                xml_set(doc, board_el, var, repr(getattr(board, var)))

        with open(path, 'w') as project_file:
            project_file.write(xml_pretty_print(doc,indent='    '))

        self.dirty = False

        return path

    def display(self, fullscreen=False, logtime=False):
        for board in self.boards:
            board.reset()

        window = pyglet.window.Window(*self.res, visible=False)
        window.switch_to()
        graphics.set_clear_color(self.bg)
        window.clear()
        window.set_visible()

        fix_cross = graphics.Cross([r/2 for r in self.res], (20, 20))

        if logtime:
            timer = Timer()
            timer.start()
            logstring = ''

        while not window.has_exit:
            window.clear()
            for board in self.boards:
                board.draw()
                board.update(self.fps)
            fix_cross.draw()
            window.dispatch_events()
            window.flip()
            if logtime:
                logstring = '\n'.join([logstring, str(timer.restart())])
        window.close()

        if logtime:
            filename = '{0}.log'.format(self.name)
            with open(filename, 'w') as logfile:
                logfile.write(logstring)

    def export(self, export_dir, export_fmt=None, folder=True, force=False):
        if not os.path.isdir(export_dir):
                msg = 'export path is not a directory'
                raise IOError(msg)
        if export_fmt == None:
            export_fmt = self.export_fmt

        fpps = [self.fps / board.freq for board in 
                self.boards if board.freq != 0]
        frames = reduce(lcm, fpps)
        count = 0

        if frames > MAX_EXPORT_FRAMES and not force:
            msg = 'large number ({0}) of frames to be exported'.\
                format(MAX_EXPORT_FRAMES)
            raise FrameOverflowError(msg)

        if folder:
            export_dir = os.path.join(export_dir, self.name)
            if not os.path.isdir(export_dir):
                os.mkdir(export_dir)

        for board in self.boards:
            board.reset()

        canvas = pyglet.image.Texture.create(*self.res)
        fbo = graphics.Framebuffer(canvas)
        fbo.start_render()
        graphics.set_clear_color(self.bg)
        fbo.clear()

        while count < frames:
            for board in self.boards:
                board.lazydraw()
                board.update(self.fps)
            savepath = \
                os.path.join(export_dir, 
                             '{0}{2}.{1}'.
                             format(self.name, export_fmt,
                                    repr(count).zfill(numdigits(frames-1))))
            canvas.save(savepath)
            count += 1

        fbo.delete()
        
class CheckerBoard:

# TODO: Reimplement mid/center anchor functionality in cool new way

    def __init__(self, dims, init_unit, end_unit, position, anchor, 
                 cols, freq, phase=0, prerender_to_texture=False):
        self.dims = tuple([int(x) for x in dims])
        self.init_unit = tuple([to_decimal(x) for x in init_unit])
        self.end_unit = tuple([to_decimal(x) for x in end_unit])
        self.position = tuple([to_decimal(x) for x in position])
        if anchor in graphics.locations and type(anchor) == str:
            self.anchor = anchor
        else:
            raise TypeError
        self.cols = tuple(cols)
        self.freq = to_decimal(freq)
        self.phase = to_decimal(phase)
        self.prerender_to_texture = prerender_to_texture
        self.reset()

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name in ['dims', 'init_unit', 'end_unit', 
                    'position', 'anchor','cols']:
            self._computed = False

    def reset(self, new_phase=None):
        """Resets checkerboard animation back to initial phase."""
        if new_phase == None:
            new_phase = self.phase
        self._cur_phase = new_phase
        self._prev_phase = new_phase
        self._first_draw = True
        if not self._computed:
            self.compute()

    def update(self, fps=DEFAULT_FPS):
        """Increase the current phase of the checkerboard animation."""
        self._prev_phase = self._cur_phase
        if self.freq != 0:
            fpp = fps / self.freq
            self._cur_phase += 360 / fpp
            if self._cur_phase >= 360:
                self._cur_phase %= 360

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
        if self.prerender_to_texture:
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

        if self.prerender_to_texture:
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
        if self.prerender_to_texture:
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
