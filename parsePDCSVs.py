
import sys
import numpy as np
import pickle
import parsers, character

# MAIN
if __name__ == '__main__':
    timesheet_file = sys.argv[1]
    roster_file = sys.argv[2]
    incidents_file = sys.argv[3]
    
    timesheet = parsers.Timesheet({}, 'PD_Data/PDHoursMar1Apr20.xlsx')
    timesheet.parseTimesheet()

    characters = timesheet.characters

    roster = parsers.Roster(characters, 'PD_Data/PDRoster.xlsx')
    roster.parseRoster()

    incidents = parsers.IncidentReport(characters, 'PD_Data/Incidents.xlsx')
    incidents.parseIncidents()

    with open(timesheet_file.split('.')[0] + '_overview.csv','w') as outcsv:
        outcsv.write('Name,CID,Department,Rank,Time Worked (hrs),Shift 1 (hrs),Shift 2 (hrs),Shift 3 (hrs),Worked per Week (hrs),Stdev (hrs),Total Incidents,Shift 1 Inc,Shift 2 Inc,Shift 3 Inc,Average per Week (Inc),Stdev (Inc)\n')
        
        # sort the characters by max time
        charList = [[characters[char].name,characters[char].loggedTime] for char in characters.keys()]
        charList.sort(key = lambda x: x[1], reverse=True)
        for (name,loggedtime) in charList:
            char = characters[name]
            char.analyzeTimeEvents()
            outcsv.write(f"{char.name},{char.stateID},{char.department},{char.rank},{char.loggedTime},{char.shift1Time},{char.shift2Time},{char.shift3Time},{np.mean(char.hoursPerWeek[1:-1])},{np.std(char.hoursPerWeek[1:-1])},{len(char.incidents)},{char.shift1Incidents},{char.shift2Incidents},{char.shift3Incidents},{np.mean(char.incidentsPerWeek[1:-1])},{np.std(char.incidentsPerWeek[1:-1])}\n")
    
    #timesheet.createGanttChart(fig_name = timesheet_file.split('.')[0] 
    #                                            + '_ganttchart.png',
    #                           ylim = (-0.1,50.1)) 
#   #                            ylim = (-0.1, len(timesheet.characters)+0.1))


    with open(timesheet_file.split('.')[0] + '_analysis_results.pkl','wb') as outpkl:
        pickle.dump([timesheet,roster,incidents,characters], outpkl)


