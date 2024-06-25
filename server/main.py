import logging
from video_chat_server import ServerAPI

logging.basicConfig(filename='./logs/server.log', level=logging.DEBUG,
                    format='[%(asctime)s] (%(levelname)s) %(name)s.%(funcName)s: %(message)s',
                    datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)
if __name__ == '__main__':
    try:
        server = ServerAPI.VideoChatServerBuilder()\
            .set_api_endpoint()\
            .set_websocket_endpoint()\
            .set_user_manager()\
            .build()
        
        ServerAPI.init(server)
        ServerAPI.start()  # Blocking
    except KeyboardInterrupt:
        ServerAPI.kill()
        logger.info("Intercepted Keyboard Interrupt.")
        logger.info("Exiting main program execution.\n")
        exit()
