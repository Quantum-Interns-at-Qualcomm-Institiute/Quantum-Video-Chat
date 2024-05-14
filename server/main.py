import logging 
from .api import ServerAPI, SocketAPI
from .server import SocketState, VideoChatServer

logging.basicConfig(filename='./logs/server.log', level=logging.DEBUG,
                    format='[%(asctime)s] (%(levelname)s) %(name)s.%(funcName)s: %(message)s',
                    datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)
if __name__ == '__main__':
    try:
        server = VideoChatServer(ServerAPI.DEFAULT_ENDPOINT, SocketAPI, SocketState)
        # server.set_host()
        ServerAPI.init(server)
        ServerAPI.start()  # Blocking
    except KeyboardInterrupt:
        ServerAPI.kill()
        logger.info("Intercepted Keyboard Interrupt.")
        logger.info("Exiting main program execution.\n")
        exit()