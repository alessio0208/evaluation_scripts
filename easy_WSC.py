#!/usr/bin/env python

# easy.py adaption for k-fold evaluation of WSC with independent testing and training
# Splits websites into k-partitions and uses k-1 partitions for training and k for testing 
# Perform k-fold evaluation
# 	performs grid.py (internal k-fold CV) on each fold's training data to find parameters
# 	trains a model with the best parameters for each fold's training data
# 	use each fold's testing data to predict the results with the corresponding model
# Merge prediction results of all k-folds into a single result
#
# each wsc_file has to have a different label for each page: 1..n

# you should have a non-patched (no prediction output) svm-train executable as svm-train-q
# svm-predict and grid.py have to be patched

from __future__ import division # for division
from subprocess import *
from datetime import datetime
import sys, os, random, glob, multiprocessing
try:
    from natsort import natsorted
except:
	print('You need natsort! (pip install natsort)')
	sys.exit()
try:
	import tldextract
except:
	print('You need tldextract! (pip install tldextract)')
	sys.exit()

def exit_with_help(error=''):
    print("""\
Usage: easy_WSC.py [options]

options:
   -in { /Path/ } : Path to WSC Instances 
                   (Each File a Single Website in CW Format)
                   (Corresponding Main Pages in a Single File in CW Format)
   -out { /Path/ } : Path to Output Files
   -name { Name } : Specify Output Filename
   -storage { Low | RemoveTemp | High } : Specify Storage Capacity
   -q : Quiet Mode (no Outputs)
   
   -format  { TCP | TLS | TLSLegacy | TLSNoSendme | 
              Cell | CellNoSendme } : Evaluated  Format (default Cell)
   -mainpages { YES | NO } : Use Mainpages for Training (default YES)
   -quickCV { YES | NO } : Execute grid.py once, not for every Fold (default YES)
   -randomInstances { YES | NO } : Shuffle Instances of each Page, not Site (!) (default NO)
   -randomSubpages { YES | NO } : Shuffle Subpages of each Site (default NO)
   -setting { CW | OW } : Evaluated Scenario (default CW)
   -simple { YES | NO } : Do not use Imaginary Classes (default YES)
*  -background { Name } : Filename of Background Instances
*  -separateEvaluation { YES | NO } : Evaluate each Website Independently (default NO)
*  -limitWebsites { website1,...,websiteN } : Evaluate Websites with specified indicies (Only in Separate Evaluation)
   -limitInstances { #subpages,#mainpages,#background } : Limit Instances that are Processed (-1 for default)
   -limitSubpages { #subpages } : Limit Subpages used for each Website
   
   -svm { /Path/ } : Path to libSVM binaries
   -gnuplot { /Path/Executable | null} : Path to gnuplot
   -log2c { begin,end,step | null } : set the range of c (default -5,15,2)
   -log2g { begin,end,step | null } : set the range of g (default 3,-15,-2)
   -v { #Number } : Number of Folds for Cross-Validation (default 10)
   -worker { #Number } : Number of Workers for Cross-Validation (default #Threads)

* option only applicable for open world scenario

Default Configuration is extracted from Environmental Variables
        Check, Adjust & Reload WFP_config if necessary

Notes:
 - Main Pages are stored with the Filename "mainPages_{Format}" with Closed-world Numbering in the same order as the Websites are stored.
 - When no amount of background instances is specified, maximum suitable amount is chosen.
 - The script tries to resume grid-search if the output file already exists. 
 """)
    print(error)
    sys.exit(1)

#Info:
# - Add Pass-through option for svm-train & Co ? (Breaks argument checking)

# Define formats
formats = [ 'TCP']

inputpath = ''
# Arguments to be read from WFP_conf
args = [ ('inputpath', 'dir_EVAL_INPUT', 'in'),
         ('outputpath', 'dir_EVAL_OUTPUT', 'out'),
         ('svmpath', 'dir_EVAL_LIBSVM', 'svm') ]

