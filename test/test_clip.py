"""Video file clip tests meant to be run with pytest."""
import os
import glob
import pytest
from moviepy.video.io.VideoFileClip import VideoFileClip

def test_event_video():
    """check whether copied event video clip can be renderizable using
    ``write_videofile``, establishing new video shared the same data
      that the orginal clip.
     """
    vid_path2 = "C:\\workspace\\Python_proj\\s3_videos_download\\eventVideos"
    o_path = "C:\\workspace\\Python_proj\\dvr_test_work"
    out_path = os.path.join(o_path, "copied_clip.mp4")
    videoFiles = [os.path.basename(x) for x in glob.glob(os.path.join(vid_path2, "*.[mM][pP]4"))]
    videoFiles.sort()

    for file in videoFiles:
        clip = VideoFileClip((os.path.join(vid_path2,file)))
        copied_clip = clip.copy()
        copied_clip.write_videofile(out_path)

        assert os.path.exists(out_path)
        copied_clip_file = VideoFileClip(out_path)

        assert copied_clip.fps == copied_clip_file.fps
        assert list(copied_clip.size) == copied_clip_file.size
        assert isinstance(copied_clip.reader,type(copied_clip_file.reader))

if __name__ == "__main__":
    pytest.main()

