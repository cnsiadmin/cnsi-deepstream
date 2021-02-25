import pyds
from gi.repository import GObject, Gst
from utils.api import send_no_helmet_event
#from .parser import ssd96_custom_parser, add_secondary_ssd96_obj_meta_to_frame
import cv2
import numpy as np
import threading

PGIE_CLASS_ID_PERSON = 0
PGIE_CLASS_ID_BAG = 1
PGIE_CLASS_ID_FACE = 2
CNT_nonHelmet = 0

def debug_probe(pad,info,u_data):
    print("It is running")
    return Gst.PadProbeReturn.OK


def osd_sink_pad_buffer_probe(pad,info,u_data):
    frame_number=0
    #Intiallizing object counter with 0.
    obj_counter = {
        PGIE_CLASS_ID_PERSON:0,
        PGIE_CLASS_ID_BAG:0,
        PGIE_CLASS_ID_FACE:0
    }
    num_rects=0

    gst_buffer = info.get_buffer()
    if not gst_buffer:
        print("Unable to get GstBuffer ")
        return

    # Retrieve batch metadata from the gst_buffer
    # Note that pyds.gst_buffer_get_nvds_batch_meta() expects the
    # C address of gst_buffer as input, which is obtained with hash(gst_buffer)
    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
    l_frame = batch_meta.frame_meta_list
    while l_frame is not None:
        try:
            # Note that l_frame.data needs a cast to pyds.NvDsFrameMeta
            # The casting is done by pyds.glist_get_nvds_frame_meta()
            # The casting also keeps ownership of the underlying memory
            # in the C code, so the Python garbage collector will leave
            # it alone.
            #frame_meta = pyds.glist_get_nvds_frame_meta(l_frame.data)
            frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
        except StopIteration:
            break
        #print(dir(frame_meta))
        frame_number=frame_meta.frame_num
        num_rects = frame_meta.num_obj_meta
        l_obj=frame_meta.obj_meta_list
        while l_obj is not None:
            try:
                # Casting l_obj.data to pyds.NvDsObjectMeta
                #obj_meta=pyds.glist_get_nvds_object_meta(l_obj.data)
                obj_meta=pyds.NvDsObjectMeta.cast(l_obj.data)
            except StopIteration:
                break
            obj_counter[obj_meta.class_id] += 1
            obj_meta.rect_params.border_color.set(0.0, 0.0, 1.0, 0.0)
            try:
                l_obj=l_obj.next
            except StopIteration:
                break

        # Acquiring a display meta object. The memory ownership remains in
        # the C code so downstream plugins can still access it. Otherwise
        # the garbage collector will claim it when this probe function exits.
        display_meta=pyds.nvds_acquire_display_meta_from_pool(batch_meta)
        display_meta.num_labels = 1
        py_nvosd_text_params = display_meta.text_params[0]
        # Setting display text to be shown on screen
        # Note that the pyds module allocates a buffer for the string, and the
        # memory will not be claimed by the garbage collector.
        # Reading the display_text field here will return the C address of the
        # allocated string. Use pyds.get_string() to get the string content.
        py_nvosd_text_params.display_text = "Frame={} People={}".format(frame_number, obj_counter[PGIE_CLASS_ID_PERSON])
        # Now set the offsets where the string should appear
        py_nvosd_text_params.x_offset = 10
        py_nvosd_text_params.y_offset = 12

        # Font , font-color and font-size
        py_nvosd_text_params.font_params.font_name = "Serif"
        py_nvosd_text_params.font_params.font_size = 10
        # set(red, green, blue, alpha); set to White
        py_nvosd_text_params.font_params.font_color.set(1.0, 1.0, 1.0, 1.0)

        # Text background color
        py_nvosd_text_params.set_bg_clr = 1
        # set(red, green, blue, alpha); set to Black
        py_nvosd_text_params.text_bg_clr.set(0.0, 0.0, 0.0, 1.0)
        # Using pyds.get_string() to get display_text as string
        print(pyds.get_string(py_nvosd_text_params.display_text))
        pyds.nvds_add_display_meta_to_frame(frame_meta, display_meta)
        try:
            l_frame=l_frame.next
        except StopIteration:
            break

    return Gst.PadProbeReturn.OK

def osd_sink_pad_buffer_probe_dummy(pad,info,u_data):
    print("osd_sink_pad_buffer_probe_dummy")
    return Gst.PadProbeReturn.OK


def api_probe(pad, info, u_data):

    print("camID : {}".format(u_data))

    global CNT_nonHelmet

    people_cnt = 0
    helmet_cnt = 0

    gst_buffer = info.get_buffer()
    if not gst_buffer:
        print("Unable to get GstBuffer ")
        return
    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
    l_frame = batch_meta.frame_meta_list


    while l_frame is not None:
        try:
            frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
            frame_number=frame_meta.frame_num
        except StopIteration:
            break
        #@@@@@@@@@@@@ FRAME METADATA @@@@@@@@@@@@@@@@@

        l_obj=frame_meta.obj_meta_list
        num_rects = frame_meta.num_obj_meta

        #*********** OBJECT METADATA ******************
        while l_obj is not None:
            try:
                obj_meta=pyds.NvDsObjectMeta.cast(l_obj.data)
            except StopIteration:
                break
            if obj_meta.unique_component_id == 1:
                people_cnt = people_cnt + 1
            elif obj_meta.unique_component_id == 2:
                helmet_cnt = helmet_cnt + 1
            try:
                l_obj=l_obj.next
            except StopIteration:
                break
        #*********** OBJECT METADATA ******************
        if people_cnt > 0 and people_cnt > helmet_cnt:
            CNT_nonHelmet +=1
        else:
            CNT_nonHelmet = 0

        if CNT_nonHelmet > 60:
            try:
                screenshot = frame2image(gst_buffer, frame_meta)
                url_ = "http://unecom.iptime.org:8080/riskzero_ys/uapi/inputEventVideoAnalysis"
                thread_send = threading.Thread(target=send_no_helmet_event, args=(url_, screenshot, u_data))
                thread_send.start()
                print("send")

            except Exception as e:
                print(e)
            CNT_nonHelmet = 0
        #@@@@@@@@@@@@ FRAME META DATA @@@@@@@@@@@@@@@@@
        try:
            l_frame = l_frame.next
        except StopIteration:
            break
    return Gst.PadProbeReturn.OK


def frame2image(gst_buffer, frame_meta):
    n_frame=pyds.get_nvds_buf_surface(hash(gst_buffer),frame_meta.batch_id)
    '''
        get_nvds_buf_surface는 segmentation fault 에러를 냅니다.
        반드시 아래와 같이 앞 엘리먼트인 nvvidconv의 memory type을 다음과 같이 setting해주어야 합니다.
        예시를 보기 위해 screenshot_test.py를 확인하세요.
        mem_type = int(pyds.NVBUF_MEM_CUDA_UNIFIED)
        nvvidconv.set_property("nvbuf-memory-type", mem_type)
    '''
    image=np.array(n_frame,copy=True,order='C')
    image=cv2.cvtColor(image,cv2.COLOR_RGBA2BGRA)
    return image
