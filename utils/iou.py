import numpy as np
from scipy.optimize import linear_sum_assignment

def find_matched_indice(iou):
    x,y = linear_sum_assignment(-iou)
    return np.array(list(zip(x,y)))

def compute_iou(boxes_a, boxes_b):
    """ Compute overlap between boxes_a and boxes_b
    Args:
        boxes_a: tensor (num_boxes_a, 4)
        boxes_b: tensor (num_boxes_b, 4)
    Returns:
        overlap: tensor (num_boxes_a, num_boxes_b)
    """
    # boxes_a => num_boxes_a, 1, 4
    boxes_a = np.expand_dims(boxes_a, 1)

    # boxes_b => 1, num_boxes_b, 4
    boxes_b = np.expand_dims(boxes_b, 0)
    top_left = np.maximum(boxes_a[..., :2], boxes_b[..., :2])
    bot_right = np.minimum(boxes_a[..., 2:], boxes_b[..., 2:])

    overlap_area = compute_area(top_left, bot_right)
    area_a = compute_area(boxes_a[..., :2], boxes_a[..., 2:])
    area_b = compute_area(boxes_b[..., :2], boxes_b[..., 2:])
    print(area_a, area_b, overlap_area)
    overlap = overlap_area / (area_a + area_b - overlap_area)

    return overlap

def compute_area(top_left, bot_right):
    """ Compute area given top_left and bottom_right coordinates
    Args:
        top_left: tensor (num_boxes, 2)
        bot_right: tensor (num_boxes, 2)
    Returns:
        area: tensor (num_boxes,)
    """
    # top_left: N x 2
    # bot_right: N x 2
    hw = bot_right - top_left
    area = hw[..., 0] * hw[..., 1]

    return area
