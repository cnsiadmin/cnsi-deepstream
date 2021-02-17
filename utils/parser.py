import sys
import pyds
import numpy as np
from .post_process import predict_onebatch
import .anchor
sys.path.append("../")
import gi
gi.require_version("Gst", "1.0")
from gi.repository import GObject, Gst
import ctypes

#param = {"ratios": [[2], [2, 3], [2, 3], [2]],
#                           "scales": [0.1, 0.3, 0.6, 0.9, 1.05],
#                           "fm_sizes": [12, 6, 3, 1],
#                           "image_size": 96}
#default_boxes = anchor.generate_default_boxes(param)

def layer_finder(output_layer_info, name):
    """ Return the layer contained in output_layer_info which corresponds
        to the given name.
    """
    for layer in output_layer_info:
        # dataType == 0 <=> dataType == FLOAT
        #print(layer.layerName)
        if layer.dataType == 0 and layer.layerName == name:
            return layer
        #if layer.layerName == name:
        #    print("layer name : {}, data type : {}".format(layer.layerName, layer.dataType))
        #    return layer
    return None

def ssd96_custom_parser(layers_info):

    model_1 = layer_finder(layers_info, "model_1")
    model_1_1 = layer_finder(layers_info, "model_1_1")

    if not model_1 or not model_1_1:
        sys.stderr.write("ERROR: missing some layers\n")
        return Gst.PadProbeReturn.OK

    if model_1.buffer:
        ptr = ctypes.cast(pyds.get_ptr(model_1.buffer), ctypes.POINTER(ctypes.c_float))
        confs = np.ctypeslib.as_array(ptr, shape=(850, 3))
        print(confs)

    if model_1_1.buffer:
        ptr = ctypes.cast(pyds.get_ptr(model_1_1.buffer), ctypes.POINTER(ctypes.c_float))
        locs = np.ctypeslib.as_array(ptr, shape=(850,4))
        print(locs)

    #boxes, classes, scores = predict_onebatch(confs, locs, default_boxes, 3, conf_thresh=0.5)
    #print("boxes")
    #print(boxes)
    #print("classes")
    #print(classes)
    #print("scores")
    #print(scores)

    object_list = []
    '''
    if len(boxes) > 0:
        for i, (_box, _class, _score) in enumerate(zip(boxes, classes, scores)):
            print(i, "-obj : ", _class)
            res = pyds.NvDsInferObjectDetectionInfo()
            res.detectionConfidence = _score
            res.classId = int(_class)

            print(_box.shape)

            x1,y1,x2,y2 = _box
            res.left = x1
            res.top = y1
            res.width = x2 - x1
            res.height = y2 - y1
            object_list.append(res)
    '''


    return object_list


def add_secondary_ssd96_obj_meta_to_frame(sub_object, batch_meta, frame_meta, obj_meta, label_names):
    """ Inserts an object into the metadata """
    # this is a good place to insert objects into the metadata.
    # Here's an example of inserting a single object.
    sub_obj_meta = pyds.nvds_acquire_obj_meta_from_pool(batch_meta)
    # Set bbox properties. These are in input resolution.

    ref_top, ref_left, ref_height, ref_width = obj_meta.rect_params.top, obj_meta.rect_params.left, obj_meta.rect_params.height, obj_meta.rect_params.width
    rect_params = sub_obj_meta.rect_params
    rect_params.left = int(ref_width * sub_object.left + ref_left)
    rect_params.top = int(ref_height * sub_object.top + ref_top)
    rect_params.width = int(ref_width * sub_object.width)
    rect_params.height = int(ref_height * sub_object.height)

    # Semi-transparent yellow backgroud
    rect_params.has_bg_color = 0
    rect_params.bg_color.set(1, 1, 0, 0.4)

    # Red border of width 3
    rect_params.border_width = 3
    rect_params.border_color.set(1, 0, 0, 1)

    # Set object info including class, detection confidence, etc.
    sub_obj_meta.confidence = sub_object.detectionConfidence
    sub_obj_meta.class_id = sub_object.classId

    # There is no tracking ID upon detection. The tracker will
    # assign an ID.
    sub_obj_meta.object_id = UNTRACKED_OBJECT_ID

    lbl_id = sub_object.classId
    if lbl_id >= len(label_names):
        lbl_id = 0

    # Set the object classification label.
    sub_obj_meta.obj_label = label_names[lbl_id]

    # Set display text for the object.
    txt_params = sub_obj_meta.text_params
    if txt_params.display_text:
        pyds.free_buffer(txt_params.display_text)

    txt_params.x_offset = int(rect_params.left)
    txt_params.y_offset = max(0, int(rect_params.top) - 10)
    txt_params.display_text = (
        label_names[lbl_id] + " " + "{:04.3f}".format(sub_object.detectionConfidence)
    )
    # Font , font-color and font-size
    txt_params.font_params.font_name = "Serif"
    txt_params.font_params.font_size = 10
    # set(red, green, blue, alpha); set to White
    txt_params.font_params.font_color.set(1.0, 1.0, 1.0, 1.0)

    # Text background color
    txt_params.set_bg_clr = 1
    # set(red, green, blue, alpha); set to Black
    txt_params.text_bg_clr.set(0.0, 0.0, 0.0, 1.0)

    # Inser the object into current frame meta
    # This object has no parent
    pyds.nvds_add_obj_meta_to_frame(frame_meta, sub_obj_meta, None)
