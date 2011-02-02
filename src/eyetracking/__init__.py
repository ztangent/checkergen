"""Provides support for CRS VideoEyetracker Toolbox."""

import win32com.client
try:
    import CRS
except ImportError:
    import crsheadergen
    crsheadergen.generate()
    import CRS
    del crsheadergen

vet = None
ProgID = "crsVET.VideoEyeTracker"

def init(source=CRS.vsHighSpeedCamera250):
    global vet
    vet = win32com.client.Dispatch(ProgID)
    vet.SelectVideoSource(source, '')
    vet.StartTracking()
    vet.CreateCameraScreen(0)
    
