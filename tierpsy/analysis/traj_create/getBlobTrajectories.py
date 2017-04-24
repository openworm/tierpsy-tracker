# -*- coding: utf-8 -*-
"""
Created on Thu Apr  2 16:33:34 2015

@author: ajaver
"""

import json
import multiprocessing as mp
import os
from functools import partial

import cv2
import numpy as np
import skimage.filters as skf
import skimage.morphology as skm
import tables

from tierpsy.analysis.compress.BackgroundSubtractor import BackgroundSubtractor
from tierpsy.analysis.compress.extractMetaData import read_and_save_timestamp
from tierpsy.helper.params import read_unit_conversions
from tierpsy.helper.params import traj_create_defaults
from tierpsy.helper.misc import TimeCounter, print_flush, TABLE_FILTERS


def _thresh_bw(pix_valid):
    # calculate otsu_threshold as lower limit. Otsu understimates the threshold.
    try:
        otsu_thresh = skf.threshold_otsu(pix_valid)
    except:
        return np.nan

    # calculate the histogram
    pix_hist = np.bincount(pix_valid)

    # the higher limit is the most frequent value in the distribution
    # (background)
    largest_peak = np.argmax(pix_hist)
    if otsu_thresh < largest_peak and otsu_thresh + 2 < len(pix_hist) - 1:
        # smooth the histogram to find a better threshold
        pix_hist = np.convolve(pix_hist, np.ones(3), 'same')
        cumhist = np.cumsum(pix_hist)

        xx = np.arange(otsu_thresh, cumhist.size)
        try:
            # the threshold is calculated as the first pixel level above the otsu threshold 
            # at which there would be larger increase in the object area.
            hist_ratio = pix_hist[xx] / cumhist[xx]
            thresh = np.where(
                (hist_ratio[3:] - hist_ratio[:-3]) > 0)[0][0] + otsu_thresh
        except IndexError:
            thresh = np.argmin(
                pix_hist[
                    otsu_thresh:largest_peak]) + otsu_thresh
    else:
        # if otsu is larger than the maximum peak keep otsu threshold
        thresh = otsu_thresh
    return thresh

def _thresh_bodywallmuscle(pix_valid):
    pix_mean = np.mean(pix_valid)
    pix_median = np.median(pix_valid)
    # when fluorescent worms are present, the distribution of pixels should be asymmetric, with a peak at low values corresponding to the background
    if pix_mean > pix_median*1.1: # alternatively, could use scipy.stats.skew and some threshold, like >1/2
        thresh = pix_mean
    else: # try usual thresholding otherwise
        thresh = 255 - _thresh_bw(255 - pix_valid) #correct for fluorescence images
    return thresh

def getBufferThresh(ROI_buffer, worm_bw_thresh_factor, is_light_background, analysis_type):
    ''' calculate threshold using the nonzero pixels.  Using the
     buffer instead of a single image, improves the threshold
     calculation, since better statistics are recovered'''
     
    if analysis_type == "ZEBRAFISH":
        # Override threshold
        thresh = 255
    else: 
        pix_valid = ROI_buffer[ROI_buffer != 0]


        if pix_valid.size > 0:
            if is_light_background:
                thresh = _thresh_bw(pix_valid)
            else:
                if analysis_type == "WORM":
                    thresh = _thresh_bodywallmuscle(pix_valid)
                else:
                    #correct for fluorescence images
                    MAX_PIX = 255 #for uint8 images
                    thresh = _thresh_bw(MAX_PIX - pix_valid)
                    thresh = MAX_PIX - thresh

            thresh *= worm_bw_thresh_factor
        else:
            thresh = np.nan
    
    return thresh


def _remove_corner_blobs(ROI_image):
    #remove blobs specially in the corners that could be part of other ROI
    # get the border of the ROI mask, this will be used to filter for valid
    # worms
    ROI_valid = (ROI_image != 0).astype(np.uint8)
    _, ROI_border_ind, _ = cv2.findContours(ROI_valid, 
                                            cv2.RETR_EXTERNAL, 
                                            cv2.CHAIN_APPROX_NONE)

    if len(ROI_border_ind) > 1:
        # consider the case where there is more than one contour in the blob
        # i.e. there is a neighboring ROI in the square, just keep the largest area
        ROI_area = [cv2.contourArea(x) for x in ROI_border_ind]
        valid_ind = np.argmax(ROI_area)
        ROI_valid = np.zeros_like(ROI_valid)
        ROI_valid = cv2.drawContours(ROI_valid, ROI_border_ind, valid_ind, 1, -1)
        ROI_image = ROI_image * ROI_valid

    return ROI_image

