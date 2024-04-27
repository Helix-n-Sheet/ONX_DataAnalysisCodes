
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import difflib
import re

import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.patches import Rectangle
from matplotlib.collections import PatchCollection

from character import Character

####
# Functions
####

def check_names(name,characters_dict,verbose=True):
    """do a check for name within the character dict
    """
    # no need to do any checks if dict is empty
    if len(characters_dict.keys()) == 0:
        return name
    
    # check if a name is not present in the dict; then check for similar
    # names
    if not characters_dict.get(name):
        # due to some unexpected characters in names or weird parsing errors, 
        # do a similarity check against all character names already in the 
        # character dict. if similarity is gt 0.6, assign the character name
        for char_name in characters_dict.keys():
            if difflib.SequenceMatcher(None,
                                       name,
                                       char_name).ratio() > 0.9:
                if verbose:
                    print(f'Mapped to {name} -> {char_name}. Does this look right?')
                return char_name
            elif difflib.SequenceMatcher(None,
                                         name,
                                         char_name).ratio() > 0.75:
                if verbose:
                    print(f'Not mapping {name} -> {char_name}. Maybe I should be though?')
                continue

    # whether present or no similar names are in the dict, return the original 
    # name
    return name


####
# Classes
####
class Roster():
    def __init__(self, charactersDict, rosterPath):
        self.rosterPath: str = str(rosterPath)
        self.characters: dict = charactersDict

    def __str__(self):
        """
        """
        return f'Roster pulled from {self.rosterPath}'

    def parseRoster(self):
        # load excel file
        xls = pd.ExcelFile(self.rosterPath)
        # then parse it
        df = xls.parse()
        # fill in values that are empty
        df['StateID'] = df['StateID'].fillna(-9999)
        # loop over entries in df
        for i in range(len(df.Name)):
            # there's possible weirdness in the sheet
            if not df.Name[i] or type(df.Name[i]) != str:
                continue
            
            # grab the essential information
            name = df.Name[i]
            stateID = int(df.StateID[i])
            
            # remove non-alphanumeric characters that might not be caught by 
            # the various parsers being used
            name = ' '.join(re.findall(r'(\w+)',name))
            name = check_names(name, self.characters)
            # grab the character's object from the character dict or make a 
            # new one
            char = self.characters.get(name,Character(name,stateID))

            # possible information in a roster file
            # NOTE: currently developed for the PD Roster only
            if df.Rank[i]:
                char.rank = df.Rank[i]
            if df.Position[i]:
                char.position = df.Position[i]
            if df.Callsign[i]:
                char.callsign = df.Callsign[i]
            if df.Department[i]:
                char.department = df.Department[i]
            if df.Shift[i]:
                char.shift = df.Shift[i]
            #if df.Status[i]:
            #    char.status = df.Status[i]

            self.characters[name] = char


