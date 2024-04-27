
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

class Character(object):
    """ The character object within which each character will have 
    associated data stored within class attributes:
        name: character name
        stateID: assigned character StateID
        rank: current rank of character in roster
        position: current position of character in roster
        callsign: current callsign of character in roster
        callsign: current department of character in roster
        shift: current shift of character in roster

        logins: list of login events
        logouts: list of logout events
        strangeness: collection of timesheet events that don't match nicely
        loggedTime: total hours logged

        loggedIn: boolean toggle for timesheet analysis
    """
    def __init__(self, name: str, stateID: int = 0):
        # basic character information
        self.name: str    = name
        self.stateID: int = stateID
        
        # roster data
        self.rank:      str = ''
        self.position:  str = ''
        self.callsign:  str = ''
        self.department:str = ''
        self.shift:     str = ''
        #self.status:    str = ''
        
        # timesheet data
        self.loggedIn: bool = False
        self.logins  : list = []
        self.logouts : list = []
        self.strangeness: dict = {'crashes': [],
                                  'pre'    : [],
                                  'post'   : [],
                                  'other'  : []}
        self.loggedTime: float = 0  # units: hours
        self.shift1Time: float = 0  # units: hours
        self.shift2Time: float = 0  # units: hours
        self.shift3Time: float = 0  # units: hours
        self.hoursPerWeek = []      # will be an array of hours
        
        # PD incidents data
        self.incidents: list = []
        self.shift1Incidents: float = 0  # units: hours
        self.shift2Incidents: float = 0  # units: hours
        self.shift3Incidents: float = 0  # units: hours
        self.incidentsPerWeek: list = []

    def __str__(self):
        """
        """
        return f'{self.name}, {self.stateID}'

    def __repr__(self):
        """
        """
        return f'Character(\'{self.name}\', {self.stateID})'

    def analyzeTimeEvents(self):
        """ Use gathered login/out events from a timesheet to analyze hours
        worked per week, per shift, etc. Update class attribute values to stash
        results associated with each character. 
        """
        # do a check for actual data before running through the code
        if len(self.logins) == 0:
            print(f'No timesheet data has been collected for {self.name}.')
            return

        # get the first and last times the character signed on
        firsttime = self.logins[0]
        lasttime = self.logouts[-1]

        # define variables needed to calculate hours/incidents per week
        # defining a week as Monday to Sunday because that's what datetime does 
        # get midnight of the first Monday
        m = firsttime.date() - timedelta(days = firsttime.weekday())
        firstMonday = int(datetime.combine(m, 
                                           datetime.min.time()).strftime('%s'))
        # get midnight of the last Monday
        m = lasttime.date() + timedelta(days = 7-firsttime.weekday())
        lastMonday = int(datetime.combine(m,
                                          datetime.min.time()).strftime('%s'))
        # numpy array of week times in epoch time values
        weekBoundaries = np.arange(firstMonday,lastMonday, 604800)
        nWeeks = len(weekBoundaries) - 1
        self.hoursPerWeek = np.zeros(nWeeks)

        # define variables needed to calculate hours within shifts
        # hardcoded shift values, covers a 48 hr range of shifts to be used 
        # later
        boundaries = [pd.Timedelta(i,'h') for i in [-15,-7,1,9,17,25,33]]
        nShifts = len(boundaries)-1
        unit = pd.Timedelta(1,'h')

        # loop over all shifts (aka a pair of login and logout events)
        for i in range(0, min(len(self.logins),len(self.logouts))):
            # handling time worked per EST shift times
            # followed code from:
            # https://stackoverflow.com/questions/73997481/calculate-working-hours-time-python-pandas-hours-worked-total-hours-worked
            start_of_day = self.logins[i].normalize()
            work_time = [0] * nShifts
            for j, (lb, ub) in enumerate(zip(boundaries[:-1],boundaries[1:])):
                shift_st = start_of_day + lb
                shift_et = start_of_day + ub
                t = (min(self.logouts[i], shift_et) - max(self.logins[i], shift_st)) / unit
                work_time[j] = max(0,t)

            # add this login/logout event to shift counters
            self.shift1Time += work_time[0] # Shift 1 is 9 AM to 5 PM
            self.shift2Time += work_time[1] # shift 2 is 5 AM to 1 AM
            self.shift3Time += work_time[2] # shift 3 is 1 AM to 9 AM
            self.shift1Time += work_time[3] # Shift 1 is 9 AM to 5 PM
            self.shift2Time += work_time[4] # Shift 2 is 5 PM to 1 AM
            self.shift3Time += work_time[5] # shift 3 is 1 AM to 9 AM
        
            # handling time worked per EST weeks (Mon -> Sun)
            work_time = np.zeros(nWeeks)
            for j, (lb, ub) in enumerate(zip(weekBoundaries[:-1],
                                             weekBoundaries[1:])):
                t = min(int(self.logouts[i].strftime('%s')),ub) - max(int(self.logins[i].strftime('%s')),lb)
                work_time[j] = max(0,t)

            self.hoursPerWeek += work_time
        self.hoursPerWeek /= 3600
        
        # loop over all incidents
        self.incidentsPerWeek = np.zeros(nWeeks)
        for i in range(len(self.incidents)):
            # get epoch time of the incident report
            reportTime = self.incidents[i][1].timestamp()
            # loop over weeks to get incidents per week values
            for j, (lb, ub) in enumerate(zip(weekBoundaries[:-1],
                                             weekBoundaries[1:])):
                # check if the reportTime is between the bounds
                if reportTime >= lb and reportTime < ub:
                    self.incidentsPerWeek[j] += 1

            # handling incidents started per EST shift times
            start_of_day = datetime.combine(self.incidents[i][1].date(),
                                            datetime.min.time()) 
            work_time = [0] * nShifts
            for j, (lb, ub) in enumerate(zip(boundaries[:-1],boundaries[1:])):
                shift_st = (start_of_day + lb).timestamp()
                shift_et = (start_of_day + ub).timestamp()
                if reportTime >= shift_st and reportTime < shift_et:
                    work_time[j] += 1

            # add this incident to shift counters
            self.shift1Incidents += work_time[0] # Shift 1 is 9 AM to 5 PM
            self.shift2Incidents += work_time[1] # shift 2 is 5 AM to 1 AM
            self.shift3Incidents += work_time[2] # shift 3 is 1 AM to 9 AM
            self.shift1Incidents += work_time[3] # Shift 1 is 9 AM to 5 PM
            self.shift2Incidents += work_time[4] # Shift 2 is 5 PM to 1 AM
            self.shift3Incidents += work_time[5] # shift 3 is 1 AM to 9 AM
       

