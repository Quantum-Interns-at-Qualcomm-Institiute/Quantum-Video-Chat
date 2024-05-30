const services = {
    setPeerId: setPeerId,
    video: {

    },
    chat: {
        sendMessage: sendMessage
    }
}

export async function setPeerId() {

}

export async function sendMessage(message: string) {
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

export async function onMessage(messageData: Object) {
    console.log(`(renderer): Received chat message with Object structure ${JSON.stringify(messageData)}`)

    // TODO: Append new message to list of messages.
    // Not sure how to get around circular import, but not important rn
    // _setMessages([...messages, messageData]);
}

export default services