class Timesheet():
    """ The timesheet object within which login/out events are gathered per 
    character and stashed. Total time logged is calculated.  
    """
    def __init__(self, characters_dict: dict, timesheet_path):
        self.timesheetPath: str = str(timesheet_path)
        self.timesheetString: str = ''
        self.characters: dict = characters_dict
        self.displayedCharacters = []
        self.firsttime = 0
        self.lasttime  = 0

    def __str__(self):
        return f'Timesheet pulled from {self.timesheetPath}'

    def parseTimesheet(self):
        # load excel file
        xls = pd.ExcelFile(self.timesheetPath)
        # then parse it:
        # Data headers happen on row 3
        # column 1 is Time data from unknown timezones, so skip it
        df = xls.parse(skiprows=3, skipcolumns=1)
        # there may be instances where a state id is not recorded in the 
        # timesheet document
        df['State ID'] = df['State ID'].fillna(-9999)
        # get first and last times
        self.firsttime = df['Time'].min()
        self.lasttime = df['Time'].max()

        # get character names and stateIDs dataframe
        chars = df[['State ID', 'Name']].drop_duplicates()
        # create the character objects within the character dict
        # and
        # gather name mapping from sheet names to dict names
        mapping = {}
        for char in chars.values:
            # there's possible weirdness in the sheet
            if not char[1] or type(char[1]) != str:
                continue
            
            # grab the essential information
            name = char[1]
            stateID = int(char[0])

            # remove non-alphanumeric characters that might not be caught by 
            # the various parsers being used
            abbrev_name = ' '.join(re.findall(r'(\w+)',name))
            mapping[name] = abbrev_name
            name = check_names(abbrev_name, self.characters) #, verbose=False
            # if not already present, create a new character and assign it to 
            # the character dict
            if not self.characters.get(name):
                self.characters[name] = Character(name,stateID)

        # loop over all events
        for i in range(len(df.Action)):
            # if the name is non-existant or weirdly formatted, SKIP
            if not df.Name[i] or type(df.Name[i]) != str:
                continue
            # otherwise, the mapping of sheet name and dict name is in mapping
            name = mapping[df.Name[i]]
            
            # grab the character object
            char = self.characters[name]

            # check for normal check in event
            if df.Action[i] == 'Check In' and not char.loggedIn:
                char.logins.append(df.Time[i])
                char.loggedIn = True
            # check for normal check out event
            elif df.Action[i] == 'Check Out' and char.loggedIn:
                char.logouts.append(df.Time[i])
                char.loggedIn = False
                # this logout event is paired with the latest observed login 
                # event so we can calculate time without re-looping.
                # .timestamp() outputs epoch time, 
                # divide by 3600 to get difference in units of hours
                char.loggedTime += (char.logouts[-1].timestamp() - char.logins[-1].timestamp())/3600
            # capture instance where the player checks in while already
            # checked in; likely happening when a crash happens
            elif df.Action[i] == 'Check In' and char.loggedIn:
                char.strangeness['crashes'].append(list(df.iloc[i]))
            # capture instances where the player checked in _before_ the 
            # time period of the CSV
            elif df.Action[i] == 'Check Out' and not char.loggedIn:
                char.strangeness['pre'].append(list(df.iloc[i]))
            # other instances. 
            else:
                char.strangeness['other'].append(list(df.iloc[i]))

        # check if anyone was still logged on at the end of the time period
        for orig, name in mapping.items():
            # get their Character object
            char = self.characters[name]
            # having looped over all events, check if they remain logged in; if
            # so, then add to the log of strangeness
            if char.loggedIn:
                chardf = df[df.Name == orig]
                char.strangeness['post'].append(chardf.iloc[-1])

        # sort the characters by max time
        charList = [[self.characters[char].name,self.characters[char].loggedTime] for char in self.characters.keys()]
        charList.sort(key = lambda x: x[1], reverse=True)
        # loop over all characters
        for name, timelogged in charList:
            # get their Character object
            char = self.characters[name]
            if char.loggedTime > 0:
                self.timesheetString +=  f"{char.loggedTime:17.2f}     {char.name}\n"
                self.displayedCharacters.append(char.name)

        self.displayedCharacters.sort()
        self.displayedCharacters.insert(0, "Overview")

    def getCharacterData(self, characterSelection):
        if characterSelection == 'Overview':
            return self.timesheetString
        else:
            output = ""
            for name in self.characters.keys():
                # get their Character object
                char = self.characters[name]
                if char.name in characterSelection:
                    output += "{} - clocked time: {}".format(char.name, str(char.loggedTime).rjust(17)) + '\n\n'
                    for i in range(0, min(len(char.logins),len(char.logouts))):
                        output +=  "in: {}  -  out: {}".format(str(char.logins[i]),str(char.logouts[i])) + '\n'
            return output

    def createGanttChart(self, 
                         fig_name = 'gantt_chart.png', 
                         ylim = (-0.1,10.1)):
        """
        """
        figure = plt.figure(figsize=(16,8))
        ax = plt.gca()
        begTime = self.firsttime.timestamp()
        endTime = self.lasttime.timestamp() - begTime

        ax.plot([0,0],[-1,len(self.characters)+1], 'r-', zorder=3)
        ax.plot([endTime,endTime],[-1,len(self.characters)+1], 'r-', zorder=3)

        # sort the characters by max time
        charList = [[self.characters[char].name,self.characters[char].loggedTime] for char in self.characters.keys()]
        charList.sort(key = lambda x: x[1], reverse=True)
        # loop over all characters
        for i, (name, timelogged) in enumerate(charList):
            char = self.characters[name]
            # get the name
            name = char.name
            # get the facecolor to draw the rectangles with
            drawColor = list(mpl.colors.XKCD_COLORS.keys())[2**i % 949]
            # loop over all paired events
            for j in range(0,min(len(char.logins),len(char.logouts))):
                # get epoch times for the log in/out event
                st = char.logins[j].timestamp()
                et = char.logouts[j].timestamp()
                # create the rectangle drawing object
                rect = Rectangle((st - begTime, i + 0.1), # (x,y)
                                 (et - st),               # width
                                 0.8,                     # height
                                 facecolor=drawColor,
                                 alpha=0.75,
                                 edgecolor='xkcd:black',
                                 zorder=3)
                # add rectangle object to the canvas
                ax.add_patch(rect)

        # setting y-axis ticks and labels
        ax.set_yticks(np.arange(len(charList))+0.5,
                        [char[0] for char in charList])
        ax.set_ylim(ylim)

        # process to get x-axis ticks and labels
        startDate = self.firsttime.date()
        endDate =   self.lasttime.date()
        delta = endDate - startDate
        days = [startDate+timedelta(days=i) for i in range(delta.days + 1)]
        midnights = [int(datetime.combine(day, datetime.min.time()).strftime('%s')) - begTime for day in days]
        ax.xaxis.set_major_formatter(mpl.dates.DateFormatter('%m-%d'))
        ax.set_xticks(midnights, labels = days)
        ax.tick_params(axis='x',pad = -1.)
        for label in ax.get_xticklabels(which='major'):
            label.set(rotation=-45,horizontalalignment='left',size='small')
        ax.set_xlim((-endTime*0.01, endTime*1.01))

        # add grid lines for aiding the eye
        plt.grid(axis='y',visible=True,which='major',
                 color='#808080',linestyle='--',alpha=0.75,zorder=1)
        plt.grid(axis='x',visible=True,which='major',
                 color='#808080',linestyle='--',alpha=0.75,zorder=1)

        plt.tight_layout()
        plt.savefig(fig_name, dpi = 300, transparent = True)