def _get_blob_mask(ROI_image, thresh, thresh_block_size, is_light_background, analysis_type):
    # get binary image, 
    if is_light_background:
        ## apply a median filter to reduce rough edges / sharpen the boundary btw worm and background
        ROI_image_th = cv2.medianBlur(ROI_image, 3)
        ROI_mask = ROI_image_th < thresh
    else:
        if analysis_type == "PHARYNX":
            # for fluorescent pharynx labeled images, refine the threshold with a local otsu (http://scikit-image.org/docs/dev/auto_examples/plot_local_otsu.html)
            # this compensates for local variations in brightness in high density regions, when many worms are close to each other
            ROI_rank_otsu = skf.rank.otsu(ROI_image, skm.disk(thresh_block_size))
            ROI_mask = (ROI_image>ROI_rank_otsu)
            # as a local threshold introcudes artifacts at the edge of the mask, also use a global threshold to cut these out
            ROI_mask &= (ROI_image>=thresh)
        else:
            # this case applies for example to worms where the whole body is fluorecently labeled
            ROI_image_th = cv2.medianBlur(ROI_image, 3)
            ROI_mask = ROI_image_th >= thresh
        
    ROI_mask &= (ROI_image != 0)
    ROI_mask = ROI_mask.astype(np.uint8)

    return ROI_mask, thresh # returning thresh here seems redundant, as it isn't actually changed



def getBlobContours(ROI_image, 
                    thresh, 
                    strel_size=(5, 5), 
                    is_light_background=True, 
                    analysis_type="WORM", 
                    thresh_block_size=15):

    
    ROI_image = _remove_corner_blobs(ROI_image)
    ROI_mask, thresh = _get_blob_mask(ROI_image, thresh, thresh_block_size, is_light_background, analysis_type)
    
    # clean it using morphological closing - make this optional by setting strel_size to 0
    if np.all(strel_size):
        strel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, strel_size)
        ROI_mask = cv2.morphologyEx(ROI_mask, cv2.MORPH_CLOSE, strel)

    # get worms, assuming each contour in the ROI is a worm
    _, ROI_worms, hierarchy = cv2.findContours(ROI_mask, 
                                               cv2.RETR_EXTERNAL, 
                                               cv2.CHAIN_APPROX_NONE)

    return ROI_worms, hierarchy


def getBlobDimesions(worm_cnt, ROI_bbox):
    
    area = float(cv2.contourArea(worm_cnt))
    
    worm_bbox = cv2.boundingRect(worm_cnt)
    bounding_box_xmin = ROI_bbox[0] + worm_bbox[0]
    bounding_box_xmax = bounding_box_xmin + worm_bbox[2]
    bounding_box_ymin = ROI_bbox[1] + worm_bbox[1]
    bounding_box_ymax = bounding_box_ymin + worm_bbox[3]

    # save everything into the the proper output format
    blob_bbox =(bounding_box_xmin, 
                bounding_box_xmax,
                bounding_box_ymin,
                bounding_box_ymax)


    (CMx, CMy), (L, W), angle = cv2.minAreaRect(worm_cnt)
    #adjust CM from the ROI reference frame to the image reference
    CMx += ROI_bbox[0]
    CMy += ROI_bbox[1]

    if W > L:
        L, W = W, L  # switch if width is larger than length
    
    blob_dims = (CMx, CMy, L, W, angle)
    return blob_dims, area, blob_bbox
    
def generateImages(masked_image_file, frames=[], bgnd_param = {}):
    
    if len(bgnd_param)==0:
        bgnd_subtractor = None
    else:
        bgnd_subtractor = BackgroundSubtractor(masked_image_file, **bgnd_param)
    
    with tables.File(masked_image_file, 'r') as mask_fid:
        mask_dataset = mask_fid.get_node("/mask")
        
        if len(frames) == 0:
            frames = range(mask_dataset.shape[0])
        
        for frame_number in frames:
            image = mask_dataset[frame_number]
            
            if bgnd_subtractor is not None:
                image_b  = bgnd_subtractor.apply(image, last_frame=frame_number)
                #image_buffer_b = 255 - image_buffer_b
                image_b[image==0] = 0
                image = image_b
            
            yield frame_number, image

