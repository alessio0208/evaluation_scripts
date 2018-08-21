#!/usr/bin/env python

# Merges Subpages for eval and adjusts class naming accordingly
# Prepares file for regular easy.py evaluation

import sys
import os

import random, glob
try:
    from natsort import natsorted
except:
	print('You need natsort! (pip install natsort)')
	sys.exit()

###### CONFIG ###### 
# How the "temporary" output and result is named 
scenario = 'allSubPages'
# Should the main page be used? (Training in each fold)
main = True
if main:
	scenario = scenario + '_main'
# Input directory
inputpath = os.getenv('dir_TEMP')+'wsc_features/'
# Input format
form = 'TCP'
# Should the input be randomized?
shuffle = False
####################

merged_file = inputpath + '/' + scenario + '_' + form
info_file = inputpath + '/' + 'list_' + scenario[0].lower() + scenario[1:] + '_' + form + '.txt'

# Merge input files
fout = open(merged_file, 'w')
finfo = open(info_file, 'w')
site = 1
for filename in natsorted(glob.glob(inputpath+'wsc*_'+form)):
        print filename
	fin = open(filename,'r')
	_, info = os.path.split(filename)
	#last = 0
	for line in fin:
		fout.write(str(site) + ' ' + line.split(' ', 1)[-1])
		#if int(line.split()[0]) != last:
			#fout.write(str(site) + ' ' + line.split(' ', 1)[-1])
			#last = int(line.split()[0])
	fin.close()
	finfo.write(info+'\n')
	site += 1
fout.close()
finfo.close()

if main:
	fin = open(inputpath + '/mainPages_' + form, 'r')
	fout = open(merged_file, 'a')
	for line in fin:
		fout.write(line)
	fout.close()
	fin.close()

