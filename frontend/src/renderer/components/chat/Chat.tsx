import Message from "./Message";

import "./Chat.css";

interface MessageData {
    time: string;
    name: string;
    body?: string;
}

interface ChatProps {
    handleSend: (message: string) => void;
    messages: MessageData[];
}

export default function Chat(props: ChatProps) {
    function getMessages() {
        if (!props.messages) return;
        return props.messages.map((message, i) => {
            if (!message.time || !message.name) return null;
            return (
                <Message key={i} time={message.time} name={message.name}>
                    {message.body ?? null}
                </Message>
            );
        });
    }

    function handleSubmit(e) {
        e.preventDefault();
        const message = e.target[0].value;
        if (props.handleSend && message.trim()) props.handleSend(message);
        e.target[0].value = "";
    }

    return (
        <div className="chat">
            <div className="messages">
                {getMessages()}
            </div>
            <form className="chat-field" onSubmit={handleSubmit}>
                <input type="text" name="Message" id="text" placeholder="Message" />
                <input type="submit" id="send" name="submit" />
            </form>
        </div>
    );
}