# Checking if all variables are/will be set
for var, env, arg in args:
    if not '-'+arg in sys.argv:
        vars()[var] = os.getenv(env)
        if vars()[var] == None:
            exit_with_help('Error: Environmental Variables or Argument'+
                        ' insufficiently set! ($'+env+' / "-'+arg+'")')

# Setting default values
inputpath = inputpath + 'wsc_features/'
outputname = 'WSC_Eval'
bg_name = ''
scenario = ''
storage = 'Low'
form = 'TCP'
setting = 'CW'
limitPage = False; limitMainPage = False; limitBackground = False; limitSite = False; limitSites = False
perPage = -1; perMainPage = -1; bg_size = -1; perSite = -1;
quiet = False

grid_option = ''

# init values
tmp1 = None; tmp2 = None; tmp3a = None; tmp3b = None; tmp4 = None; tmp5 = None; tmp6 = None; tmp7 = None; tmp8 = None
gnuplot_exe = None

# Read parameters from command line call
if len(sys.argv) != 0:
    i = 0
    options = sys.argv[1:]
    # iterate through parameter
    while i < len(options):
        if options[i] == '-in':
                i = i + 1
                inputpath = options[i]
        elif options[i] == '-out':
                i = i + 1
                outputpath = options[i]
        elif options[i] == '-name':
                i = i + 1
                outputname=options[i]
        elif options[i] == '-storage':
                i = i + 1
                storage=options[i]
        elif options[i] == '-q':
                quiet = True
        elif options[i] == '-format':
                i = i + 1
                form=options[i]
        elif options[i] == '-mainpages':
                i = i + 1
                tmp1 = options[i]
        elif options[i] == '-quickCV':
                i = i + 1
                tmp2 = options[i]
        elif options[i] == '-randomInstances':
                i = i + 1
                tmp3a = options[i]
        elif options[i] == '-randomSubpages':
                i = i + 1
                tmp3b = options[i]
        elif options[i] == '-setting':
                i = i + 1
                setting = options[i]
        elif options[i] == '-simple':
                i = i + 1
                tmp4 = options[i]
        elif options[i] == '-background':
                i = i + 1
                bg_name = options[i]
        elif options[i] == '-separateEvaluation':
                i = i + 1
                tmp5 = options[i]
        elif options[i] == '-limitWebsites':
                i = i + 1
                limitSites = True
                websitesIndex = map(int, options[i].split(','))
        elif options[i] == '-limitInstances':
                i = i + 1
                tmp6 = options[i]
        elif options[i] == '-limitSubpages':
                i = i + 1
                perSite = int(options[i])
        elif options[i] == '-svm':
                i = i + 1
                svmpath = options[i]
        elif options[i] == '-gnuplot':
                i = i + 1
                gnuplot_exe = options[i]
        elif options[i] == '-log2g':
                i = i + 1
                grid_option = grid_option + ' -log2g ' + options[i]
        elif options[i] == '-log2c':
                i = i + 1
                grid_option = grid_option + ' -log2c ' + options[i]
        elif options[i] == '-v':
                i = i + 1
                tmp7 = options[i]
                grid_option = grid_option + ' -v ' + options[i]
        elif options[i] == '-worker':
                i = i + 1
                tmp8 = options[i]
                grid_option = grid_option + ' -worker ' + options[i]
        else:
            exit_with_help('Error: Unknown Argument! ('+ options[i] + ')')
        i = i + 1

# Check set variables
if not os.path.isdir(inputpath):
    exit_with_help('Error: Invalid Input Path!')
if not os.path.isdir(outputpath):
    os.mkdir(outputpath)
# Remove "Name" in Output directory?
if storage not in [ 'Low', 'RemoveTemp', 'High' ]:
    exit_with_help('Error: Unknown Storage Option!')
if form not in formats:
    exit_with_help('Error: Unknown Format!')
if tmp1 in [ 'YES', 'NO' ] or tmp1 == None:
    if tmp1 == 'NO':
        main = False
    else:
        main = True
        if not os.path.isfile(inputpath+'mainPages_'+form):
            exit_with_help('Error: Invalid Main Pages Files!')