def generateROIBuff(masked_image_file, buffer_size, bgnd_param):
    
    img_generator = generateImages(masked_image_file, bgnd_param=bgnd_param)
    
    with tables.File(masked_image_file, 'r') as mask_fid:
        tot_frames, im_h, im_w = mask_fid.get_node("/mask").shape
    
    for frame_number, image in img_generator:
        if frame_number % buffer_size == 0:
            if frame_number + buffer_size > tot_frames:
                buffer_size = tot_frames-frame_number #change this value, otherwise the buffer will not get full
            image_buffer = np.zeros((buffer_size, im_h, im_w), np.uint8)
            ini_frame = frame_number            
        
        
        image_buffer[frame_number-ini_frame] = image
        
        #compress if it is the last frame in the buffer
        if (frame_number+1) % buffer_size == 0 or (frame_number+1 == tot_frames):
            # z projection and select pixels as connected regions that were selected as worms at
            # least once in the masks
            main_mask = np.any(image_buffer, axis=0)
    
            # change from bool to uint since same datatype is required in
            # opencv
            main_mask = main_mask.astype(np.uint8)
    
            #calculate the contours, only keep the external contours (no holes) and 
            _, ROI_cnts, _ = cv2.findContours(main_mask, 
                                                cv2.RETR_EXTERNAL, 
                                                cv2.CHAIN_APPROX_NONE)
    
            yield ROI_cnts, image_buffer, ini_frame
            
def _cnt_to_ROIs(ROI_cnt, image_buffer, min_box_width):
    #get the corresponding ROI from the contours
    ROI_bbox = cv2.boundingRect(ROI_cnt)
    # bounding box too small to be a worm - ROI_bbox[2] and [3] are width and height
    if ROI_bbox[2] > min_box_width and ROI_bbox[3] > min_box_width:
        # select ROI for all buffer slides 
        ini_x = ROI_bbox[1]
        fin_x = ini_x + ROI_bbox[3]
        ini_y = ROI_bbox[0]
        fin_y = ini_y + ROI_bbox[2]
        ROI_buffer = image_buffer[:, ini_x:fin_x, ini_y:fin_y]
    else:
        ROI_buffer = None

    return ROI_buffer, ROI_bbox


def getBlobsData(buff_data, blob_params):
    
    #I packed input data to be able top to map the function into generateROIBuff
    ROI_cnts, image_buffer, frame_number = buff_data
    
    is_light_background, min_area, min_box_width, worm_bw_thresh_factor, \
    strel_size, analysis_type, thresh_block_size = blob_params
    
    blobs_data = []
    # examinate each region of interest
    for ROI_cnt in ROI_cnts:
        #get the corresponding ROI from the contours
        ROI_buffer, ROI_bbox = _cnt_to_ROIs(ROI_cnt, image_buffer, min_box_width)
        if ROI_buffer is not None:
            # calculate threshold
            thresh_buff = getBufferThresh(ROI_buffer, worm_bw_thresh_factor, is_light_background, analysis_type)
            
            for buff_ind in range(image_buffer.shape[0]):
                curr_ROI = ROI_buffer[buff_ind, :, :]
    
                # get the contour of possible worms
                ROI_worms, hierarchy = getBlobContours(curr_ROI, 
                                                        thresh_buff, 
                                                        strel_size, 
                                                        is_light_background,
                                                        analysis_type, 
                                                        thresh_block_size)
                current_frame = frame_number + buff_ind
                
                for worm_ind, worm_cnt in enumerate(ROI_worms):
                    # ignore contours from holes. This shouldn't occur with the flag RETR_EXTERNAL
                    assert hierarchy[0][worm_ind][3] == -1
                        
    
                    # obtain features for each worm
                    blob_dims, area, blob_bbox = getBlobDimesions(worm_cnt, ROI_bbox)
                    
                    if area >= min_area:
                        # append data to pytables only if the object is larget than min_area
                        row = (-1, -1, current_frame, *blob_dims, area, *blob_bbox, thresh_buff)
                        blobs_data.append(row)
    
                    
    return blobs_data


