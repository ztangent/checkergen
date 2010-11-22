import os, sys
import pygame
from pygame.locals import *

DEFAULT_FPS = 60

BLACK = Color(0,0,0)
GREY = Color(127,127,127)
WHITE = Color(255,255,255) 

CB_ORIGIN = {'topleft': (1,1), 'topright': (-1,1), 'btmleft': (1,-1), 'btmright': (-1,-1)}

global_fps = DEFAULT_FPS

class CheckerBoard:

    def __init__(self, dims, init_unit, end_unit, position, origin, cols, freq, phase = 0):
        self.dims = dims
        self.init_unit = [float(x) for x in init_unit]
        self.end_unit = [float (x) for x in end_unit]
        self.unit_grad = [(self.end_unit[x] - self.init_unit[x]) / self.dims[x] for x in range(2)]
        self.position = list(position)
        self.origin = origin
        self.cols = list(cols)
        self.freq = float(freq)
        self.phase = float(phase) # In degrees
        self.firstrun = True

    def draw(self, Surface, position = None):
        # Set initial values
        if position != None:
            self.position = list(position)
        cur_unit_pos = self.position[:]
        cur_unit = [self.init_unit[x] + (self.unit_grad[x] / 2) for x in range(len(self.init_unit))]
        for j in range(self.dims[1]):
            for i in range(self.dims[0]):
                cur_unit_rect = cur_unit_pos + cur_unit
                # Ensure unit cells are drawn in the right place
                for n in range(len(CB_ORIGIN[self.origin])):
                    if CB_ORIGIN[self.origin][n] < 0:
                        cur_unit_rect[n] -= cur_unit[n]
                Surface.fill(self.cols[(i + j) % 2], tuple(cur_unit_rect))
                # Increase x values
                cur_unit_pos[0] += CB_ORIGIN[self.origin][0]*cur_unit[0]
                cur_unit[0] += self.unit_grad[0]
            # Reset x values
            cur_unit_pos[0] = self.position[0]
            cur_unit[0] = self.init_unit[0] + (self.unit_grad[0] / 2)
            # Increase y values
            cur_unit_pos[1] += CB_ORIGIN[self.origin][1]*cur_unit[1]
            cur_unit[1] += self.unit_grad[1]

    def anim(self, Surface, position = None, fps = None):
        if fps == None:
            fps = global_fps
        fpp = fps / self.freq
        if self.firstrun == True:
            self.firstrun = False
        else:
            self.phase += 360 / fpp
        if self.phase >= 180:
            self.phase -= 180
            self.cols.reverse()
        self.draw(Surface, position)

pygame.init()

size = width, height = 800, 600
window = pygame.display.set_mode(size)
pygame.display.set_caption('checkergen')
screen = pygame.display.get_surface()

clock = pygame.time.Clock()

screen.fill(GREY)
 
myboard1 = CheckerBoard([6, 6], [20, 20], [40, 40], [width/2 - 20, height/2 - 20], 'btmright', [BLACK, WHITE], 1)
myboard2 = CheckerBoard([6, 6], [20, 20], [40, 40], [width/2 + 20, height/2 - 20], 'btmleft', [BLACK, WHITE], 2)
myboard3 = CheckerBoard([6, 6], [20, 20], [40, 40], [width/2 - 20, height/2 + 20], 'topright', [BLACK, WHITE], 3)
myboard4 = CheckerBoard([6, 6], [20, 20], [40, 40], [width/2 + 20, height/2 + 20], 'topleft', [BLACK, WHITE], 4)

while True:
    clock.tick(global_fps)
    myboard1.anim(screen)
    myboard2.anim(screen)
    myboard3.anim(screen)
    myboard4.anim(screen)
    for event in pygame.event.get():
        if event.type == QUIT:
            sys.exit(0)

    pygame.display.flip()
