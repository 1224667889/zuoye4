import re

#by mirrorlied 2020/2/24
import datetime

def redatetime(date):
    try:        
    	datetime.datetime.strptime(date, '%Y-%m-%d %H:%M:%S')        
    	return date
    except ValueError:        
    	return 0

def redate(date):
    try:        
    	datetime.datetime.strptime(date, '%Y-%m-%d')        
    	return date 
    except ValueError:        
    	return 0 
