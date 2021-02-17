import sys
sys.path.append('../')
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')
from gi.repository import GObject, Gst, GstRtspServer
from common.is_aarch_64 import is_aarch64
from common.bus_call import bus_call
import os, argparse, json
import pyds
from utils.probe import osd_sink_pad_buffer_probe, api_probe
from utils.probe_in_experiments import screenshottest_probe
from utils.rtsp import create_source_bin, get_from_env


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
    #RTSPINPUT_URI = "rtsp://unecom1:test1234!@unecom.iptime.org/h264"
    RTSPINPUT_URI = "rtsp://admin:Tldosdptmdk2@223.171.56.203:554/profile2/media.smp"
    source = create_source_bin(0, RTSPINPUT_URI)
    if not source:
        sys.stderr.write(" Unable to create Source \n")
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
    capsfilter1 = Gst.ElementFactory.make("capsfilter", "capsfilter1")
    if not capsfilter1:
        sys.stderr.write(" Unable to create capsfilter1 \n")
    capsfilter2 = Gst.ElementFactory.make("capsfilter", "capsfilter2")
    if not capsfilter2:
        sys.stderr.write(" Unable to create capsfilter2 \n")
    encoder = Gst.ElementFactory.make("nvv4l2h264enc", "encoder")
    if not encoder:
        sys.stderr.write(" Unable to create encoder \n")
    rtppay = Gst.ElementFactory.make("rtph264pay", "rtppay")
    if not rtppay:
        sys.stderr.write(" Unable to create rtppay \n")
    sink = Gst.ElementFactory.make("udpsink", "udpsink")
    if not sink:
        sys.stderr.write(" Unable to create sink \n")


    ################################################################################
    ################### *** SET properties of each elements  *** ###################
    ################################################################################
    streammux.set_property('width', 1920)
    streammux.set_property('height', 1080)
    streammux.set_property('batch-size', 1)
    streammux.set_property('batched-push-timeout', 4000000)
    streammux.set_property('live-source', 1)

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


    caps1 = Gst.Caps.from_string("video/x-raw(memory:NVMM), format=I420")
    #caps = Gst.Caps.from_string("video/x-raw(memory:NVMM), format=RGBA")
    capsfilter1.set_property("caps", caps1)
    caps2 = Gst.Caps.from_string("video/x-raw(memory:NVMM), format=RGBA")
    capsfilter2.set_property("caps", caps2)
    encoder.set_property("bitrate", 2000000)

    UDP_MULTICAST_ADDRESS = '224.224.255.255'
    UDP_MULTICAST_PORT = 5400
    sink.set_property('host', UDP_MULTICAST_ADDRESS)
    sink.set_property('port', UDP_MULTICAST_PORT)
    sink.set_property('async', True)

    if not is_aarch64():
        # Use CUDA unified memory in the pipeline so frames
        # can be easily accessed on CPU in Python.
        mem_type = int(pyds.NVBUF_MEM_CUDA_UNIFIED)
        #streammux.set_property("nvbuf-memory-type", mem_type)
        nvvidconv.set_property("nvbuf-memory-type", mem_type)
        #nvvidconv2.set_property("nvbuf-memory-type", mem_type)
        #tiler.set_property("nvbuf-memory-type", mem_type)

    ################################################################################
    ################### *** Define srcs and sinks to be proved  *** ################
    ################################################################################
    sinkpad = streammux.get_request_pad("sink_0")
    if not sinkpad:
        sys.stderr.write(" Unable to get the sink pad of streammux \n")
    srcpad = source.get_static_pad("src")
    if not srcpad:
        sys.stderr.write(" Unable to get source pad of decoder \n")
    osdsinkpad = nvosd.get_static_pad("sink")
    if not osdsinkpad:
        sys.stderr.write(" Unable to get sink pad of nvosd \n")

    sgie_srcpad = sgie.get_static_pad("src")
    if not sgie_srcpad:
        sys.stderr.write(" Unable to get source pad of sgie_srcpad \n")
    osdsinkpad.add_probe(Gst.PadProbeType.BUFFER, osd_sink_pad_buffer_probe, 0)
    osdsinkpad.add_probe(Gst.PadProbeType.BUFFER, api_probe, 0)

    ################################################################################
    ############# *** ADD elements into the pipeline and LINK them *** #############
    ################################################################################
    print("Adding elements to Pipeline \n")
    pipeline.add(source)
    pipeline.add(streammux)
    pipeline.add(pgie)
    pipeline.add(sgie)
    pipeline.add(tracker)
    pipeline.add(nvvidconv)
    pipeline.add(nvosd)
    pipeline.add(queue)
    pipeline.add(nvvidconv2)
    pipeline.add(capsfilter1)
    pipeline.add(capsfilter2)
    pipeline.add(encoder)
    pipeline.add(rtppay)
    pipeline.add(sink)

    print("Linking elements in the Pipeline \n")
    srcpad.link(sinkpad)
    streammux.link(pgie)
    pgie.link(tracker)
    tracker.link(sgie)
    sgie.link(nvvidconv)
    nvvidconv.link(capsfilter2)
    capsfilter2.link(nvosd)
    nvosd.link(queue)
    queue.link(nvvidconv2)
    nvvidconv2.link(capsfilter1)
    capsfilter1.link(encoder)
    encoder.link(rtppay)
    rtppay.link(sink)

    # create an event loop and feed gstreamer bus mesages to it
    loop = GObject.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect ("message", bus_call, loop)

    # create a GstRtspStreamer insttance
    RTSPOUTPUTPORTNUM = get_from_env('RTSPOUTPUTPORTNUM', '9999')
    RTSPOUTPUTPATH = get_from_env('RTSPOUTPUTPATH', '/cnsi') # The output URL's path
    CODEC = "H264"
    server = GstRtspServer.RTSPServer.new()
    server.props.service = RTSPOUTPUTPORTNUM
    server.attach(None)
    factory = GstRtspServer.RTSPMediaFactory.new()
    factory.set_launch( "( udpsrc name=pay0 port=%d buffer-size=524288 protocol=GST_RTSP_LOWER_TRANS_TCP caps=\"application/x-rtp, media=video, clock-rate=90000, encoding-name=(string)%s, payload=96 \" )" % (UDP_MULTICAST_PORT, CODEC))
    factory.set_shared(True)
    server.get_mount_points().add_factory(RTSPOUTPUTPATH, factory)
    print("RTSP output stream service is ready \n")



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
