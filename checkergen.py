import os, sys
import pygame
from pygame.locals import *

class CheckerBoard:
    def __init__(self, dims, init_unit, end_unit, cols, freq, phase = 0):
        self.dims = dims
        self.init_unit = init_unit
        self.end_unit = end_unit
        self.unit_grad = [(self.end_unit[x] - self.init_unit[x]) / self.dims[x] for x in range(2)]
        self.cols = cols
        self.freq = freq
        self.phase = phase # In degrees
    def draw(self, Surface, position):
        # Set initial values
        cur_unit_pos = list(position)
        cur_unit = [self.init_unit[x] + (self.unit_grad[x] / 2) for x in range(2)]
        for j in range(self.dims[1]):
            for i in range(self.dims[0]):
                pygame.draw.rect(Surface, self.cols[(i + j) % 2], tuple(cur_unit_pos + cur_unit))
                # Increase x values
                cur_unit_pos[0] += cur_unit[0]
                cur_unit[0] += self.unit_grad[0]
            # Reset x values
            cur_unit_pos[0] = position[0]
            cur_unit[0] = self.init_unit[0] + (self.unit_grad[0] / 2)
            # Increase y values
            cur_unit_pos[1] += cur_unit[1]
            cur_unit[1] += self.unit_grad[1]
    def anim(self, Surface, position, fps):
        # TODO: Resolve fractional frames per period
        fpp = fps / self.freq
        self.phase += 360 / fpp
        if self.phase >= 360:
            self.phase -= 360
            self.cols = (self.cols[1], self.cols[0])
            self.draw(Surface, position)

pygame.init()

size = width, height = 800, 600
window = pygame.display.set_mode(size)
pygame.display.set_caption('checkergen')
screen = pygame.display.get_surface()

fps = 30
clock = pygame.time.Clock()

black = Color(0,0,0,0)
white = Color(255,255,255,255)

myboard = CheckerBoard((10, 10), (20, 20), (50, 50), (black, white), 4)
myboard.draw(screen, (width/4, height/4))

while True:
    clock.tick(fps)
    myboard.anim(screen, (width/4, height/4), fps)
    for event in pygame.event.get():
        if event.type == QUIT:
            sys.exit(0)

    pygame.display.flip()
