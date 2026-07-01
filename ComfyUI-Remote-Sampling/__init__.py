from .nodes.remote_sampling_local import RemoteSamplingLocal
from .nodes.remote_sampling_remote import RemoteSamplingRemote


NODE_CLASS_MAPPINGS = {
    "Remote_Sampling_local": RemoteSamplingLocal,
    "Remote_Sampling_remote": RemoteSamplingRemote,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Remote_Sampling_local": "Remote Sampling Local",
    "Remote_Sampling_remote": "Remote Sampling Remote",
}
