const services = {
    isValidId: isValidId,
    joinRoom: joinRoom,
    leaveRoom: leaveRoom,
    video: {

    },
    chat: {
        sendMessage: sendMessage
    }
}

async function joinRoom(room_id?: string) {
    console.log(`(services): Attempting to join room with ${room_id ? 'room_id' + room_id : 'no room_id'}`);
    window.electronAPI.joinRoom(room_id);
}

async function leaveRoom() {
    console.log(`(services): Leaving video chat room`)
    window.electronAPI.leaveRoom();
}

async function sendMessage(message: string) {
    console.log(`(services): Sending chat message '${message}'`);

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
            error: "Please enter a valid room ID."
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