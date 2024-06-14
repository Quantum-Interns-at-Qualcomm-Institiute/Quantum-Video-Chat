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
    selfId: '',
    peerId: '',
    joinPeer: services.joinPeer,
    video: {
        onFrame: () => {},
    },
    chat: {
        messages: initMessages,
        sendMessage: services.chat.sendMessage,
    },
    quitSession: services.quitSession,
}

export const ClientContext = createContext(initClientContext);

export function ClientContextProvider({ children } ) {
    const [selfId, _setSelfId] = useState(initClientContext.selfId);
    const [peerId, _setPeerId] = useState(initClientContext.peerId);
    const [onFrame, _setOnFrame] = useState(initClientContext.video.onFrame);
    const [messages, _setMessages] = useState(initClientContext.chat.messages);

    const navigate = useNavigate();

    const joinPeer = (peer_id) => {
        console.log(`(renderer): Setting peer_id ${peer_id} from user input.`);
        _setPeerId(peer_id);
        services.joinPeer(peer_id)
    }

    // Establish middleware listeners on initial render
    useEffect(() => {
        window.electronAPI.ipcListen('self_id', (e: IpcMainEvent, id: string) => {
            console.log(`(renderer): Received self_id ${id} from \`main.ts\`.`)
            _setSelfId(id);

            // Navigate away from Splash page after receiving self_id
            if(window.location.pathname === '/splash') {
                console.log('(renderer): Closing Splash page.')
                navigate('/');
            }
        })

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

        // Inform main process that ClientContext is ready for IPC communication
        console.log('(renderer): Renderer Ready');
        window.electronAPI.rendererReady();
    }, []);

    return (
        <ClientContext.Provider value={{
            selfId: selfId,
            peerId: peerId,
            joinPeer: services.joinPeer,
            video: {
                onFrame: onFrame
            },
            chat: {
                messages: messages,
                sendMessage: services.chat.sendMessage
            },
            quitSession: services.quitSession
        }}>
            {children}
        </ClientContext.Provider>
    )
}