else:
    exit_with_help('Error: Unknown Main Page Option!')
if tmp2 in [ 'YES', 'NO' ] or tmp2 == None:
    if tmp2 == 'NO':
        quick = False
    else:
        quick = True
else:
    exit_with_help('Error: Unknown Quick CV Option!')
if tmp3a in [ 'YES', 'NO' ] or tmp3a == None:
    if tmp3a == 'YES':
        shuffleInstances = True
    else:
        shuffleInstances = False
if tmp3b in [ 'YES', 'NO' ] or tmp3b == None:
    if tmp3b == 'YES':
        shuffleSubpages = True
    else:
        shuffleSubpages = False
else:
    exit_with_help('Error: Unknown Random Option!')
if setting not in [ 'CW', 'OW' ]:
    exit_with_help('Error: Unknown Setting!')
if tmp4 in [ 'YES', 'NO' ] or tmp4 == None:
    if tmp4 == 'NO':
        simple = False
    else:
        simple = True
else:
    exit_with_help('Error: Unknown Simple Option!')
if setting == 'OW':
    if bg_name == '':
        exit_with_help('Error: No Background File Set!')
    if not os.path.isfile(inputpath+bg_name+'_'+form):
        exit_with_help('Error: Invalid Background File!')
    bg_domain_file = 'list_' + bg_name[0].lower() + bg_name[1:] + '_' + form + '.txt'
    if not os.path.isfile(inputpath+bg_domain_file):
        exit_with_help('Error: Invalid Domain-Background File!')
else:
    if bg_name != '':
        exit_with_help('Error: Background File Set in Closed-world Scenario!')
if tmp5 in [ 'YES', 'NO' ] or tmp5 == None:
    if tmp5 == 'YES':
        if setting == 'OW':
            separateEval = True
        else:
            exit_with_help('Error: Separate Evaluation is only meaningful in Open-world Scenario!')
    else:
        separateEval = False
else:
    exit_with_help('Error: Unknown Separate Evaluation Option!')
if tmp6 != None:
    perPage, perMainPage, bg_size = map(int,tmp6.split(','))
if not os.path.isdir(svmpath):
    exit_with_help('Error: Invalid LibSVM Path!')
else:
	svmscale_exe = os.path.join(svmpath, 'svm-scale')
	svmtrain_exe_q = os.path.join(svmpath, 'svm-train-q')
	svmpredict_exe = os.path.join(svmpath, 'svm-predict')
	grid_py = os.path.join(svmpath, './tools/grid_patched.py')
	if gnuplot_exe == None:
		gnuplot_exe = "/usr/bin/gnuplot"
		if not os.path.exists(gnuplot_exe):
			gnuplot_exe = None
	else:
		assert os.path.exists(gnuplot_exe),"gnuplot executable not found"
	assert os.path.exists(svmscale_exe),"svm-scale executable not found"
	assert os.path.exists(svmtrain_exe_q),"svm-train executable not found"
	assert os.path.exists(svmpredict_exe),"svm-predict executable not found"
	assert os.path.exists(grid_py),"grid_patched.py not found"
if tmp7 == None or tmp7.isdigit():
    if tmp7 == None:
        folds = 10
    elif int(tmp7) > 0:
        folds = int(tmp7)
    else:
        exit_with_help('Error: Number of Folds is not a valid Number!')
else:
    exit_with_help('Error: Number of Folds is not a Number!')
if tmp8 == None or tmp8.isdigit():
    if tmp8 == None:
        nr_worker = multiprocessing.cpu_count()
    elif int(tmp8) > 0:
        nr_worker = int(tmp8)
    else:
        exit_with_help('Error: Number of Workers is not a valid Number!')
else:
    exit_with_help('Error: Number of Workers is not a Number!')


# Additional checks
if setting == 'OW':
    openworld = True
else:
    openworld = False
if simple:
    scenario = scenario + '_simple'
if perPage > -1:
    limitPage = True
if perMainPage > -1:
    limitMainPage = True
