import argparse
import asyncio
import logging
import math

import cv2
import numpy
from aiortc import (
    RTCIceCandidate,
    RTCPeerConnection,
    RTCSessionDescription,
    VideoStreamTrack,
)
from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder, MediaStreamTrack
from aiortc.contrib.signaling import BYE, add_signaling_arguments, create_signaling
from av import VideoFrame, AudioFrame


# class FlagVideoStreamTrack(VideoStreamTrack):
#     """
#     A video track that returns an animated flag.
#     """

#     def __init__(self):
#         super().__init__()  # don't forget this!
#         self.counter = 0
#         height, width = 480, 640

#         # generate flag
#         data_bgr = numpy.hstack(
#             [
#                 self._create_rectangle(
#                     width=213, height=480, color=(255, 0, 0)
#                 ),  # blue
#                 self._create_rectangle(
#                     width=214, height=480, color=(255, 255, 255)
#                 ),  # white
#                 self._create_rectangle(width=213, height=480, color=(0, 0, 255)),  # red
#             ]
#         )

#         # shrink and center it
#         M = numpy.float32([[0.5, 0, width / 4], [0, 0.5, height / 4]])
#         data_bgr = cv2.warpAffine(data_bgr, M, (width, height))

#         # compute animation
#         omega = 2 * math.pi / height
#         id_x = numpy.tile(numpy.array(range(width), dtype=numpy.float32), (height, 1))
#         id_y = numpy.tile(
#             numpy.array(range(height), dtype=numpy.float32), (width, 1)
#         ).transpose()

#         self.frames = []
#         for k in range(30):
#             phase = 2 * k * math.pi / 30
#             map_x = id_x + 10 * numpy.cos(omega * id_x + phase)
#             map_y = id_y + 10 * numpy.sin(omega * id_x + phase)
#             self.frames.append(
#                 VideoFrame.from_ndarray(
#                     cv2.remap(data_bgr, map_x, map_y, cv2.INTER_LINEAR), format="bgr24"
#                 )
#             )

#     async def recv(self):
#         pts, time_base = await self.next_timestamp()

#         frame = self.frames[self.counter % 30]
#         frame.pts = pts
#         frame.time_base = time_base
#         self.counter += 1
#         return frame

#     def _create_rectangle(self, width, height, color):
#         data_bgr = numpy.zeros((height, width, 3), numpy.uint8)
#         data_bgr[:, :] = color
#         return data_bgr

# Possible encoding method
# class EncodeRelayStreamTrack(MediaStreamTrack):
#     def __init__(self, relay, source: MediaStreamTrack, buffered: bool) -> None:
#         super().__init__()
#         self.kind = source.kind
#         self._relay = relay
#         self._source: Optional[MediaStreamTrack] = source
#         self._buffered = buffered

#         self._frame: Optional[Frame] = None
#         self._queue: Optional[asyncio.Queue[Optional[Frame]]] = None
#         self._new_frame_event: Optional[asyncio.Event] = None

#         if self._buffered:
#             self._queue = asyncio.Queue()
#         else:
#             self._new_frame_event = asyncio.Event()

#     async def recv(self):
#         if self.readyState != "live":
#             raise MediaStreamError

#         self._relay._start(self)

#         if self._buffered:
#             self._frame = await self._queue.get()
#         else:
#             await self._new_frame_event.wait()
#             self._new_frame_event.clear()

#         if self._frame is None:
#             self.stop()
#             raise MediaStreamError
#         return encode(self._frame)

async def run(pc, player: MediaPlayer, recorder, signaling, role):
    def add_tracks():
        if player and player.audio:
            pc.addTrack(player.audio)

        if player and player.video:
            pc.addTrack(player.video)
        # else:
        #     pc.addTrack(FlagVideoStreamTrack())

    @pc.on("track")
    async def on_track(track: MediaStreamTrack):
        print("Receiving %s" % track.kind)
        # recorder.addTrack(track)
        if track.kind == "video":
            track: VideoStreamTrack = track
            while True:
                frame = await track.recv()
                frame = frame.to_ndarray(format="bgr24")
                cv2.imshow("recv", frame)
                cv2.waitKey(1)

    # connect signaling
    await signaling.connect()

    if role == "offer":
        # send offer
        add_tracks()
        await pc.setLocalDescription(await pc.createOffer())
        await signaling.send(pc.localDescription)

    # consume signaling
    while True:
        obj = await signaling.receive()

        if isinstance(obj, RTCSessionDescription):
            await pc.setRemoteDescription(obj)
            await recorder.start()

            if obj.type == "offer":
                # send answer
                add_tracks()
                await pc.setLocalDescription(await pc.createAnswer())
                await signaling.send(pc.localDescription)
        elif isinstance(obj, RTCIceCandidate):
            await pc.addIceCandidate(obj)
        elif obj is BYE:
            print("Exiting")
            break

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Video stream from the command line")
    parser.add_argument("role", choices=["offer", "answer"])
    parser.add_argument("--play-from", help="Read the media from a file and sent it."),
    parser.add_argument("--record-to", help="Write received media to a file."),
    parser.add_argument("--verbose", "-v", action="count")
    
    args = parser.parse_args()

    HOST = '127.0.0.1'
    # HOST = 'IP ADDRESS'
    # HOST = '100.80.231.89'
    PORT = '65431'
    signaling_parser = argparse.ArgumentParser()
    add_signaling_arguments(signaling_parser)
    signaling_args = signaling_parser.parse_args(
        ['--signaling', 'tcp-socket', '--signaling-host', HOST, '--signaling-port', PORT]
    )

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    # create signaling and peer connection
    signaling = create_signaling(signaling_args)
    pc = RTCPeerConnection()

    # create media source
    if args.play_from:
        player = MediaPlayer(args.play_from)
    else:
        player = None
    player = MediaPlayer('default:none', format='avfoundation', options={
        'framerate': '30', 
        'video_size': '640x480'
    })

    # create media sink
    if args.record_to:
        recorder = MediaRecorder(args.record_to)
    else:
        recorder = MediaBlackhole()
    # recorder = MediaRecorder('recording.mp4')

    # run event loop
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            run(
                pc=pc,
                player=player,
                recorder=recorder,
                signaling=signaling,
                role=args.role,
            )
        )
    except KeyboardInterrupt:
        pass
    finally:
        # cleanup
        loop.run_until_complete(recorder.stop())
        loop.run_until_complete(signaling.close())
        loop.run_until_complete(pc.close())