def getBlobsTable(masked_image_file, 
                  trajectories_file,
                  buffer_size = None,
                    min_area=25,
                    min_box_width=5,
                    worm_bw_thresh_factor=1.,
                    strel_size=(5,5),
                    analysis_type="WORM",
                    thresh_block_size=15,
                    n_cores_used = 2, 
                    bgnd_param = {}):



    #correct strel if it is not a tuple or list
    if not isinstance(strel_size, (tuple,list)):
        strel_size = (strel_size, strel_size)
    assert len(strel_size) == 2


    #read properties
    fps_out, _, is_light_background = read_unit_conversions(masked_image_file)
    expected_fps = fps_out[0]

    #find if it is using background subtraction
    if len(bgnd_param) > 0:
        bgnd_param['is_light_background'] = is_light_background
    buffer_size = traj_create_defaults(expected_fps, buffer_size)
    

    def _ini_plate_worms(traj_fid, masked_image_file):
        # intialize main table
    
        int_dtypes = [('worm_index_blob', np.int),
                      ('worm_index_joined', np.int),
                      ('frame_number', np.int)]
        dd = ['coord_x', 
              'coord_y', 
              'box_length', 
              'box_width', 
              'angle',
              'area',
              'bounding_box_xmin',
              'bounding_box_xmax',
              'bounding_box_ymin',
              'bounding_box_ymax',
              'threshold']
        
        float32_dtypes = [(x, np.float32) for x in dd]
        
        plate_worms_dtype = np.dtype(int_dtypes + float32_dtypes)
        plate_worms = traj_fid.create_table('/',
                                            "plate_worms",
                                            plate_worms_dtype,
                                            "Worm feature List",
                                            filters = TABLE_FILTERS)

        
        
        #find if it is a mask from fluorescence and save it in the new group
        plate_worms._v_attrs['is_light_background'] = is_light_background
        plate_worms._v_attrs['expected_fps'] = expected_fps

        #make sure it is in a "serializable" format
        plate_worms._v_attrs['bgnd_param'] = bytes(json.dumps(bgnd_param), 'utf-8')
        

        read_and_save_timestamp(masked_image_file, trajectories_file)
        return plate_worms
    

    
    buff_generator = generateROIBuff(masked_image_file, buffer_size, bgnd_param)
    

    #switch the is_light_background flag if we are using background subtraction.
    #I have it so after background subtraction we have a dark background.
    is_light_background_b = is_light_background if len(bgnd_param)==0 else not is_light_background
    
    blob_params = (is_light_background_b,
                  min_area,
                  min_box_width,
                  worm_bw_thresh_factor,
                  strel_size,
                  analysis_type,
                  thresh_block_size)
    
    f_blob_data = partial(getBlobsData, blob_params = blob_params)
    
    
    if n_cores_used > 1:
        p = mp.Pool(n_cores_used)
        blobs_generator = p.imap(f_blob_data, buff_generator)
    else:
        blobs_generator = map(f_blob_data, buff_generator)
    
    #loop, save data and display progress
    base_name = masked_image_file.rpartition('.')[0].rpartition(os.sep)[-1]
    progress_str = base_name + ' Calculating trajectories.'
    
    progressTime = TimeCounter(progress_str)  
    with tables.open_file(trajectories_file, mode='w') as traj_fid:
        plate_worms = _ini_plate_worms(traj_fid, masked_image_file)
        
        for ibuf, blobs_data in enumerate(blobs_generator):
            if blobs_data:
                plate_worms.append(blobs_data)
            
            frames = ibuf*buffer_size
            if frames % (expected_fps*20) == 0:
                # calculate the progress and put it in a string
                print_flush(progressTime.get_str(frames))
                
    print_flush( progressTime.get_str(frames))
    

    
    


    
if __name__ == '__main__':
    #%%
    #dname = '/Users/ajaver/OneDrive - Imperial College London/Local_Videos/fluorescence/'
    #masked_image_file = os.path.join(dname, 'test_s.hdf5')
#    min_area=15/2
#    buffer_size=9
#    thresh_block_size=15    
#    max_allowed_dist = 20
#    area_ratio_lim = (0.25, 4)
#    n_proc = 20
    
    masked_image_file = '/Users/ajaver/OneDrive - Imperial College London/Local_Videos/Avelino_17112015/MaskedVideos/CSTCTest_Ch1_17112015_205616.hdf5'
    min_area=25/2
    buffer_size=25
    thresh_block_size=15 
    max_allowed_dist = 25
    area_ratio_lim = (0.5, 2)
    n_cores_used = 1
    
    trajectories_file = masked_image_file.replace('.hdf5', '_skeletons.hdf5')
    skeletons_file = masked_image_file.replace('.hdf5', '_skeletons.hdf5')
        
    
    
    from tierpsy.analysis.ske_init.processTrajectoryData import processTrajectoryData
    from tierpsy.helper.params.tracker_param import TrackerParams, default_param

    default_param['expected_fps'] = buffer_size
    default_param['traj_area_ratio_lim'] = area_ratio_lim
    param = TrackerParams()
    param._get_param(**default_param)
    
    #correctTrajectories(trajectories_file, False, param.join_traj_param)
    processTrajectoryData(skeletons_file, masked_image_file, skeletons_file, param.smoothed_traj_param, filter_model_name = '')