if bg_size > -1 and openworld:
    limitBackground = True
if perSite > -1:
    limitSite = True
scenario = scenario + '_' + form

def outputInput():
	for currentFold in range(1, folds+1):
		# output training & testing
		ftrainout = open(os.path.join(outputpath, outputname + scenario + '_' + str(currentFold) + '.train'), 'w')
		ftestout = open(os.path.join(outputpath, outputname + scenario + '_' + str(currentFold) + '.test'), 'w')
		# iterate through each page
		site=0
		for k in range(1,sites*subpages+1):
			
			if k % subpages == 1:
				site += 1
				# Filter out main pages
				if not main:
					continue
			
			lower = currentFold + 1 +((site-1)*subpages)
			higher = currentFold + pagesPerFold + ((site-1)*subpages)
			
			if simple:
				classNumber = site
			else:
				classNumber = k
			
			if k in range(lower, higher+1):
				for item in classes[k]:
					ftestout.write(str(classNumber) + ' ' + item.split(' ', 1)[-1])
			else:
				for item in classes[k]:
					ftrainout.write(str(classNumber) + ' ' + item.split(' ', 1)[-1])
			
		
		if openworld:
			# append background
			lower = (currentFold-1)*pagesPerBGFold
			higher = currentFold*pagesPerBGFold
			for i in range(0, len(background)):
				if i in range(lower, higher):
					ftestout.write(background[i])
				else:
					ftrainout.write(background[i])
		
		ftrainout.close()
		ftestout.close()
	
	return


def evaluation():
	for currentFold in range(1, folds+1):
		
		training_file = os.path.join(outputpath, outputname + scenario + '_' + str(currentFold) + '.train')
		model_file = os.path.join(outputpath, outputname + scenario + '_' + str(currentFold) + '.model')
		
		if not quick:
			
			status_file = os.path.join(outputpath, outputname + scenario + '.out')
			gnuplot_file = os.path.join(outputpath, outputname + scenario + '.png')
			
			# CV for each fold of each
				# check if we can resume
			if os.path.isfile(status_file):
				grid_option += ' -resume "{0}" -out "{0}" -png "{1}" '.format(status_file, gnuplot_file)
			else:
				grid_option += ' -out "{0}" -png "{1}" '.format(status_file, gnuplot_file)
			cmd = 'python {0} -svmtrain "{1}" -gnuplot "{2}" {3} "{4}"'.format(grid_py, svmtrain_exe_q, gnuplot_exe, grid_option, training_file)
			if not quiet:
				print('[' + str(datetime.now()).split('.')[0] + '] Fold: {0:>3} - Cross Validation...'.format(currentFold))
			f = Popen(cmd, shell = True, stdout = PIPE).stdout
			
			line = ''
			while True:
				last_line = line
				line = f.readline()
				if not line: break
			c,g,rate = map(float,last_line.split())
			results.append((c,g,rate))
	
			if not quiet:
				print('[' + str(datetime.now()).split('.')[0] + '] Fold: {0:>3} - '.format(currentFold) + 'Best c={0}, g={1} CV rate={2}'.format(results[currentFold-1][0],results[currentFold-1][1],results[currentFold-1][2]))
		
		# train model for each fold
		cmd = '{0} -c {1} -g {2} "{3}" "{4}"'.format(svmtrain_exe_q,results[currentFold-1][0],results[currentFold-1][1], training_file, model_file)
		
		if not quiet:
			print('[' + str(datetime.now()).split('.')[0] + '] Fold: {0:>3} - Training...'.format(currentFold))
		Popen(cmd, shell = True, stdout = PIPE).communicate()

		testing_file = os.path.join(outputpath, outputname + scenario + '_' + str(currentFold) + '.test')
		predict_file = os.path.join(outputpath, outputname + scenario + '_' + str(currentFold) + '.predict')
		
		# test model for each fold
		cmd = '{0} "{1}" "{2}" "{3}"'.format(svmpredict_exe, testing_file, model_file, predict_file)
		if not quiet:
			print('[' + str(datetime.now()).split('.')[0] + '] Fold: {0:>3} - Testing...'.format(currentFold))
			Popen(cmd, shell = True).communicate()
		else:
			Popen(cmd, shell = True, stdout = PIPE).communicate()

	# merge result for each fold
	result_file = os.path.join(outputpath, outputname + scenario + '.result')
	
	correct = 0; wrong = 0
	tp = 0; fn = 0; fp = 0; tn = 0
	fresult = open(result_file, 'w')
	for currentFold in range(1, folds+1):
		fpredict = open(os.path.join(outputpath, outputname + scenario + '_' + str(currentFold) + '.predict'), 'r')
		for line in fpredict:
			if simple:
				pred = int(line.split(',')[0])
				real = int(line.split(',')[1])
			else:
				pred = int(line.split(',')[0])
				real = int(line.split(',')[1])
				if pred % subpages == 0:
					pred = pred // subpages
				else:
					pred = pred // subpages + 1
				if real % subpages == 0:
					real = real // subpages
				else:
					real = real // subpages + 1
			if pred == real:
				correct += 1
				if separateEval:
					if real == 0:
						tn += 1
					else:
						tp += 1
			else:
				wrong += 1
				if separateEval:
					if real == 0:
						fp += 1
					else:
						fn += 1
			fresult.write(str(pred) + ',' + str(real) + '\n')
		fpredict.close()
	fresult.close()
	
	if not quiet:
		print('Output prediction: {0}'.format(result_file))
	if separateEval:
		print(currentName + ': Correct: ' + str(correct) + ' Wrong: ' + str(wrong) + ' of ' + str(sites*instances*pagesPerFold*folds+len(background)))
		
		result_file_merged = os.path.join(outputpath, outputname_saved + '_Separate' + scenario + '.result')
		result = open(result_file_merged, 'a')
		result.write('%s %d %d %d %d\n' % (currentName, tp, fp, fn, tn))
		result.close()
	else:
		print('Correct: ' + str(correct) + ' Wrong: ' + str(wrong) + ' of ' + str(sites*instances*pagesPerFold*folds+len(background)))
	
	return

