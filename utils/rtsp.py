import os, sys
import pyds
sys.path.append('../')
from common.is_aarch_64 import is_aarch64
from common.bus_call import bus_call
from gi.repository import GObject, Gst

def debug(s):
  print(s)
  pass

def get_from_env(v, d):
  if v in os.environ and '' != os.environ[v]:
    return os.environ[v]
  else:
    return d

def cb_newpad(decodebin, decoder_src_pad, data):
    debug("In cb_newpad")
    caps=decoder_src_pad.get_current_caps()
    gststruct=caps.get_structure(0)
    gstname=gststruct.get_name()
    source_bin=data
    features=caps.get_features(0)

    # Need to check if the pad created by the decodebin is for video and not
    # audio.
    if(gstname.find("video")!=-1):
        # Link the decodebin pad only if decodebin has picked nvidia
        # decoder plugin nvdec_*. We do this by checking if the pad caps contain
        # NVMM memory features.
        if features.contains("memory:NVMM"):
            # Get the source bin ghost pad
            bin_ghost_pad=source_bin.get_static_pad("src")
            if not bin_ghost_pad.set_target(decoder_src_pad):
                sys.stderr.write("ERROR: Failed to link decoder src pad to source bin ghost pad\n")
                sys.exit(1)
        else:
            sys.stderr.write("ERROR: Decodebin did not pick nvidia decoder plugin.\n")
            sys.exit(1)
def decodebin_child_added(child_proxy,Object,name,user_data):
    debug("Decodebin child added:" + name)
    if(name.find("decodebin") != -1):
        Object.connect("child-added",decodebin_child_added,user_data)
    if(is_aarch64() and name.find("nvv4l2decoder") != -1):
        debug("Seting bufapi_version")
        Object.set_property("bufapi-version",True)
def create_source_bin(index,uri):
    debug("Creating source bin")

    # Create a source GstBin to abstract this bin's content from the rest of the
    # pipeline
    bin_name="source-bin-%02d" %index
    debug(bin_name)
    nbin=Gst.Bin.new(bin_name)
    if not nbin:
        sys.stderr.write("ERROR: Unable to create source bin")
        sys.exit(1)

    # Source element for reading from the uri.
    # We will use decodebin and let it figure out the container format of the
    # stream and the codec and plug the appropriate demux and decode plugins.
    uri_decode_bin=Gst.ElementFactory.make("uridecodebin", "uri-decode-bin")
    if not uri_decode_bin:
        sys.stderr.write("ERROR: Unable to create uri decode bin")
        sys.exit(1)
    # We set the input uri to the source element
    uri_decode_bin.set_property("uri",uri)
    # Connect to the "pad-added" signal of the decodebin which generates a
    # callback once a new pad for raw data has beed created by the decodebin
    uri_decode_bin.connect("pad-added",cb_newpad,nbin)
    uri_decode_bin.connect("child-added",decodebin_child_added,nbin)

    # We need to create a ghost pad for the source bin which will act as a proxy
    # for the video decoder src pad. The ghost pad will not have a target right
    # now. Once the decode bin creates the video decoder and generates the
    # cb_newpad callback, we will set the ghost pad target to the video decoder
    # src pad.
    Gst.Bin.add(nbin,uri_decode_bin)
    bin_pad=nbin.add_pad(Gst.GhostPad.new_no_target("src",Gst.PadDirection.SRC))
    if not bin_pad:
        sys.stderr.write("ERROR: Failed to add ghost pad in source bin")
        sys.exit(1)
    return nbin
