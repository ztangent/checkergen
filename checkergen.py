import os, sys
import pygame
from pygame.locals import *
pygame.init()

size = width, height = 800, 600
window = pygame.display.set_mode(size)
pygame.display.set_caption('checkergen')
screen = pygame.display.get_surface()
clock = pygame.time.Clock()

pygame.draw.rect(screen, Color(255,255,255), (200,150,400,300))

while True:
    clock.tick(60)
    for event in pygame.event.get():
        if event.type == QUIT:
            sys.exit(0)

    pygame.display.flip()
    
