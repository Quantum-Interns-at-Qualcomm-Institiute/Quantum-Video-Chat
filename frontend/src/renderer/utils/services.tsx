const services = {
    isValidId: isValidId,
    joinPeer: joinPeer,
    video: {

    },
    chat: {
        sendMessage: sendMessage
    }
}

async function joinPeer(peerId: string) {
    // window.electronAPI.joinPeer(peerId)
}

async function sendMessage(message: string) {
    console.log(`(renderer): Sending chat message '${message}'`);

    const date = new Date();
    const time = date.toLocaleTimeString();
    // TODO: Need to replace `name: "Client 1"` with self_id
    // Not sure how to get around circular import, but not important rn
    const messageData = {
        time: time.substring(0, time.length - 6),
        name: "Client 1",
        body: message,
    };

    // TODO: send the message
}

function isValidId(id: string) {
    let isAlphanumeric = id.match(/^[a-zA-Z0-9]+$/) !== null;

    if (id === "")
        return {
            ok: false,
            error: "Please enter a valid ID."
        }
    
    else if(!isAlphanumeric)
        return {
            ok: false,
            error: "ID must be alphanumeric."
        }

    else if(id.length !== 5)
        return {
            ok: false,
            error: "Code must be strictly 5 characters."
        }

    else return {ok: true, error: ''}
}

export default services