def removeTemp():
	for currentFold in range(1, folds+1):
		os.remove(os.path.join(outputpath, outputname + scenario + '_' + str(currentFold) + '.train'))
		os.remove(os.path.join(outputpath, outputname + scenario + '_' + str(currentFold) + '.test'))
		os.remove(os.path.join(outputpath, outputname + scenario + '_' + str(currentFold) + '.predict'))


outputname_saved = outputname
scenario_saved = scenario
foreground = []
sitefiles = natsorted(glob.glob(inputpath+'wsc*_'+form))
if separateEval:
	sites = 1
else:
	sites = len(sitefiles)

for currentSite in range(0,len(sitefiles)):
	
	# Determine Filenames
	if separateEval:
		currentName = os.path.basename(sitefiles[currentSite]).replace('wsc','').split('_')[0]
		outputname = outputname_saved + '_' + currentName
		scenario = scenario_saved
		foreground = [ currentName.lower() ]
		if limitSites:
			if not currentSite in websitesIndex:
				continue
	
	if not quiet:
		print('[' + str(datetime.now()).split('.')[0] + '] Processing ' + outputname + scenario)
	merged_file = os.path.join(outputpath, outputname + scenario + '.merged')
	range_file = os.path.join(outputpath, outputname + scenario + '.range')
	merged_scaled_file = os.path.join(outputpath, outputname + scenario + '.merged.scale')

	# Merge input files
	site = 1
	fout = open(merged_file, 'w')
	# Read foreground / closed-world dataset
	for filename in sitefiles:
		if separateEval:
			# we do not want to process this page at the moment
			if filename != sitefiles[currentSite]:
				continue
			compare = currentSite + 1
		else:
			foreground.append(os.path.basename(filename).replace('wsc','').split('_')[0].lower())
			compare = site
		# Add Main Page
		if main:
			fmain = open(inputpath+'mainPages_'+form, 'r')
			for line in fmain:
				if int(line.split()[0]) == compare:
					fout.write('-1 ' + line.split(' ', 1)[-1])
			fmain.close()
		# Add Subpages of website
		fin = open(filename,'r')
		fout.write(fin.read())
		fin.close()
		site += 1

	# Read in background dataset
	if openworld:
		fbg = open(inputpath+bg_name+'_'+form,'r')
		fout.write(fbg.read())
		fbg.close()

	fout.close()

	# Scale data and obtain range file
	cmd = '{0} -s "{1}" "{2}" > "{3}"'.format(svmscale_exe, range_file, merged_file, merged_scaled_file)
	if not quiet:
		print('[' + str(datetime.now()).split('.')[0] + '] Scaling data...')
		Popen(cmd, shell = True).communicate()
	else:
		Popen(cmd, shell = True, stdout = PIPE).communicate()

	# Read File into Arrays per class
	classes = {}
	mainpages = []
	background = []
	className = 0
	lastClass = 0
	# In OW, filter out domains
	if openworld:
		fdomain = open(inputpath + bg_domain_file,'r')
	
	f = open(merged_scaled_file, 'r')
	for line in f:
		currentClass = int(line.split()[0])
		if currentClass != lastClass:
			className += 1
			lastClass = currentClass
		
		# handle background separately
		if currentClass == 0:
			if openworld:
				link = fdomain.next().rstrip('\n')
				domain = tldextract.extract(link)
				domainname = domain.domain
				if domainname not in foreground:
					background.append(line)
				else:
					if not quiet:
						print('\tSkipped: ' + domainname + '//' + link)
				continue
			else:
				print('Error: The instance number seems to be incorrect!')
				raise SystemExit
		
		# append to all gathered instances
		if className in classes:
			classes[className].append(str(className) + ' ' + line.split(' ', 1)[-1])
		else:
			classes[className] = [str(className) + ' ' + line.split(' ', 1)[-1]]
	f.close()
	# Adjust classCount
	if openworld:
		className -= 1
		fdomain.close()
	if main:
		className -= sites

	# Remove temporary data
	if storage == 'RemoveTemp' or storage == 'Low':
		os.remove(merged_file)
		os.remove(merged_scaled_file)

	# Check if Subpages can be split into folds
	if (className/sites) % folds == 0:
		subpages=className//sites
		pagesPerFold = subpages//folds
		if limitSite:
			if perSite % folds != 0:
				print('Error: Limited Pages cannot be partitioned into equally sized folds!')
				raise SystemExit
			pagesPerFold = perSite//folds
		else:
			perSite = subpages
		if main:
			subpages += 1
	else: 
		print('Error: Pages cannot be partitioned into equally sized folds!')
		raise SystemExit

	# Shuffle Arrays
	if shuffleInstances:
		# Instances of each page
		for k in classes.keys():
			random.shuffle(classes[k])
		if openworld:
			random.shuffle(background)
	if shuffleSubpages:
		# Pages of each site
		for k in range(1,sites+1):
			
			lower = (k-1)*subpages+1
			# Do not shuffle the main page!
			if main:
				lower += 1
			higher = (k)*subpages
			
			tmp = []
			for j in range(lower, higher+1):
				tmp.append(classes[j])
			random.shuffle(tmp)
			tmp.reverse()
			for j in range(lower, higher+1):
				classes[j] = tmp.pop()

	# Check if Background can be split into folds
	if openworld:
		# Calculate Upper BG bound
		if not limitBackground:
			bg_size = len(background)
			if bg_size % folds != 0:
				bg_size = bg_size//folds*folds
		
		# Limit background size
		if len(background) >= bg_size:
			background = background[:bg_size]
		else:
			print('Error: Not enough instances in background! - only '+ str(len(background)))
			raise SystemExit
		
		if bg_size % folds == 0:
			pagesPerBGFold = bg_size//folds
		else:
			print('Error: Background cannot be partitioned into equally sized folds!')
			raise SystemExit

	# Check for equal amount of instances and limit if desired
	if limitPage:
		instances=perPage
	else:
		instances = len(classes[2]) # Take as reference
		perPage = instances
	if limitMainPage:
		instancesMain = perMainPage
	else:
		instancesMain = len(classes[1])
		perMainPage = instancesMain
	
	# Limit Instances First
	for k in classes.keys():
		# Check if we have a main page
		if main and k % subpages == 1:
			if limitMainPage:
				if len(classes[k]) >= perMainPage:
					classes[k] = classes[k][:perMainPage]
					continue
				else:
					print('Error: Mainpage does not have enough instances!')
					raise SystemExit
			else:
				continue
		if limitPage:
			if len(classes[k]) >= perPage:
				classes[k] = classes[k][:perPage]
				continue
			else:
				print('Error: Subpages do not have enough instances!')
	# Check for same amount of instances Second
	for k in classes.keys():
		# Check if we have a main page
		if main and k % subpages == 1:
			if len(classes[k]) != instancesMain:
				print('Error: Mainpages do have the same amount of instances!')
				raise SystemExit
			else:
				continue
		if len(classes[k]) != instances:
			print('Error: Subpages do have the same amount of instances!')
			raise SystemExit

	if not separateEval:
		scenario +=  '_' + str(sites) + 'S'
	scenario += '_' + str(perSite) + 'SP_' + str(perPage) + 'ISP'
	if main:
		scenario += '_' + str(perMainPage) + 'IMP'
	if openworld:
		scenario += '_' + str(bg_size) + 'IBG'
	
	results = []
	# Perform CV once for all data, not for every fold
	if quick:
		scaled_file = os.path.join(outputpath, outputname + scenario + '.scale')
		status_file = os.path.join(outputpath, outputname + scenario + '.out')
		gnuplot_file = os.path.join(outputpath, outputname + scenario + '.png')
		
		fout = open(scaled_file, 'w')
		className = 0
		pageCount = 1
		for k in classes.keys():
			# is the first page of a new website?
			if k % subpages == 1:
				className += 1
				pageCount = 1
				# Even a main page?
				if main:
					pageCount -= 1
			else:
				if limitSite:
					if pageCount >= perSite:
						continue
				pageCount += 1 
				if not simple:
					className += 1
			
			for item in classes[k]:
				fout.write(str(className) + ' ' + item.split(' ', 1)[-1])
		
		if openworld:
			for item in background:
				fout.write(item)
		fout.close()
		
		# check if we can resume
		if os.path.isfile(status_file):
			grid_option += ' -resume "{0}" -out "{0}" -png "{1}" '.format(status_file, gnuplot_file)
		else:
			grid_option += ' -out "{0}" -png "{1}" '.format(status_file, gnuplot_file)
		cmd = 'python {0} -svmtrain "{1}" -gnuplot "{2}" {3} "{4}"'.format(grid_py, svmtrain_exe_q, gnuplot_exe, grid_option, scaled_file)
		if not quiet:
			print('[' + str(datetime.now()).split('.')[0] + '] Cross validation...')
		f = Popen(cmd, shell = True, stdout = PIPE).stdout
		
		line = ''
		while True:
			last_line = line
			line = f.readline()
			if not line: break
		c,g,rate = map(float,last_line.split())
		#c,g,rate=map(float, ['8192','0.5','90.3487'])
		
		for currentFold in range(1, folds+1):
			results.append((c,g,rate))
		
		if not quiet:
			print('[' + str(datetime.now()).split('.')[0] + '] Best c={0}, g={1} CV rate={2}'.format(c,g,rate))
		
		# Remove temporary data
		if storage == 'RemoveTemp' or storage == 'Low':
			os.remove(scaled_file)

	# for k folds: partition i is used for testing in fold i, the remaining k-1 partitions are used for training
	outputInput()
	# perform evaluation
	evaluation()
	# remove temporary data
	if storage == 'RemoveTemp' or storage == 'Low':
		removeTemp()
	
	# The evaluation has been performed
	if not separateEval:
		break
