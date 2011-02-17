"""Provides support for CRS VideoEyetracker Toolbox."""

import os.path

try:
    import win32com.client
    available = True
except ImportError:
    available = False

# COM ProgID of the Toolbox
ProgID = "crsVET.VideoEyeTracker"
# VET application object
VET = None

class EyetrackingError(Exception):
    """Raised when something goes wrong with VET."""
    pass

if available:
    # Try dispatching object, else unavailable
    try:
        VET = win32com.client.Dispatch(ProgID)
    except:
        available = False

if available:

    # For easier access to constants and standardization with MATLAB interface
    CRS = win32com.client.constants

    def select_source(user_select = False, path = None):
        if user_select:
            if not VET.SelectVideoSource(CRS.vsUserSelect, ''):
                msg = 'could not select video source'
                raise EyetrackingError(msg)
        elif path != None:
            # Open from file
            if not VET.SelectVideoSource(CRS.vsFile, path):
                msg = 'could not use path as video source'
                raise EyetrackingError(msg)            
        else:
            # Default to 250 Hz High Speed Camera
            if not VET.SelectVideoSource(CRS.vsHighSpeedCamera250, ''):
                msg = 'could not select video source'
                raise EyetrackingError(msg)

    def show_camera():
        VET.CreateCameraScreen(0)

    def quit_camera():
        VET.DestroyCameraScreen()
        
    def setup(viewing_distance, screen_dims,
              fixation_period = None, fixation_range = None):
        """Calibrates the display and sets fixation properties."""
        if len(screen_dims) != 2:
            msg = 'screen_dims must be a 2-tuple'
            raise ValueError(msg)
        VET.SetDeviceParameters(CRS.deUser, viewing_distance,
                                screen_dims[0], screen_dims[1])
        if fixation_period != None:
            VET.FixationPeriod = fixation_period
        if fixation_range != None:
            VET.FixationRange = fixation_range

    def calibrate(path = None):
        """Calibrate the subject.
           Optionally supply a path with no spaces to a 
           calibration file to load."""
        if path == None:
            if not VET.Calibrate():
                msg = 'calibration failed'
                raise EyetrackingError(msg)
        else:
            if not os.path.isfile(path):
                msg = 'specified file does not exist'
                raise EyetrackingError(msg)
            if not VET.LoadCalibrationFile(path):
                msg = 'file could not be loaded'
                raise EyetrackingError(msg)

    def start():
        """Start tracking the eye."""
        if VET.CalibrationStatus()[0] == 0:
            msg = 'subject not yet calibrated'
            raise EyetrackingError(msg)
        VET.ClearDataBuffer()
        VET.StartTracking()

    def stop():
        """Stop tracking the eye."""
        VET.StopTracking()

    def fixating(fix_pos, fix_range):
        """Checks whether subject is fixating on specificied location.

        fix_pos -- (x, y) position of desired fixation location in mm
        from center of screen

        fix_range -- (width, height) of box surrounding fix_pos within
        which fixation is allowed (in mm)

        """
        if VET.CalibrationStatus()[0] == 0:
            msg = 'subject not yet calibrated'
            raise EyetrackingError(msg)
        if VET.FixationLocation.Fixation:
            xdiff = abs(VET.FixationLocation.Xposition - fix_pos[0])
            ydiff = abs(VET.FixationLocation.Yposition - fix_pos[1])
            if (xdiff <= fix_range[0]/2) and (ydiff <= fix_range[1]/2):
                return True
        return False
