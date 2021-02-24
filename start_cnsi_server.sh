#!/bin/bash
docker restart cnsi_deepstream
docker exec cnsi_deepstream python3 /home/files/cnsi-deepstream/back_to_back_tracked_rtsp.py
