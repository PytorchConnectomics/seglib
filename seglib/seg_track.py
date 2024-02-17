import numpy as np
from skimage.morphology import remove_small_objects
from tqdm import tqdm
from emu.io import read_vol, compute_bbox_all, read_vol
from .region_graph import merge_id

def seg_to_iou(seg0, seg1, uid0=None, bb0=None, uid1=None, uc1=None):
    """
    Compute the intersection over union (IoU) between segments in two segmentation maps (2D or 3D).

    Args:
        seg0 (numpy.ndarray): The first segmentation map.
        seg1 (numpy.ndarray): The second segmentation map.
        uid0 (numpy.ndarray, optional): The segment IDs to compute IoU for in the first segmentation map. Defaults to None.
        bb0 (numpy.ndarray, optional): The bounding boxes of segments in the first segmentation map. Defaults to None.
        uid1 (numpy.ndarray, optional): The segment IDs in the second segmentation map. Defaults to None.
        uic2 (numpy.ndarray, optional): The segment counts in the second segmentation map. Defaults to None.

    Returns:
        numpy.ndarray: An array containing the segment IDs, the best matching segment IDs, the segment counts, and the maximum overlap counts.

    Notes:
        - The function computes the intersection over union (IoU) between segments in two segmentation maps.
        - The IoU is computed for the specified segment IDs in `uid0`.
        - If `uid0` is not provided, the IoU is computed for all unique segment IDs in `seg0`.
    """    
    assert (np.array(seg0.shape) - seg1.shape).abs().max()==0, "seg0 and seg1 should have the same shape"
    if bb0 is not None:
        if seg0.ndim == 2:
            assert bb0.shape[1] == 6, "input bounding box for 2D segment has 6 columns [seg_id, ymin, ymax, xmin, xmax, count]"        
        elif seg0.ndim == 3:
            assert bb0.shape[1] == 8, "input bounding box for 3D segment has 8 columns [seg_id, zmin, zmax, ymin, ymax, xmin, xmax, count]"        
        else:
            raise "segment should be either 2D or 3D"                    
        
    # seg0 info: uid0, uc1, bb0
    # uid0 can be a subset of seg ids
    if uid0 is None:
        if bb0 is None:
            bb0 = compute_bbox_all(seg0, True)  
        uid0 = bb0[:, 0]
    elif bb0 is None:
        bb0 = compute_bbox_all(seg0, True, uid0)
    else:
        # select the boxes correspond to uid0
        bb0 = bb0[np.in1d(bb0[:, 0], uid0)]
        uid0 = bb0[:, 0]
    uc0 = bb0[:, -1]         

    # seg1 info: uid1, uc1
    if uid1 is None or uc1 is None:            
        uid1, uc1 = np.unique(seg1, return_counts=True)

    out = np.zeros((len(uid0), 5), int)
    out[:, 0] = uid0
    out[:, 2] = uc0

    for j, i in enumerate(uid0):
        bb = bb0[j, 1:]
        if seg0.ndim ==2:
            ui3, uc3 = np.unique(
                seg1[bb[0] : bb[1] + 1, bb[2] : bb[3] + 1]
                * (seg0[bb[0] : bb[1] + 1, bb[2] : bb[3] + 1] == i),
                return_counts=True,
            )
        else:
            ui3, uc3 = np.unique(
            seg1[bb[0] : bb[1] + 1, bb[2] : bb[3] + 1, bb[4] : bb[5] + 1]
            * (
                seg0[bb[0] : bb[1] + 1, bb[2] : bb[3] + 1, bb[4] : bb[5] + 1]
                == i
            ),
            return_counts=True,
        )
        uc3[ui3 == 0] = 0
        if (ui3 > 0).any():
            out[j, 1] = ui3[np.argmax(uc3)]
            out[j, 3] = uc1[uid1 == out[j, 1]]
            out[j, 4] = uc3.max()
    return out
def segs_to_iou(get_seg, index, th_iou=0):
    # get_seg function:
    # raw iou result or matches
    ndim = 5 if th_iou == 0 else 2
    out = [[]] * (len(index) - 1)
    seg0 = get_seg(index[0])
    bb0 = compute_bbox_all(seg0, True)
    out =[[]] * (len(index) - 1)
    for i, z in enumerate(index[1:]):
        seg1 = get_seg(z)
        bb1 = compute_bbox_all(seg1, True)    
        iou = seg_to_iou(seg0, seg1, bb0=bb0, uid1=bb1[:, 0], uc1=bb1[:, -1])    
        if th_iou == 0:
            # store all iou
            out[i] = iou.T
        else:
            # store matches
            # remove background seg id            
            iou = iou[iou[:, 1] != 0]
            score = iou[:, 4].astype(float) / (
                iou[:, 2] + iou[:, 3] - iou[:, 4]
            )
            gid = score > th_iou
            out[i] = iou[gid, :2].T
        bb0 = bb1       
    return out

