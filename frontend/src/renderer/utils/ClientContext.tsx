import { useState, createContext, useEffect } from "react";
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
    setPeerId: () => {},
    video: {
        onFrame: null,
    },
    chat: {
        messages: [{}],
        sendMessage: (message: string) => {},
    }
}

export const ClientContext = createContext(initClientContext);

export function ClientContextProvider({ children } ) {
    const [selfId, _setSelfId] = useState('');
    const [peerId, _setPeerId] = useState('');
    const [onFrame, _setOnFrame] = useState(null);
    const [messages, _setMessages] = useState(initMessages);

    // Establish middleware listeners on initial render
    useEffect(() => {
        window.electronAPI.ipcListen('self_id', (e, data: string) => {
            console.log(`(renderer): Received self_id ${data} from \`main.ts\`.`)
            _setSelfId(data);
        })
    }, []);

    return (
        <ClientContext.Provider value={{
            selfId: selfId,
            peerId: peerId,
            setPeerId: services.setPeerId, 
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