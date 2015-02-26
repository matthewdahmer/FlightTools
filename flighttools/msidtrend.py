#!/usr/bin/python
""" Create an object to make rudimentary predictions for telemetry.
"""
import numpy as np
import sqlite3

import Ska.engarchive.fetch_eng as fetch_eng
import Chandra.Time as ct

import gretafun


class MSIDTrend(object):
    """ Create an object to make linear predictions for telemetry.

    ---------------------------------------------------------------------------
    This function is written to provide some tools to make basic predictions
    for telemetry using a linear curve fit through monthly data. 


    Author: Matthew Dahmer


    ---------------------------------------------------------------------------
    Requires one input argument:
    
    msid: This must be a valid msid name in the engineering telemetry archive


    ---------------------------------------------------------------------------
    Includes these optional keyword arguments:
    
    tstart: This must be a date that is a valid input argument for the
            Chandra.Time.DateTime object. If this is None, then the default
            action for the Chandra.Time.DateTime object is to use the current
            time, which would not make sense.
            
    tstop: Similar to tstart in that this must be a valid input argument for
           the Chandra.Time.DateTime object, however a value of None would
           make sense here as this is just the current time. If None is used
           then the telemetry queried from the engineering archive will include
           the most recent values available.

    trendmonths: This is the number of months counting backwards to use in
                 creating a trending prediction. Each month is assumed to be
                 30 days, so 'monthly' data are grabbed in 30 day chunks.

    numstddev: This is the number of standard deviations to use as a factor of
               safety when making a prediction of when the data will reach a
               limit. The distance of the monthly data used to generate a
               linear curve fit from that curve fit is used to generate the
               standard deviation. For more details on the definition of this
               standard deviation, please see the documentation for the Numpy
               std() function.

               
    ---------------------------------------------------------------------------
    Creates an object with these attributes:

    msid: This is the msid used to create the object.

    numstddev: See documentation above.

    trendmonths: See documentation above.

    tstart: See documentation above.

    tstop: See documentation above.    

    safetylimits: The database limits are replaced with the G_LIMMON limits if
                  the G_LIMMON limits are more permissive (which would only be
                  the case if the database limits are outdated). Only those
                  individual limits that are more permissive are replaced, not
                  the entire set. This object contains these updated limits.

    telem: Fetch data from the engineering telemetry archive, using the daily
           stats. Monthly telemetry is calculated and added to this object.

    getPolyfitLine: Returns the coefficients for the linear curve fit through
                    the last N months of data. The data is expected to be
                    either the monthly maximum, monthly minimum, or monthly
                    mean. Also returns the standard deviation of the data about
                    this curve fit.

    getPrediction: Return the prediction at one or more times for the requested
                   data.

    getLimitIntercept: Return the date when the data is expected to reach a
                       limit. See the documentation in the code below for more
                       details.
    """
    
    def __init__(self, msid, tstart='2000:001:00:00:00', tstop=None,
                 trendmonths = 24, numstddev=2, removeoutliers=True, 
                 maxoutlierstddev=5):

        self.msid = msid
        self.tstart = ct.DateTime(tstart).date
        
        if tstop == None:
            self.tstop = ct.DateTime().date
        else:
            self.tstop = ct.DateTime(tstop).date
            
        self.trendmonths = trendmonths
        self.numstddev = numstddev
        self.removeoutliers = removeoutliers
        self.maxoutlierstddev = maxoutlierstddev
        self.telem = self._getMonthlyTelemetry()
        self.safetylimits = gretafun.getSafetyLimits(self.telem)

        db = sqlite3.connect('/home/mdahmer/AXAFAUTO/G_LIMMON_Archive/glimmondb.sqlite3')
        cursor = db.cursor()
        cursor.execute('''SELECT a.msid, a.setkey, a.default_set, a.warning_low, 
                          a.caution_low, a.caution_high, a.warning_high FROM limits AS a 
                          WHERE a.active_set=1 AND a.setkey = a.default_set AND a.msid = ?
                          AND a.modversion = (SELECT MAX(b.modversion) FROM limits AS b
                          WHERE a.msid = b.msid and a.setkey = b.setkey)''', [msid.lower(),])
        lims = cursor.fetchone()
        self.trendinglimits = {'warning_low':lims[3], 'caution_low':lims[4], 'caution_high':lims[5], 
                 'warning_high':lims[6]}


    def filteroutliers(self, datavals):
        keep = np.abs(datavals - np.mean(datavals)) <= (np.std(datavals) * 
                                                        self.maxoutlierstddev)
        return keep

    def _getMonthlyTelemetry(self):
        """ Retrieve the telemetry and calculate the 30 day stats
        
        30 day stats start at the most recent time point, so there are likely
        to be a remainder of daily datapoints not used at the begining of the
        dataset
        """

        def returnmonthlyvals(datavals, numdays, keepmask):
            datavals = datavals[keepmask]
            returnvals = [np.m]

        
        telem = fetch_eng.Msid(self.msid, self.tstart, self.tstop, 
                               stat='daily')

        if self.removeoutliers:
            keepmean = self.filteroutliers(telem.means)
            keepmax = self.filteroutliers(telem.maxes)
            keepmin = self.filteroutliers(telem.mins)

        else:
            keepmean = np.array([True]*len(telem.means))
            keepmax = np.array([True]*len(telem.maxes))
            keepmin = np.array([True]*len(telem.mins))

        # Save this for future access outside of this function, you need to 
        # merge the keep arrays since they all share a common time array.
        keep = keepmean & keepmax & keepmin
        telem.keep = keep


        # Calculate the mean time value for each 30 day period going backwards.
        #
        # Monthly values are calculated going backwards because it is more
        # important to have a full month at the end than at the beginning since
        # recent data is more likely to reflect future trends than older data.
        #
        # Note that the hours used for each daily time value are 12pm.
        #
        # Determine monthly min, max, and mean values.
        #
        # Data is reported in chronological order
        #
        days = len(telem.times[keep])
        telem.monthlytimes = [np.mean(telem.times[keep][n:n + 30]) for n in
                              range(days - 30, 0, -30)]
        telem.monthlytimes.reverse()
        
        telem.monthlymaxes = [np.max(telem.maxes[keep][n:n + 30]) for n in
                              range(days - 30, 0, -30)]
        telem.monthlymaxes.reverse()
        
        telem.monthlymins = [np.min(telem.mins[keep][n:n + 30]) for n in
                              range(days - 30, 0, -30)]
        telem.monthlymins.reverse()

        telem.monthlymeans = [np.mean(np.double(telem.means[keep][n:n + 30])) 
                              for n in range(days - 30, 0, -30)]
        telem.monthlymeans.reverse()       

        return telem


    def getPolyfitLine(self, data):
        """ Return the linear curve fit and standard deviation for the data.
        
        Return the coefficients for the linear curve fit through
        the last N months of data. The data is expected to be either the
        monthly maximum, monthly minimum, or monthly mean.Also return the
        standard deviation of the data about this curve fit.

        The number of months used is specified using the trendmonths input
        argument.
        """

        # Select the last N months of data
        datarange = data[-self.trendmonths:]
        timerange = self.telem.monthlytimes[-self.trendmonths:]

        # Calculate the coefficients
        p = np.polyfit(timerange, datarange, 1)

        # Calculate the standard deviation of the fit.
        #
        # This is the standard deviation of the distance of the datapoints
        # from the curve fit (line).This standard deviation is intended to be
        # used as a simplistic measure of the variation of the data about the
        # fit line. Some multiple of this number may be used as a
        # "factor of safetly" when making predictions (such as when the
        # maximum value may reach a warning high limit).
        stddev = np.std(datarange - np.polyval(p, timerange))
        
        return (p, stddev)


    def getPrediction(self, date, maxminmean='max'):
        """ Return the prediction at one or more times for the requested data.

        The date passed into this function can be either a
        Chandra.Time.DateTime object, or a compatible input argument for a
        Chandra.time.DateTime class.

        The maxminmean input argument is case insensitive but must be one of
        three valid strings:
            min
            max
            mean
        """
        
        # Ensure the date is a date object (either a single or multiple
        # element object) and convert it to seconds
        date = ct.DateTime(date).secs

        # Return the coeficients and associated standard deviation for the
        # requested linear curve fit.
        if maxminmean.lower() == 'max':

            p, stddev =  self.getPolyfitLine(self.telem.monthlymaxes)

        elif maxminmean.lower() == 'min':

            p, stddev =  self.getPolyfitLine(self.telem.monthlymins)
            
        elif maxminmean.lower() == 'mean':

            p, stddev =  self.getPolyfitLine(self.telem.monthlymeans)

        return np.polyval(p, date)

    
    def getLimitIntercept(self, thresholdtype, limittype='safety'):
        """ Return the date when the data is expected to reach a limit.
        
        Valid values for thresholdtype are:
            warning_low
            caution_low
            caution_high
            warning_high
        """

        # Ensure the thresholdtype is lower case, since all such keys to the
        # safetylimits dict are lower case.
        thresholdtype = thresholdtype.lower()


        def getdate(self, p, stddev, thresholdtype, limittype):
            """ Return the date when the specified threshold is reached.

            p and stddev are the linear curve fit parameters and standard
            deviation output from getPolyfitLine.

            thresholdtype has three valid input strings:
                warning_low
                caution_low
                caution_high
                warning_high

            limittype has two valid input strings:
                safety
                trending

            There are two ways one can incorporate a safety factor, one is to
            modify the threshold, the other is to modify the linear curve fit.
            In this case the threshold is modified by either subtracting or
            adding a multiple of the standard deviation depending on the type of
            threshold the user is interested in.

            If there is a time when the threshold is reached, then a date
            string is returned, otherwise None is returned. Keep in mind that
            if None is input into a Chandra.Time.DateTime object, it returns
            the current time.
            """

            # Get the threshold value and include the appropriate safety factor
            if limittype.lower() == 'trending':
                if thresholdtype == 'warning_high' or \
                   thresholdtype == 'caution_high':

                    threshold = (self.trendinglimits[thresholdtype] - stddev *
                                 self.numstddev)
                else:
                    threshold = (self.trendinglimits[thresholdtype] + stddev *
                             self.numstddev) 
            else:
                if thresholdtype == 'warning_high' or \
                   thresholdtype == 'caution_high':

                    threshold = (self.safetylimits[thresholdtype] - stddev *
                                 self.numstddev)
                else:
                    threshold = (self.safetylimits[thresholdtype] + stddev *
                             self.numstddev)
                
            # Calculate the date at which the modified threshold is reached
            seconds = (threshold - p[1]) / p[0]
            if seconds < ct.DateTime('3000:001:00:00:00').secs:
                crossdate = ct.DateTime(seconds).date

            else:
                crossdate = '3000:001:00:00:00'

            return crossdate


        if thresholdtype == 'warning_high' or thresholdtype == 'caution_high':
            # If an upper limit threshold is used, then fit the line to the
            # monthly maximum data.

            p, stddev = self.getPolyfitLine(self.telem.monthlymaxes)
            
            # If an upper limit threshold is used, then there is no cross date
            # if the slope is negative.
            if p[0] > 0:

                crossdate = getdate(self, p, stddev, thresholdtype, limittype)
                
            else:

                crossdate = None
                print('Slope for %s is %e, so no %s limit cross'%
                      (self.msid, p[0], thresholdtype))


        if thresholdtype == 'warning_low' or thresholdtype == 'caution_low':
            # If a lower limit threshold is used, then fit the line to the
            # monthly minimum data.

            p, stddev = self.getPolyfitLine(self.telem.monthlymins)

            # If a lower limit threshold is used, then there is no cross date
            # if the slope is positive.
            if p[0] < 0: 
                
                crossdate = getdate(self, p, stddev, thresholdtype, limittype)

            else:

                crossdate = None        
                print('Slope for %s is %e, so no %s limit cross'%
                      (self.msid, p[0], thresholdtype))

        return crossdate
                                 