def segs_to_global_id(get_seg, index):
    count = np.zeros(1 + len(index), int)
    for i, ind in enumerate(index):
        count[i + 1] = get_seg(ind).max()
    return np.cumsum(count)

def seg2d_vol_to_iou2d(seg_vol, th_iou=0):
    get_seg = lambda z: seg_vol[z]
    index = range(seg_vol.shape[0])
    return segs_to_iou(get_seg, index, th_iou)

def seg_list_to_iou(seg_list, th_iou=0):    
    get_seg = lambda z: read_vol(seg_list[z]) if isinstance(seg_list[z], str) else seg_list[z]
    index = range(len(seg_list))
    return segs_to_iou(get_seg, index, th_iou)

def seg_list_to_global_id(seg_list):
    get_seg = lambda z: read_vol(seg_list[z]) if isinstance(seg_list[z], str) else seg_list[z]
    index = range(len(seg_list))
    return segs_to_global_id(get_seg, index)

def ious_to_global_id(get_iou, index, return_count=False):
    count = [0] + [[]] * len(index) 
    for i, ind in enumerate(index):
        iou = get_iou(ind)
        if not isinstance(iou, list):
            iou = [iou]
        count[i + 1] = np.zeros(len(iou))
        for j in range(len(count)):
            count[i + 1][j] = iou[j][:,0].max()
    count = np.hstack(count)
    return count[1:] if return_count else np.cumsum(count)

def ious_to_matches(get_iou, index, th_iou=0.1, global_id=None):
    # assume each 2d seg id is not overlapped
    matches = [[]] * (len(index))
    chunk_st = 0
    for i, ind in enumerate(index):
        iou = get_iou(ind)
        if not isinstance(iou, list):
            iou = [iou]
        matches_i = [[]] * len(iou) 
        chunk_lt = chunk_st + len(iou)
        for j in range(len(iou)):
            sc = iou[j][:, 4].astype(float) / (iou[j][:, 2] + iou[j][:, 3] - iou[j][:, 4])
            gid = sc > th_iou
            matches_i[j] = iou[j][gid, :2].T
            if global_id is not None:
                matches_i[j][0] += global_id[chunk_st : chunk_lt][i]
                matches_i[j][1] += global_id[chunk_st : chunk_lt][i + 1]
        matches[i] = np.vstack(matches_i)
        chunk_st = chunk_lt
    return np.vstack(matches)

def iou_list_to_global_id(iou_list):
    get_iou = lambda z: read_vol(iou_list[z]) if isinstance(iou_list[z], str) else iou_list[z]
    index = range(len(iou_list))
    return ious_to_global_id(get_iou, index)

def iou_list_to_matches(iou_list, th_iou=0.1, global_id=None):
    get_iou = lambda z: read_vol(iou_list[z]) if isinstance(iou_list[z], str) else iou_list[z]
    index = range(len(iou_list))
    return ious_to_global_id(get_iou, index, th_iou, global_id)

def seg_to_remapped(seg, mapping):
    mapping_len = np.uint64(len(mapping))
    mapping_max = mapping.max()
    ind = seg < mapping_len
    seg[ind] = mapping[seg[ind]]  # if within mapping: relabel
    seg[np.logical_not(ind)] -= (
        mapping_len - mapping_max
    )  # if beyond mapping range, shift left
    return seg

def track_seg2d_vol(seg2d_vol, mapping=None, matches=None, global_id=None, iou=None, th_iou=0.1, th_sz=-1):
    # parallel version: demo/track_seg2d_list.py
    # assume can't load all seg2d into a volume
    if global_id is None:
        if iou is None:
            iou = seg2d_vol_to_iou2d(seg2d_vol)
        global_id = iou_list_to_global_id(iou) 
    if mapping is None:
        if matches is None:
            matches = iou_list_to_matches(iou, th_iou, global_id)
        matches = matches.astype(np.uint32)
        mapping = merge_id(matches[0], matches[1])
    
    for z in range(seg2d_vol.shape[0]):
        seg2d_vol[z] = seg_to_remapped(seg2d_vol[z] + global_id[z], mapping)

    if th_sz > 0:
        seg2d_vol = remove_small_objects(seg2d_vol, th_sz)
    return seg2d_vol
