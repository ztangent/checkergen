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
    vet = win32com.client.Dispatch(ProgID)
    vet.SelectVideoSource(source, '')
    vet.CreateCameraScreen(0)
    
def calibrate():
    vet.Calibrate()

# def check():
# use either vet.GetFixationLocation or vet.GetLatestEyePosition

def start():
    vet.ClearDataBuffer()
    vet.StartTracking()

def stop():
    vet.StopTracking()
