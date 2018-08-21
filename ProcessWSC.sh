#!/bin/bash

#Initially:
#Check/Clean-fetches
echo "WSC: Make sure that the fetches are clean!"

# Outlier Removal & Main Page Backup
#echo "WSC: Assumes that the cell format exists!"

INSTANCES=10
INSTANCES_MAIN=10
SUBPAGES=20
INPUT="${dir_TEMP_COMPILED}"
SCRIPTS="${dir_FETCH_SCRIPTS}"

COMPILED_TMP="${INPUT}../wsc_compiled/"
MERGED_TMP="${INPUT}../wsc_merged/"
OUTLIER_TMP="${INPUT}../wsc_outlier/"
FEATURES="${INPUT}../wsc_features/"
INPUT_MAIN="${INPUT}../main_merged/"
MERGED_MAIN="${INPUT}../wsc_main_merged/"
OUTLIER_MAIN="${INPUT}../wsc_main_outlier/"

# Define all available formats
formats=( "output-tcp" )

# Prepare beforehand !
echo "WSC: Main pages can be stored beforehand! Be aware of possible duplicates!"

# Clean up
if [ -d "$COMPILED_TMP" ]; then
    rm -rf ${COMPILED_TMP}
fi
mkdir -p ${COMPILED_TMP}

# Create Main Pages Output
mkdir -p ${MERGED_MAIN}

#a) Define WSC List
SITES=$(ls ${INPUT} | cut -d _ -f 5 | sort -u)

### Example for preparing main pages ###
###############
# Stackoverflow is broken :/
###
# for site in ${SITES[@]}; do
# 	for format in ${formats[@]}; do
# 		if [ -d ${INPUT_MAIN}output-${format}/ ]; then
# 			name=$(ls ${INPUT_MAIN}output-${format}/ | grep -i ${site:3})
# 			cp ${INPUT_MAIN}output-${format}/$name ${MERGED_MAIN}output-${format}/${site/wsc/} # if performed beforehand
# 			#cat ${INPUT_MAIN}output-${format}/$name >> ${MERGED_MAIN}output-${format}/${site/wsc/} # if performed afterwards
# 		fi
# done
# read -p "WSC: Fix Problems with Main Page Preparation and Press Enter"
###############

#b) For each Site perform following steps
for site in ${SITES[@]}; do
	#Step 1: Merge Instances of Pages (CW - Setting)
	echo "WSC: Copying"
	fetches=$(ls ${INPUT} | grep ${site})
	for fetch in ${fetches[@]}; do
		cp -R ${INPUT}$fetch ${COMPILED_TMP}
	done
	
	echo "WSC: Merging"
	${SCRIPTS}merge-input.sh -in "${COMPILED_TMP}" -out "${MERGED_TMP}" -setting "CW"

	#Step 2: Backup Mainpage (Shortest Filename?!) # Dangerous!!!
	mainpage=$(ls ${MERGED_TMP}output-tcp/ | awk '{ print length($0) " " $0; }' | sort -r -n | cut -d ' ' -f 2 | tail -1)
       
        echo "MAIN PAGE ++++++++++++++++++++++++++++ " $mainpage
	for format in ${formats[@]}; do
		if [ ! -d "${MERGED_TMP}output-tcp/" ]; then
			continue
		fi
		if [ ! -d "${MERGED_MAIN}output-tcp/" ]; then
			mkdir -p ${MERGED_MAIN}output-tcp/
		fi
		#mv ${MERGED_TMP}output-${format}/${mainpage} ${MERGED_MAIN}output-${format}/${site/wsc/} # if performed beforehand
		mv ${MERGED_TMP}output-tcp/${mainpage} ${MERGED_MAIN}output-tcp # if performed afterwards
		rm ${MERGED_TMP}output-tcp/${mainpage} # if performed afterwards
	done

	#Step 3: Perform Outlier Removal (Fixed Number of Instances per Page)
	echo "WSC: Outlier Removal"
	${SCRIPTS}outlier-removal.py -in "${MERGED_TMP}" -out "${OUTLIER_TMP}" -setting "CW" -ignoreOutlier "NO" -outlierRemoval "Simple" -randomInstances "YES" -referenceFormat "tcp" -instances "${INSTANCES}"

	#Step 4: Keep only Fixed Number of Subpages
	count=$(ls ${OUTLIER_TMP}output-tcp-outlierfree/ | wc -l)
	if [ ${count} -lt ${SUBPAGES} ]; then
		# We don't have enough! Ignore Outlier
		echo "WSC: Outlier Removal - Repeated"
		${SCRIPTS}outlier-removal.py -in "${MERGED_TMP}" -out "${OUTLIER_TMP}" -setting "CW" -ignoreOutlier "YES" -outlierRemoval "Simple" -randomInstances "YES" -referenceFormat "tcp" -instances "${INSTANCES}"
		rm ${OUTLIER_TMP}output-tcp-outlierfree/${mainpage}
		# count again
		count=$(ls ${OUTLIER_TMP}output-tcp-outlierfree/ | wc -l)
		if [ ${count} -lt ${SUBPAGES} ]; then
			echo "WSC: Error not enough Subpages"
			exit
		fi
	fi
	if [ ${count} -gt ${SUBPAGES} ]; then
		echo "WSC: Too many Subpages (${count}/${SUBPAGES}) - removing"
	fi
	while [ ${count} -gt ${SUBPAGES} ]; do
		# all subpages
		pages=($(ls ${OUTLIER_TMP}output-tcp-outlierfree/ | shuf))
		
		# get random page and remove if not mainpage
		#if [ "${mainpage}" = "${pages[0]}" ]; then
		#	continue
		#else
	
	        rm ${OUTLIER_TMP}output-tcp-outlierfree/${pages[0]}
			
	        count=$(ls ${OUTLIER_TMP}output-tcp-outlierfree/ | wc -l)
		#fi
	done
	
	#Step 5: Generate Features (CW - Setting) and merge into Single File for Site
	echo "WSC: Feature Generation"
	${SCRIPTS}generate-feature.py -in "${OUTLIER_TMP}" -out "${FEATURES}" -setting "CW" -classifier "CUMULATIVE" -features "100" -randomInstances "NO" -instances "${INSTANCES}" -dataSet "${site}"
	
	#Step 6: Clean up
	rm -rf ${COMPILED_TMP}
	mkdir -p ${COMPILED_TMP}
done

rm -rf ${COMPILED_TMP}
rm -rf ${MERGED_TMP}
rm -rf ${OUTLIER_TMP}

for format in ${formats[@]}; do
	if [ ! "$(ls -A ${MERGED_MAIN}output-tcp/)" ]; then
		rmdir ${MERGED_MAIN}output-tcp/
	fi
done

#c) Process Mainpages Set
echo "WSC: Outlier-Removal Mainpages"


${SCRIPTS}outlier-removal.py -in "${MERGED_MAIN}" -out "${OUTLIER_MAIN}" -setting "CW" -ignoreOutlier "NO" -outlierRemoval "Simple" -randomInstances "YES" -referenceFormat "tcp" -instances 10

echo "WSC: Feature Generation Mainpages"
${SCRIPTS}generate-feature.py -in "${OUTLIER_MAIN}" -out "${FEATURES}" -setting "CW" -classifier "CUMULATIVE" -features "100" -randomInstances "NO" -instances "${INSTANCES_MAIN}" -dataSet "mainPages"
#echo "WSC: Better execute again with more instances to obtain a bigger Data Set!"

#Execute WSC-Subpage Eval-Script and easy.py on Mainpages
echo "WSC: Excute Evaluation Scripts now!"

