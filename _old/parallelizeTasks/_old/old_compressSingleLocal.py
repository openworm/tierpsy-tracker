# -*- coding: utf-8 -*-
"""
Created on Thu Jul  2 14:38:05 2015

@author: ajaver
"""
import os, stat
import sys
import h5py
import shutil


curr_script_dir = os.path.dirname(os.path.realpath(__file__))
with open(os.path.join(curr_script_dir, 'MWTracker_dir.txt'), 'r') as f:
    MWTracker_dir = f.readline()
sys.path.append(MWTracker_dir)

from MWTracker.helperFunctions.compressVideoWorkerL import compressVideoWorkerL

if __name__ == "__main__":

	try:
		video_file = sys.argv[1]
		mask_dir = sys.argv[2]
		tmp_mask_dir = sys.argv[3]

		json_file = ''
		if len(sys.argv) > 4:
			json_file = sys.argv[4]
		
		print(json_file)
		
		if mask_dir[-1] != os.sep: mask_dir += os.sep 
		if tmp_mask_dir[-1] != os.sep: tmp_mask_dir += os.sep 

		base_name = video_file.rpartition('.')[0].rpartition(os.sep)[-1]
		masked_image_file = mask_dir + base_name + '.hdf5'
		masked_image_file_tmp = tmp_mask_dir + base_name + '.hdf5'
	    
		try:

			with h5py.File(masked_image_file, "r") as mask_fid:
				if mask_fid['/mask'].attrs['has_finished'] == 1:
					has_finished = 1
		except:
			has_finished = 0


		print(has_finished, masked_image_file)
		if not has_finished:	
			print("Creating temporal masked file.")
			compressVideoWorkerL(video_file, tmp_mask_dir, json_file)

			print("Copying temporal masked file into the final directory.")
			shutil.copy(masked_image_file_tmp, masked_image_file)
			os.chmod(masked_image_file, stat.S_IRUSR|stat.S_IRGRP|stat.S_IROTH) #change the permissions to read only

			print("Removing temporary files.")
			if masked_image_file_tmp != masked_image_file:
				os.remove(masked_image_file_tmp)

			print("Finished to create masked file")
		else:
			print('File alread exists: %s. If you want to calculate the mask again delete the existing file.' % masked_image_file)
	except:
		print('Error')
		raise