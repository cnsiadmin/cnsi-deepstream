#!/bin/bash
# docker restart cnsi_deepstream
docker exec cnsi_deepstream python3 /home/files/cnsi-deepstream/back_to_back_tracked_rtsp_1.py /home/files/cnsi-deepstream/configs/headhelmet.json &
docker exec cnsi_deepstream python3 /home/files/cnsi-deepstream/back_to_back_tracked_rtsp_2.py /home/files/cnsi-deepstream/configs/headhelmet.json &
