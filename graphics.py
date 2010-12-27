"""Functions for drawing simple 2D shapes, both onscreen and offscreen."""

import ctypes

import pyglet
from pyglet.gl import *

if not gl_info.have_extension('GL_EXT_framebuffer_object'):
    msg = 'framebuffer extension not available in this OpenGL implementation'
    raise NotImplementedError(msg)

locations = {'topleft': (1, -1), 'topright': (-1, -1),
             'bottomleft': (1, 1), 'bottomright': (-1, 1),
             'midtop': (0, -1), 'midbottom': (0, 1),
             'midleft': (1, 0), 'midright': (-1, 0),
             'center': (0, 0)}

def set_clear_color(color=(0,)*3):
    """Set the color OpenGL contexts such as windows will clear to."""
    clamped_color = [c / 255.0 for c in color if type(c) == int]
    glClearColor(*(clamped_color + [1.0]))
    
def get_window_texture(window):
    """Returns color buffer of the specified window as a Texture."""
    window.switch_to()
    Texture = \
        pyglet.image.get_buffer_manager().get_color_buffer().get_texture()
    return Texture 

def get_window_image_data(window):
    """Returns color buffer of the specified window as ImageData."""
    window.switch_to()
    ImageData = \
        pyglet.image.get_buffer_manager().get_color_buffer().get_image_data()
    return ImageData 

class FramebufferIncompleteError(Exception):
    pass

class Framebuffer:

    # Warning: not compatible with OpenGL 3.1 because of use of EXT

    def __init__(self, Texture=None):
        """Creates a new framebuffer object. Attaches texture if specified."""
        self.id = GLuint()
        glGenFramebuffersEXT(1, ctypes.byref(self.id))
        if Texture != None:
            self.attach_texture(Texture)
        self._rendering = False

    def bind(self):
        """Binds framebuffer to current context."""
        glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, self.id)

    def unbind(self):
        """Unbinds framebuffer from current context."""
        glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, 0)

    def delete(self):
        """Deletes framebuffer, after which it cannot be used."""
        self.end_render()
        self.unbind()
        glDeleteFramebuffersEXT(1, ctypes.byref(self.id))         
        
    def attach_texture(self, Texture):
        """Attaches a texture to the framebuffer as the first color buffer."""
        self.bind()
        self.Texture = Texture
        glBindTexture(GL_TEXTURE_2D, Texture.id)
        glFramebufferTexture2DEXT(GL_FRAMEBUFFER_EXT,
                                  GL_COLOR_ATTACHMENT0_EXT,
                                  GL_TEXTURE_2D, Texture.id, 0)

    def set2D(self):
        """Sets up the framebuffer for 2D rendering."""
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, self.Texture.width, 0, self.Texture.height, 0, 1)
        glDisable(GL_DEPTH_TEST)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        # Exact pixelization trick
        # glTranslatef(0.5, 0.5, 0)

    def start_render(self, set2D=True):
        """Sets up rendering environment. To be called before any drawing."""
        if self._rendering:
            return
        self.bind()
        status = glCheckFramebufferStatusEXT(GL_FRAMEBUFFER_EXT)
        if status != GL_FRAMEBUFFER_COMPLETE_EXT:
            msg = 'framebuffer incomplete'
            raise FramebufferIncompleteError(msg)
        glPushAttrib(GL_VIEWPORT_BIT);
        glViewport(0, 0, self.Texture.width, self.Texture.height);
        if set2D:
            self.set2D()
        self._rendering = True

    def end_render(self):
        """Cleans up rendering environment. To be called after drawing."""
        if not self._rendering:
            return
        glPopAttrib();
        self.unbind()
        self._rendering = False

    def render(self, func, args=[], set2D=True, end=False):
        """Calls specified function within the rendering environment."""
        self.start_render(set2D)
        func(*args)
        if end:
            self.end_render()

    def clear(self):
        """Clears the framebuffer to the current clear color."""
        glClear(gl.GL_COLOR_BUFFER_BIT)

