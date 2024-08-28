import type { IpcMainEvent } from "electron";
import { useState, createContext, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import services from './services';

// TODO: Remove placeholder when chat is properly implemented
const initMessages = [
    {
        time: "ti:me",
        name: "Client 1",
        body: "text from client 1",
    },
    {
        time: "ti:me",
        name: "Client 2",
        body: "text from client 2",
    },
]

const initClientContext = {
    roomId: '',
    joinRoom: (peer_id?: string) => {},
    leaveRoom: () => {},
    video: {
        onFrame: () => {},
    },
    chat: {
        messages: initMessages,
        sendMessage: services.chat.sendMessage,
    }
}

export const ClientContext = createContext(initClientContext);

export function ClientContextProvider({ children } ) {
    const [roomId, _setRoomId] = useState(initClientContext.roomId);
    const [onFrame, _setOnFrame] = useState(initClientContext.video.onFrame);
    const [messages, _setMessages] = useState(initClientContext.chat.messages);

    const navigate = useNavigate();

    const joinRoom = (room_id?: string) => {
        services.joinRoom(room_id)
        navigate('/loading');
    }

    const leaveRoom = () => {
        services.leaveRoom();
        navigate('/');
    }

    // Establish middleware listeners on initial render
    useEffect(() => {
        console.log(`(ClientContext): Initialization.`);

        // Event emitted when Python subprocess to ready to proceed with chatting
        window.electronAPI.ipcListen('ready', (e: IpcMainEvent, id: string) => {
            console.log(`(renderer): Python backend readied.`)

            // Navigate away from Splash page after receiving self_id
            if(window.location.pathname === '/loading') {
                console.log('(renderer): Closing Splash page.')
                navigate('/');
            }
        })

        // Inform main process that ClientContext is ready for IPC communication
        console.log('(renderer): Renderer Ready');
        window.electronAPI.rendererReady();
    }, []);


    // Middleware for managing sessions
    useEffect(() => {
        console.log(`(ClientContext): Setting up session management.`)
        

    }, []);


    // Middleware for communication during a session
    useEffect(() => {
        console.log(`(ClientContext): Setting up peer-to-peer communication.`)

        window.electronAPI.ipcListen('message', (e: IpcMainEvent, messageData: Object) => {
            console.log(`(renderer): Received chat message with Object structure ${JSON.stringify(messageData)}`)
            _setMessages([...messages, messageData]);
        })

        window.electronAPI.ipcListen('frame',
        (
            event: IpcMainEvent,
            canvasData: {
                frame: Uint8Array;
                height: number;
                width: number
            }
        ) => {
            onFrame(canvasData);
        });
    }, []);

    return (
        <ClientContext.Provider value={{
            roomId: roomId,
            joinRoom: joinRoom,
            leaveRoom: leaveRoom,
            video: {
                onFrame: onFrame
            },
            chat: {
                messages: messages,
                sendMessage: services.chat.sendMessage
            }
        }}>
            {children}
        </ClientContext.Provider>
    )
}