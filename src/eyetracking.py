"""Provides support for CRS VideoEyetracker Toolbox."""

try:
    import win32com.client
    available = True
except ImportError:
    available = False

# COM ProgID of the Toolbox
ProgID = "crsVET.VideoEyeTracker"
# VET application object
VET = None

if available:
    # Try dispatching object, else unavailable
    try:
        VET = win32com.client.Dispatch(ProgID)
        VET = None
    except:
        available = False

if available:

    # For easier access to constants and standardization with MATLAB interface
    CRS = win32com.client.constants

    class EyetrackingError(Exception):
        """Raised when something goes wrong with VET."""

    def init(user_select = False, path = None):
        global VET
        try:
            VET = win32com.client.Dispatch(ProgID)
        except:
            msg = 'could not start VideoEyetracker Toolbox'
            raise EyetrackingError(msg)
        if user_select:
            if not VET.SelectVideoSource(CRS.vsUserSelect, ''):
                msg = 'could not select video source'
                raise EyetrackingError(msg)
        else if path != None:
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

    def calibrate():
        """Calibrate the subject."""
        VET.Calibrate()

    def start():
        """Start tracking the eye."""
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
        if not VET.CalibrationStatus()[0]:
            msg = 'subject not yet calibrated'
            raise EyetrackingError(msg)
        if VET.FixationLocation.Fixation:
            xdiff = abs(VET.FixationLocation.Xposition - fix_pos[0])
            ydiff = abs(VET.FixationLocation.Yposition - fix_pos[1])
            if (xdiff <= fix_range[0]/2) and (ydiff <= fix_range[1]/2):
                return True
        return False
