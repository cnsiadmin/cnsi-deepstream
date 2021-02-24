import sys
sys.path.append('../')
import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst
from common.is_aarch_64 import is_aarch64
from common.bus_call import bus_call
import os, argparse, json
import pyds
from utils.probe import osd_sink_pad_buffer_probe

def main(config):
    # Standard GStreamer initialization
    input_video = config["input_video"]
    output_video = config["output_video"]
    GObject.threads_init()
    Gst.init(None)

    ################################################################################
    ######################### *** CREATE Gst Elements *** ##########################
    ################################################################################
    # 0. Create gstreamer elements
    # Create Pipeline element that will form a connection of other elements
    print("Creating Pipeline \n ")
    pipeline = Gst.Pipeline()
    if not pipeline:
        sys.stderr.write(" Unable to create Pipeline \n")
    # 1. Source element for reading from the file
    print("Creating Source \n ")
    source = Gst.ElementFactory.make("filesrc", "file-source")
    if not source:
        sys.stderr.write(" Unable to create Source \n")
    # 2. Since the data format in the input file is elementary h264 stream,
    # we need a h264parser
    print("Creating H264Parser \n")
    h264parser = Gst.ElementFactory.make("h264parse", "h264-parser")
    if not h264parser:
        sys.stderr.write(" Unable to create h264 parser \n")
    # 3. Use nvdec_h264 for hardware accelerated decode on GPU
    print("Creating Decoder \n")
    decoder = Gst.ElementFactory.make("nvv4l2decoder", "nvv4l2-decoder")
    if not decoder:
        sys.stderr.write(" Unable to create Nvv4l2 Decoder \n")
    # 4. Create nvstreammux instance to form batches from one or more sources.
    streammux = Gst.ElementFactory.make("nvstreammux", "Stream-muxer")
    if not streammux:
        sys.stderr.write(" Unable to create NvStreamMux \n")
    # 5. Use nvinfer to run inferencing on decoder's output,
    # behaviour of inferencing is set through config file
    pgie = Gst.ElementFactory.make("nvinfer", "primary-inference")
    if not pgie:
        sys.stderr.write(" Unable to create pgie \n")

    sgie = Gst.ElementFactory.make("nvinfer", "secondary-inference")
    if not sgie:
        sys.stderr.write(" Unable to create sgie \n")

    tracker = Gst.ElementFactory.make("nvtracker", "tracker")
    if not tracker:
        sys.stderr.write(" Unable to create tracker \n")

    # 6. Use convertor to convert from NV12 to RGBA as required by nvosd
    nvvidconv = Gst.ElementFactory.make("nvvideoconvert", "convertor")
    if not nvvidconv:
        sys.stderr.write(" Unable to create nvvidconv \n")
    # 7. Create OSD to draw on the converted RGBA buffer
    nvosd = Gst.ElementFactory.make("nvdsosd", "onscreendisplay")
    if not nvosd:
        sys.stderr.write(" Unable to create nvosd \n")

    # 8. Finally encode and save the osd output
    queue = Gst.ElementFactory.make("queue", "queue")
    if not queue:
        sys.stderr.write(" Unable to create queue \n")
    nvvidconv2 = Gst.ElementFactory.make("nvvideoconvert", "convertor2")
    if not nvvidconv2:
        sys.stderr.write(" Unable to create nvvidconv2 \n")
    capsfilter = Gst.ElementFactory.make("capsfilter", "capsfilter")
    if not capsfilter:
        sys.stderr.write(" Unable to create capsfilter \n")
    encoder = Gst.ElementFactory.make("avenc_mpeg4", "encoder")
    if not encoder:
        sys.stderr.write(" Unable to create encoder \n")
    codeparser = Gst.ElementFactory.make("mpeg4videoparse", "mpeg4-parser")
    if not codeparser:
        sys.stderr.write(" Unable to create codeparser \n")
    container = Gst.ElementFactory.make("qtmux", "qtmux")
    if not container:
        sys.stderr.write(" Unable to create container \n")
    sink = Gst.ElementFactory.make("filesink", "filesink")
    if not sink:
        sys.stderr.write(" Unable to create sink \n")


    ################################################################################
    ################### *** SET properties of each elements  *** ###################
    ################################################################################
    source.set_property('location', input_video)
    streammux.set_property('width', 960)
    streammux.set_property('height', 544)
    streammux.set_property('batch-size', 1)
    streammux.set_property('batched-push-timeout', 4000000)

    pgie.set_property('config-file-path', config['pgie_config'])
    sgie.set_property('config-file-path', config['sgie_config'])

    tracker_prop = config["tracker"]
    tracker_width=tracker_prop['tracker-width']
    tracker_height=tracker_prop['tracker-height']
    tracker_gpu_id=tracker_prop['gpu-id']
    tracker_ll_lib_file=tracker_prop['ll-lib-file']
    tracker_enable_batch_process=tracker_prop['enable-batch-process']
    tracker.set_property('tracker-width', tracker_width)
    tracker.set_property('tracker-height', tracker_height)
    tracker.set_property('gpu_id', tracker_gpu_id)
    tracker.set_property('ll-lib-file', tracker_ll_lib_file)
    #tracker.set_property('ll-config-file', tracker_ll_config_file)
    tracker.set_property('enable_batch_process', tracker_enable_batch_process)
    tracker.set_property('display-tracking-id', 1)

    caps = Gst.Caps.from_string("video/x-raw, format=I420")
    capsfilter.set_property("caps", caps)
    encoder.set_property("bitrate", 2000000)
    sink.set_property("location", output_video)
    sink.set_property("sync", 0)
    sink.set_property("async", 0)

    ################################################################################
    ################### *** Define srcs and sinks to be proved  *** ################
    ################################################################################
    sinkpad = streammux.get_request_pad("sink_0")
    if not sinkpad:
        sys.stderr.write(" Unable to get the sink pad of streammux \n")
    srcpad = decoder.get_static_pad("src")
    if not srcpad:
        sys.stderr.write(" Unable to get source pad of decoder \n")
    osdsinkpad = nvosd.get_static_pad("sink")
    if not osdsinkpad:
        sys.stderr.write(" Unable to get sink pad of nvosd \n")

    sgie_srcpad = sgie.get_static_pad("src")
    if not sgie_srcpad:
        sys.stderr.write(" Unable to get source pad of sgie_srcpad \n")
    osdsinkpad.add_probe(Gst.PadProbeType.BUFFER, osd_sink_pad_buffer_probe, 0)
    #sgie_srcpad.add_probe(Gst.PadProbeType.BUFFER, sgie_src_pad_buffer_probe, 0)

    ################################################################################
    ############# *** ADD elements into the pipeline and LINK them *** #############
    ################################################################################
    print("Adding elements to Pipeline \n")
    pipeline.add(source)
    pipeline.add(h264parser)
    pipeline.add(decoder)
    pipeline.add(streammux)
    pipeline.add(pgie)
    pipeline.add(sgie)
    pipeline.add(tracker)
    pipeline.add(nvvidconv)
    pipeline.add(nvosd)
    pipeline.add(queue)
    pipeline.add(nvvidconv2)
    pipeline.add(capsfilter)
    pipeline.add(encoder)
    pipeline.add(codeparser)
    pipeline.add(container)
    pipeline.add(sink)

    print("Linking elements in the Pipeline \n")
    source.link(h264parser)
    h264parser.link(decoder)
    srcpad.link(sinkpad)
    streammux.link(pgie)
    pgie.link(tracker)
    tracker.link(sgie)
    sgie.link(nvvidconv)
    nvvidconv.link(nvosd)
    nvosd.link(queue)
    queue.link(nvvidconv2)
    nvvidconv2.link(capsfilter)
    capsfilter.link(encoder)
    encoder.link(codeparser)
    codeparser.link(container)
    container.link(sink)

    # create an event loop and feed gstreamer bus mesages to it
    loop = GObject.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect ("message", bus_call, loop)

    # start play back and listen to events
    print("Starting pipeline \n")
    pipeline.set_state(Gst.State.PLAYING)
    try:
        loop.run()
    except:
        pass
    # cleanup
    pipeline.set_state(Gst.State.NULL)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('config', metavar='config_file',
                        help='path to config file.')
    args = parser.parse_args()
    config = args.config
    with open(config, 'r') as file:
        config = json.load(file)
    main(config)
