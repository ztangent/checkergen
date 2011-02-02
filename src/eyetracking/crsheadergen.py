#! /usr/bin/env python

"""Simple script to generate Python-compatible CRS header file.

Generate header file containing CRS Video Eyetracker Toolbox constants
dynamically to avoid copyright concerns. Prompts user for location of
crsLoadConstants.m, which is then transcribed to CRS.py, with the
unnecessary portions stripped.

CRS and Video Eyetracker Toolbox are trademarks of Cambridge Research Systems.

"""

import os
import sys

mfilename = 'crsLoadConstants.m'
pyfilename = 'CRS.py'
default_path = os.path.normpath(\
"C:\Program Files\Cambridge Research Systems\
\CRS Toolbox for MATLAB\Tools\VSG\System\crsLoadConstants.m")
sep1 = "\
% *************************************\
****************************************\n\
% Video Eye Tracker Toolbox constants *\
****************************************\n\
% *************************************\
****************************************"
sep2 = "\
% *************************************\
****************************************\n\
% * CONSTANTS DEFINED IN VSGV8.h ******\
****************************************\n\
% *************************************\
****************************************"

def generate():

   print 'path to crsLoadConstants.m: (default: {0})'.format(default_path)
   path = raw_input()
   if path == '':
       # Default to standard Windows install path
       path = default_path
   else:
       path = os.path.normpath(path)
   print path
   if not os.path.isfile(path):
       sys.exit("path specified is not a file")
   elif os.path.basename(path) != mfilename:
       sys.exit("wrong filename, {0} expected".format(mfilename))

   # U flag for standardized newlines
   mfile = open(path, 'rU')
   mstr = mfile.read()
   mfile.close()

   # Actual text processing
   pystr = mstr.split(sep1)[1]
   pystr = sep1 + pystr
   pystr = pystr.split(sep2)[0]
   pystr = pystr.replace('%', '#')
   pystr = pystr.replace('CRS.', '')
   pystr = pystr.replace(';', '')

   # Remove leading whitespace
   pystrlist = pystr.splitlines()
   pystrlist = [line.strip() for line in pystrlist]
   pystr = '\n'.join(pystrlist)

   # Write out to file
   pyfile = open(pyfilename, 'w')
   pyfile.write(pystr)
   pyfile.close()

   print 'Done.'

if __name__ == '__main__':
   generate()