class Rect:

    def __init__(self, pos, dims, anchor='bottomleft', col=(255,)*3):
        """Creates a rectangle with a position and dimensions.

        pos -- [x,y] position of the origin of the rectangle in its parent 
        context in pixels.
        
        dims -- [width,height] dimensions of the rectangle in pixels.
        
        anchor -- [x,y] relative position of the origin of the rectangle from
        the bottom left corner. Common locations can be given as string
        constants (e.g. topleft, midbottom, center). 

        col -- Color of the rectangle as a 3-tuple. Defaults to white.

        """
        self.pos = [float(p) for p in pos]
        self.dims = [float(d) for d in dims]
        if type(anchor) == str:
            anchor = [(1 - a)* d/2.0 for d, a in 
                      zip(self.dims, locations[anchor])]
        self.anchor = [float(a) for a in anchor]
        self.col = tuple(col)
        self.VertexList = None
 
    def x(self):
        return [self.pos[0] - self.anchor[0], 
                self.pos[0] - self.anchor[0] + self.dims[0]]

    def y(self):
        return [self.pos[1] - self.anchor[1],
                self.pos[1] - self.anchor[1] + self.dims[1]]

    def verts(self):
        return [(x, y) for x in self.x() for y in self.y()]

    def concat_verts(self):
        concat_verts = []
        for vert in self.verts():
            concat_verts += vert
        return tuple(concat_verts)

    def draw(self):
        """Draws rectangle in the current context."""
        pyglet.graphics.draw_indexed(4, GL_TRIANGLES,
                                     [0, 1, 2, 1, 2, 3],
                                     ('v2f', self.concat_verts()),
                                     ('c3B', self.col * 4))

    def gl_draw(self):
        """Draw using raw OpenGL functions."""
        glBegin(GL_TRIANGLES)
        glColor3ubv(self.col)
        for i in [0, 1, 2, 1, 2, 3]:
            glVertex2fv(self.verts()[i])
        glEnd()

    def add_to_batch(self, Batch):
        """Adds rectangle to specified Batch."""
        self.VertexList = Batch.add_indexed(4, GL_TRIANGLES, None,
                                            [0, 1, 2, 1, 2, 3],
                                            ('v2f', self.concat_verts()),
                                            ('c3B', self.col * 4))

class Cross:

    def __init__(self, pos, dims, thick=2.0, col=(0,)*3):
        """Creates a cross(hair) with a position, dimensions and thickness.

        pos -- [x,y] position of the center of the cross in its parent 
        context in pixels.
        
        dims -- [width,height] dimensions of the cross in pixels.        
        
        thick -- Thickness of the cross in pixels

        col -- Color of the rectangle as a 3-tuple. Defaults to white.

        """
        self.pos = [float(p) for p in pos]
        self.dims = [float(d) for d in dims]
        self.thick = float(thick)
        self.col = tuple(col)
        self.VertexList = None
 
    def x(self):
        return [self.pos[0] - self.dims[0]/2, 
                self.pos[0] + self.dims[0]/2]

    def y(self):
        return [self.pos[1] - self.dims[1]/2, 
                self.pos[1] + self.dims[1]/2]

    def x_verts(self):
        return [(x, self.pos[1]) for x in self.x()]

    def y_verts(self):
        return [(self.pos[0], y) for y in self.y()]

    def verts(self):
        return self.x_verts() + self.y_verts()

    def concat_verts(self):
        concat_verts = []
        for vert in self.verts():
            concat_verts += vert
        return tuple(concat_verts)

    def draw(self):
        """Draws rectangle in the current context."""
        glLineWidth(self.thick)
        pyglet.graphics.draw(4, GL_LINES,
                             ('v2f', self.concat_verts()),
                             ('c3B', self.col * 4))
        glLineWidth(1.0)

    def gl_draw(self):
        """Draw using raw OpenGL functions."""
        glLineWidth(self.thick)
        glBegin(GL_LINES)
        glColor3ubv(self.col)
        for vert in self.verts():
            glVertex2fv(vert)
        glEnd()
        glLineWidth(1.0)

    def add_to_batch(self, Batch):
        """Adds cross to specified Batch. Line thickness not supported."""
        self.VertexList = Batch.add(4, GL_LINES, None,
                                    ('v2f', self.concat_verts()),
                                    ('c3B', self.col * 4))
