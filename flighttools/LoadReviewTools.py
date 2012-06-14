#!/usr/bin/python
'''
Process Matlab load review output files. This script is meant for two purposes:

1) Read in the propagation ending information and write a review schedule input
   file for MCC to read. This is done with this type of syntax:
   
   python LoadReviewTools.py --Propschedule=MAY0712A \
   --OutputPropEndingConfiguration

2) Read in both the propagation and review schdule output files and write a
   thermal loadreview report listing all the relevant temperature data. This
   is done with this type of syntax:

   python LoadReviewTools.py --Propschedule=MAY0712A --Reviewschdule=MAY1412A \
   --OutputThermalReport

'''

import sys
import os
import numpy as np
import argparse


class LoadReviewTools(object):

    def __init__(self, propschedule, reviewschedule=None):

        self.fileparts = {'psmc':'_1pdeaat_plot.txt',
                          'minusz':'_tephin_plot.txt',
                          'dpa':'_dpa_plot.txt',
                          'tank':'_pftank2t_plot.txt',
                          'mups':'_mups_valves_plot.txt'}

        self.headerinfo = {'psmc':{'columns':3,
                                   'names':['Time', '1PDEAAT', '1PIN1AT'],
                                   'title':'ACIS: PSMC'},
                           'minusz':{'columns':8,
                                     'names':['Time','TEPHIN', 'TCYLAFT6',
                                              'TMZP_MY', 'TCYLFMZM', 'TFSSBKT1',
                                              'Pitch', 'Roll'],
                                     'title':'Spacecraft: Minus-Z'},
                           'dpa':{'columns':9,
                                  'names':['Time','1DPAMZT', 'Pitch', 'Roll',
                                           'SimPos', 'FEP_Count', 'CCD_Count',
                                           'Vid_Board', 'Clocking'],
                                  'title':'ACIS: DPA'},
                           'tank':{'columns':6,
                                   'names':['Time', 'PFTANK2T', 'PFTANKIP',
                                            'PF0TANK2T', 'Pitch', 'Roll'],
                                   'title':'Spacecraft: Fuel Tank'},
                           'mups':{'columns':5,
                                   'names':['Time', 'PM1THV1T',
                                            'PM1THV1T Settle', 'PM2THV1T',
                                            'PM2THV1T Settle'],
                               'title':'Spacecraft: MUPS Valves'}}

        self.plotorder = ['minusz', 'tank', 'mups', 'psmc', 'dpa']

        self.propschedule = propschedule
        self.reviewschedule = reviewschedule

        if reviewschedule == None:
            writePropData(self.propschedule)
        else:
            writeChecklistData(self.propschedule,self.reviewschedule)


    def __readfile(filename,subheaderinfo):

        # Headerinfo should be a sub-dict of the original header info,
        # including only the information for the current model
            
        datalines = fin.readlines()
        fin.close()

        header = datalines.pop(0)

        data = {}

        for num,name in enumerate(subheaderinfo['names']):
            if name.lower() == 'time':
                data.update(dict({name:np.array([line.strip().split()[num]
                                                for line in datalines])}))
            else:
                data.update(dict({name:np.array(
                    [np.double(line.strip().split()[num])
                     for line in datalines])}))

        return data


    def __writeReportData(outfile,propdata,reviewdata,names,modelname):

        # The 'names' list should not include time

        outfile.write(('-'*79)+'\n')
        outfile.write('%s Report\n'%modelname)
        outfile.write(('-'*79)+'\n\n')

        outfile.write('Propagation:\n')
        outfile.write('------------\n')

        outfile.write('Start: %s\n'%(propdata['Time'][0]))

        for name in names:
            outfile.write(' %s: %f\n'%(name, propdata[name][0]))

        outfile.write('\nReviewed Schedule:\n')
        outfile.write('-------------------\n')

        outfile.write('Start: %s\n'%(reviewdata['Time'][0]))

        for name in names:
            outfile.write(' %s: %f\n'%(name, reviewdata[name][0]))

        outfile.write('\nMax Values:\n')

        for name in names:
            maxind = np.argmax(reviewdata[name])
            outfile.write(' %s: %f  (%s)\n'%(name, reviewdata[name][maxind],
                                           reviewdata['Time'][maxind]))

        outfile.write('\nEnd: %s\n'%(reviewdata['Time'][-1]))
        for name in names:
            outfile.write(' %s: %f\n'%(name, reviewdata[name][-1]))

        outfile.write('\n\n\n')

        return outfile


    def writeChecklistData(propschedule,reviewschedule):

        schedulename = os.path.basename(reviewschedule)
        outfile = file('%s_Thermal_Load_Review_Report.txt'%schedulename,'w')

        for name in plotorder:

            filename = propschedule+fileparts[name]
            propdata = __readfile(filename,headerinfo[name])

            filename = reviewschedule+fileparts[name]
            reviewdata = __readfile(filename,headerinfo[name])

            datanames = headerinfo[name]['names']
            datanames.pop(0)

            __writeReportData(outfile,propdata,reviewdata,datanames,
                              headerinfo[name]['title'])
            __writeReportData(sys.stdout,propdata,reviewdata,datanames,
                              headerinfo[name]['title'])

        outfile.close()
        print('Wrote thermal report data to '\
              '%s_Thermal_Load_Review_Report.txt\n'%reviewschedulename)
        

    def writePropData(propschedule):


        propnames = ['TEPHIN', '3TRMTRAT', 'PM1THV1T', 'PM2THV1T', '1PDEAAT',
                     '1PIN1AT', 'TCYLAFT6', 'TMZP_MY', 'TCYLFMZM', 'TFSSBKT1',
                     '1DPAMZT', 'PFTANK2T', 'PF0TANK2T', 'SimPos', 'chips',
                     'FEP_Count', 'CCD_Count', 'Vid_Board', 'Clocking']

        outfile = file(propschedule + '_Ending_Configuration.txt','w')

        for num,name in enumerate(plotorder):
            filename = propschedule+fileparts[name]
            propdata = __readfile(filename,headerinfo[name])

            datanames = headerinfo[name]['names'][1:]

            if num == 0:
                outfile.write('Time of Validity:  %s\n'%(propdata['Time'][-1]))

            for loc in datanames:
                if loc in propnames:
                    outfile.write(' %s : %f\n'%(loc, propdata[loc][-1]))


        outfile.close()
        print('Wrote propagation ending data to %s'%outfile)


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument('--Propschedule')
    parser.add_argument('--Reviewschedule')
    parser.add_argument('--OutputPropEndingConfiguration', action='store_true',
                        default=False)
    parser.add_argument('--OutputThermalReport', action='store_true',
                        default=False)

    args = vars(parser.parse_args())

    if args['OutputPropEndingConfiguration']:
        LoadReviewTools(propschedule=args['Propschedule'])

    if args['OutputThermalReport']:
        LoadReviewTools(propschedule=args['Propschedule'],
                        reviewschedule=args['Reviewschedule'])   
