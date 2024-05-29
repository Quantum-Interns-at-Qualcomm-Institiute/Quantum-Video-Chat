import { useState, createContext, useEffect } from "react";
import services from './services';

const initClientContext = {
    selfId: null,
    peerId: null,
    setPeerId: () => {},
    onFrame: null,
}

export const ClientContext = createContext(initClientContext);

export function ClientContextProvider({ children } ) {
    const [selfId, _setSelfId] = useState(null);
    const [peerId, _setPeerId] = useState(null);
    const [onFrame, _setOnFrame] = useState(null);

    // Establish middleware listeners on initial render
    useEffect(() => {
        window.electronAPI.ipcListen('self_id', (e, data) => {
            console.log(`(renderer): Received self_id ${data} from \`main.ts\`.`)
            _setSelfId(data);
        })
    }, []);

    return (
        <ClientContext.Provider value={{
            selfId: selfId,
            peerId: peerId,
            setPeerId: services.setPeerId, 
            onFrame: onFrame
        }}>
            {children}
        </ClientContext.Provider>
    )
}