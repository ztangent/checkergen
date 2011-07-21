"""Utility functions and classes."""

import os
import time
import math
from decimal import *
from itertools import *

def numdigits(x):
    """Returns number of digits in a decimal integer."""
    if x == 0:
        return 1
    elif x < 0:
        x = -x
    return int(math.log(x, 10)) + 1

def public_dir(obj):
    """Returns all 'public' attributes of an object"""
    names = dir(obj)
    for name in names[:]:
        if name[0] == '_' or name[-1] == '_':
            names.remove(name)
    return names

def to_bool(s,
            y_words=['t','y','1','True','true','yes','Yes'],
            n_words=['f','n','0','False','false','no','No']):
    """Converts certain strings to True or False."""
    if str(s) in y_words:
        return True
    elif str(s) in n_words:
        return False
    else:
        msg = 'Invalid true/false keyword'
        raise ValueError(msg)

def to_decimal(s):
    """ValueError raising Decimal converter."""
    try:
        return Decimal(s)
    except (InvalidOperation, TypeError):
        try:
            return Decimal(str(s))
        except (InvalidOperation, TypeError):
            raise ValueError

def to_color(s, sep=','):
    """Tries to cast a string to a color (3-tuple)."""
    c = tuple([int(x) for x in s.split(sep)])
    if len(c) != 3:
        raise ValueError
    return c

def to_list(s, sep=',', typecast=None):
    """Cast comma separated values to a list."""
    l = s.split(sep)
    if typecast != None:
        l = [typecast(i) for i in l]
    return l

def cyclic_permute(sequence):
    """Return a list of all cyclic permutations of supplied sequence."""
    n = len(sequence)
    return [[sequence[i - j] for i in range(n)] for j in range(n, 0, -1)]

# From itertools documentation
def grouper(iterable, n, fillvalue=None):
    """grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"""
    args = [iter(iterable)] * n
    return izip_longest(fillvalue=fillvalue, *args)

class Timer:
    """High-res timer that should be cross-platform."""
    def __init__(self):
        # Assigns appropriate clock function based on OS
        if os.name == 'nt':
            self.clock = time.clock
            self.clock()
        elif os.name == 'posix':
            self.clock = time.time
        self.running = False
        
    def start(self):
        self.start_time = self.clock()
        self.running = True

    def stop(self):
        if not self.running:
            return None
        self.stop_time = self.clock()
        self.running = False
        return self.stop_time - self.start_time

    def elapsed(self):
        if not self.running:
            return None
        cur_time = self.clock()
        return cur_time - self.start_time

    def restart(self):
        old_start_time = self.start_time
        self.start_time = self.clock()
        self.running = True
        return self.start_time - old_start_time

    def tick(self, fps):
        """Limits loop to specified fps. To be placed at start of loop."""
        fps = float(fps)
        ret = self.elapsed()
        if self.elapsed() != -1:
            while self.elapsed() < (1.0 / fps):
                pass
        self.start()
        if ret != -1:
            return ret * 1000