class IncidentReport():
    """
    """
    def __init__(self, charactersDict, incidentPath):
        self.incidentPath: str = str(incidentPath)
        self.characters: dict = charactersDict

    def __str__(self):
        """
        """
        return f'Incidents pulled from {self.incidentPath}'

    def parseIncidents(self):
        # load excel file
        xls = pd.ExcelFile(self.incidentPath)
        # then parse it
        df = xls.parse('_Incidents')
        self.incidents = df

        # create the character objects within the character dict
        # and
        # gather name mapping from sheet names to dict names
        # loop over all incidents using indices
        for i in range(len(df.Involved)):
            # grab all names listed in the incident row
            try:
                involved_names = df.Involved[i].split(',')
            except:
                involved_names = []
            names = list(set([df.StartedBy[i]] + involved_names))

            # loop over all character names associated with the incident
            for name in names:
                # remove non-alphanumeric characters that might not be caught
                # by the various parsers being used
                abbrev_name = ' '.join(re.findall(r'(\w+)',name))
                name = check_names(abbrev_name, self.characters)
                # if not already present, create a new character and assign it
                # to the character dict
                if not self.characters.get(name):
                    self.characters[name] = Character(name,0)

                incidentDate = datetime.strptime(df.Date[i],'%Y-%m-%d %H:%M:%S')
                self.characters[name].incidents.append([df.IncidentNr[i],
                                                        incidentDate])


