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

// TODO: Remove after status has been properly implemented
const statuses = ["waiting", "good", "bad"];

const initClientContext = {
    status: statuses[0],
    roomId: '',
    joinRoom: async (peer_id?: string) => {},
    leaveRoom: async () => {},
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
	const [status, _setStatus] = useState(initClientContext.status);
    const [roomId, _setRoomId] = useState(initClientContext.roomId);
    const [onFrame, _setOnFrame] = useState(initClientContext.video.onFrame);
    const [messages, _setMessages] = useState(initClientContext.chat.messages);


    const navigate = useNavigate();

    const joinRoom = async (room_id?: string) => {
        navigate('/loading');
        var res = await services.joinRoom(room_id)
        if(res) {
            console.log(`(ClientContext): ERROR - ${res}`)
            return res;
        }
    }

    const leaveRoom = async () => {
        navigate('/');
        var res = await services.leaveRoom();
        if(res) {
            console.log(`(ClientContext): ERROR - ${res}`)
            return res;
        }
    }

    // Establish middleware listeners on initial render
    useEffect(() => {
        console.log(`(ClientContext): Initialization.`);

        // Event emitted when Python subprocess to ready to proceed with chatting
        window.electronAPI.ipcListen('ready', (e: IpcMainEvent, id: string) => {
            console.log(`(renderer): Python backend readied.`)

            // Navigate away from Splash page after Python is ready
            if(window.location.pathname === '/loading') {
                console.log('(renderer): Closing Splash page.')
                navigate('/');
            } else {
                console.log(`(ClientContext): CRITICAL - Received 'ready' event outside of loading screen.`)
            }
        })

        // Inform main process that ClientContext is ready for IPC communication
        console.log('(renderer): Renderer Ready');
        window.electronAPI.rendererReady();
    }, []);


    // Middleware for managing rooms
    useEffect(() => {
        console.log(`(ClientContext): Setting up room management.`)
        
        // Event emitted when server puts client in a room
        window.electronAPI.ipcListen('room-id', (e: IpcMainEvent, room_id: string) => {
            console.log(`(ClientContext): Received room_id '${room_id}'.`)
            if(window.location.pathname === '/loading') {
                _setRoomId(room_id);
                navigate('/session');
            } else {
                console.log(`(ClientContext): CRITICAL - Received 'room-id' event outside of loading screen.`)
            }
        });

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
            status: status,
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