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

   python loadreviewtools.py --Propschedule=MAY0712A --Reviewschedule=MAY1412A \
   --OutputThermalReport

NOTE: This is meant to be run from within the working directory
'''

import sys
import os
import numpy as np
import argparse
import glob


class LoadReviewTools(object):

    def __init__(self, propschedule, reviewschedule=None):

        self.fileparts = {'psmc':'_1pdeaat_plot.txt',
                          'minusyz':'_tephin_plot.txt',
                          'dpa':'_dpa_plot.txt',
                          'tank':'_pftank2t_plot.txt',
                          'aca':'_aca_plot.txt',
                          'mups':'_mups_valves_plot.txt',
			  'oba':'_4rt700t_plot.txt'}

        self.headerinfo = {'psmc':{'columns':3,
                                   'names':['Time', '1PDEAAT', 'PIN1AT'],
                                   'title':'ACIS: PSMC'},
                           'minusyz':{'columns':8,
                                     'names':['Time','TEPHIN', 'TCYLAFT6',
                                              'TMZP_MY', 'PMTANK3T', 
                                              'TCYLAFT6_0', 'PMTANK3T_0',
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
                           'aca':{'columns':5,
                                   'names':['Time', 'AACCCDPT', 'ACA0',
                                            'Pitch', 'Roll'],
                                   'title':'Spacecraft: Fuel Tank'},
                           'mups':{'columns':5,
                                   'names':['Time', 'PM1THV1T',
                                            'PM1THV1T Settle', 'PM2THV1T',
                                            'PM2THV1T Settle'],
                                   'title':'Spacecraft: MUPS Valves'},
                           'oba':{'columns':5,
                                   'names':['Time', '4RT700T',
                                            '4RT700T_0', 'Pitch',
                                            'Roll'],
                                   'title':'OBA: Forward Bulkhead'}}
        
        self.propnames = ['TEPHIN', 'PM1THV1T', 'PM2THV1T','1PDEAAT', 
                          'PIN1AT', 'TCYLAFT6', 'TCYLAFT6_0', 'TMZP_MY', 
                          'PMTANK3T', 'PMTANK3T_0', '1DPAMZT', 'PFTANK2T',
                          'PF0TANK2T', 'SimPos', 'chips', 'FEP_Count',
                          'CCD_Count', 'Vid_Board', 'Clocking', 'AACCCDPT',
                          'ACA0', '4RT700T', '4RT700T_0']
        
        self.plotorder = ['minusyz', 'oba', 'tank', 'mups', 'psmc', 'dpa', 'aca']

        self.propschedule = propschedule
        self.reviewschedule = reviewschedule

        if reviewschedule == None:
            self.writePropData()
        else:
            self.writeChecklistData()


    def _readfile(self, filename, subheaderinfo):

        # Headerinfo should be a sub-dict of the original header info,
        # including only the information for the current model
        
        fin = open(filename,'rb')    
        datalines = fin.readlines()
        fin.close()

        header = datalines.pop(0)

        data = {}

        for num, name in enumerate(subheaderinfo['names']):
            if name.lower() == 'time':
                data.update(dict({name:np.array([line.strip().split()[num]
                                                for line in datalines])}))
            else:
                data.update(dict({name:np.array(
                    [np.double(line.strip().split()[num])
                     for line in datalines])}))

        return data


    def _writeReportData(self, outfile, propdata, reviewdata, names, modelname):

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


    def writeChecklistData(self):

        reviewfilename = self.reviewschedule + '_Thermal_Load_Review_Report.txt'
        outfile = file(reviewfilename, 'w')

        for name in self.plotorder:

            filename = self.propschedule + self.fileparts[name]
            propdata = self._readfile(filename, self.headerinfo[name])

            filename = self.reviewschedule + self.fileparts[name]
            reviewdata = self._readfile(filename, self.headerinfo[name])

            datanames = self.headerinfo[name]['names']
            datanames.pop(0) # remove time

            self._writeReportData(outfile, propdata, reviewdata, datanames,
                                  self.headerinfo[name]['title'])
            self._writeReportData(sys.stdout, propdata, reviewdata, datanames,
                                  self.headerinfo[name]['title'])

        outfile.close()
        print('Wrote thermal report data to '\
              '%s_Thermal_Load_Review_Report.txt\n'%reviewfilename)
        

    def writePropData(self):

        propfilename = self.propschedule + '_Ending_Configuration.txt'
        outfile = file(propfilename, 'w')

        for num,name in enumerate(self.plotorder):
            filename = self.propschedule + self.fileparts[name]
            propdata = self._readfile(filename, self.headerinfo[name])

            datanames = self.headerinfo[name]['names'][1:]

            if num == 0:
                outfile.write('Time of Validity:  %s\n'%(propdata['Time'][-1]))

            for loc in datanames:
                if loc in self.propnames:
                    outfile.write(' %s : %f\n'%(loc, propdata[loc][-1]))


        outfile.close()
        print('Wrote propagation ending data to %s'%propfilename)


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

    # Copy files to parent directory
    for file in glob.glob(args['Reviewschedule'] + '*'):
        os.link(file, '../' + file)
    
